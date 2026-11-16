import type {
  ApiResponse, AuthClientOptions, AuthState, Flow, TokenStore, Tokens, Transport,
} from "./types";
import { createCredential, getCredential } from "./webauthn";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Keeps header-transport tokens in memory: gone on reload, invisible to other tabs. */
export function memoryStore(): TokenStore {
  let tokens: Tokens | null = null;
  return { get: () => tokens, set: (value) => { tokens = value; } };
}

/**
 * Keeps header-transport tokens in localStorage. Readable by any script on the
 * page, so an XSS bug leaks them; browsers should prefer cookie transport.
 */
export function localStorageStore(key = "dj-rest-jwt:tokens"): TokenStore {
  return {
    get: () => {
      try { return JSON.parse(localStorage.getItem(key) ?? "null"); } catch { return null; }
    },
    set: (value) => {
      try {
        if (value) localStorage.setItem(key, JSON.stringify(value)); else localStorage.removeItem(key);
      } catch { /* storage unavailable */ }
    },
  };
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

function jwtExpiry(token: string): number | null {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const exp = JSON.parse(atob(part.padEnd(Math.ceil(part.length / 4) * 4, "="))).exp;
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

function pendingFlow(body: ApiResponse | null): Flow | null {
  return body?.data?.flows?.find?.((f: Flow) => f.is_pending) ?? null;
}

type Listener = (state: AuthState) => void;
type Body = Record<string, unknown> | undefined;

interface RequestOptions {
  body?: Body;
  /** Refresh the access token and retry once on 401. Off for sign-in steps. */
  refresh?: boolean;
  headers?: Record<string, string>;
}

/**
 * Talks to dj-rest-jwt (allauth headless under the hood).
 *
 * - Refreshes the access token once on 401 and retries the request; one
 *   refresh at a time per tab, and across tabs with the Web Locks API.
 * - Tells other tabs about sign-in/sign-out (BroadcastChannel).
 * - Cookie transport: sends the CSRF token; never touches tokens.
 *   Header transport: stores tokens, sends `Authorization: Bearer`.
 * - Carries allauth's short-lived `X-Session-Token` through multi-step
 *   sign-in (MFA, email code, passkey signup).
 */
export class AuthClient {
  readonly transport: Transport;
  readonly baseUrl: string;
  private readonly store: TokenStore;
  private readonly fetchImpl: typeof fetch;
  private readonly credentials: RequestCredentials;
  private readonly csrfCookieName: string;
  private readonly csrfHeaderName: string;
  private readonly channelName: string;
  private readonly leewayMs: number;
  private readonly channel: BroadcastChannel | null;
  private state: AuthState = { status: "unknown", user: null, pendingFlow: null, flows: [], methods: [] };
  private listeners = new Set<Listener>();
  private sessionToken: string | null = null;
  private refreshing: Promise<boolean> | null = null;
  private lastRefreshLocal = 0;

  constructor(options: AuthClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "/api/auth/v1").replace(/\/$/, "");
    this.transport = options.transport ?? "cookie";
    this.store = options.tokenStore ?? memoryStore();
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.credentials = options.credentials ?? "include";
    this.csrfCookieName = options.csrfCookieName ?? "csrftoken";
    this.csrfHeaderName = options.csrfHeaderName ?? "X-CSRFToken";
    this.channelName = options.channelName ?? "dj-rest-jwt";
    this.leewayMs = (options.refreshLeewaySeconds ?? 30) * 1000;
    this.channel = typeof BroadcastChannel === "function" ? new BroadcastChannel(this.channelName) : null;
    this.channel?.addEventListener("message", (event) => this.onTabMessage(event.data));
  }

  // --- State ---------------------------------------------------------------

  getState = (): AuthState => this.state;

  /** Calls `listener` on every state change. Returns an unsubscribe function. */
  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  private setState(patch: Partial<AuthState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener(this.state));
  }

  // --- Low-level requests ----------------------------------------------------

  /** Calls an endpoint under `baseUrl`, e.g. `request("GET", "/auth/sessions")`. */
  async request<T = any>(method: string, path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    const { body, refresh = true, headers } = options;
    const startedAt = Date.now();
    let res = await this.send(method, this.baseUrl + path, body, { sessionToken: true, headers });
    if (res.status === 401 && refresh && !pendingFlow(res.json) && (await this.mayHaveSession())) {
      if (await this.refresh(startedAt)) {
        res = await this.send(method, this.baseUrl + path, body, { sessionToken: true, headers });
      }
    }
    await this.absorb(res.status, res.json);
    return res.json;
  }

  /**
   * `fetch` for your own API: adds credentials, refreshes on 401 and retries
   * once. Credentials are only attached for the API's own origin (and any in
   * `trustedOrigins`), so a stray absolute URL can't leak a token.
   */
  async fetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
    const startedAt = Date.now();
    const attempt = async () => {
      const headers = new Headers(init.headers);
      const method = (init.method ?? "GET").toUpperCase();
      if (this.isOwnOrigin(String(input))) await this.authorize(headers, method, true);
      return this.fetchImpl(input, { ...init, headers, credentials: this.requestCredentials() });
    };
    let res = await attempt();
    if (res.status === 401 && this.isOwnOrigin(String(input)) && (await this.mayHaveSession())) {
      if (await this.refresh(startedAt)) res = await attempt();
    }
    return res;
  }

  private requestCredentials(): RequestCredentials {
    return this.transport === "cookie" ? this.credentials : "omit";
  }

  private isOwnOrigin(url: string): boolean {
    const here = (globalThis as any).location?.href;
    try {
      const target = new URL(url, here ?? this.baseUrl);
      const api = new URL(this.baseUrl, here ?? this.baseUrl);
      return target.origin === api.origin;
    } catch {
      return false;
    }
  }

  private async authorize(headers: Headers, method: string, bearer: boolean) {
    if (this.transport === "header") {
      headers.set("X-Auth-Transport", "header");
      if (!bearer || headers.has("Authorization")) return;
      let tokens = await this.store.get();
      const exp = tokens ? jwtExpiry(tokens.access) : null;
      if (tokens && exp !== null && exp - Date.now() < this.leewayMs && tokens.refresh) {
        await this.refresh();
        tokens = await this.store.get();
      }
      if (tokens?.access) headers.set("Authorization", `Bearer ${tokens.access}`);
    } else if (UNSAFE_METHODS.has(method)) {
      const csrf = readCookie(this.csrfCookieName);
      if (csrf) headers.set(this.csrfHeaderName, csrf);
    }
  }

  private async send(
    method: string, url: string, body: Body,
    opts: { sessionToken?: boolean; bearer?: boolean; headers?: Record<string, string> } = {},
  ): Promise<{ status: number; json: ApiResponse }> {
    const headers = new Headers({ ...opts.headers, Accept: "application/json" });
    if (body !== undefined) headers.set("Content-Type", "application/json");
    await this.authorize(headers, method, opts.bearer ?? true);
    if (opts.sessionToken && this.sessionToken) headers.set("X-Session-Token", this.sessionToken);
    const res = await this.fetchImpl(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: this.requestCredentials(),
    });
    let json: ApiResponse;
    try {
      json = await res.json();
    } catch {
      json = { status: res.status };
    }
    return { status: res.status, json };
  }

  /** Learns from an auth response: pending-flow token, issued tokens, signed-in state. */
  private async absorb(status: number, body: ApiResponse) {
    const meta = body.meta ?? {};
    if (status === 410) this.sessionToken = null;     // the pending sign-in expired
    if (meta.session_token) this.sessionToken = meta.session_token;
    if (meta.access_token) {
      this.sessionToken = null;
      if (this.transport === "header") {
        await this.store.set({ access: meta.access_token, refresh: meta.refresh_token ?? null });
      }
    }
    if (meta.is_authenticated === undefined) return;

    const data = body.data ?? {};
    const flows: Flow[] = Array.isArray(data.flows) ? data.flows : this.state.flows;
    if (meta.is_authenticated) {
      this.sessionToken = null;
      const wasSignedIn = this.state.status === "authenticated";
      this.setState({
        status: "authenticated",
        user: data.user ?? this.state.user,
        methods: data.methods ?? this.state.methods,
        pendingFlow: pendingFlow(body),
        flows,
      });
      if (!wasSignedIn) this.broadcast("signed-in");
    } else {
      const pending = pendingFlow(body);
      const wasSignedIn = this.state.status === "authenticated";
      if (wasSignedIn && this.transport === "header") await this.store.set(null);
      this.setState({ status: pending ? "pending" : "anonymous", user: null, methods: [], pendingFlow: pending, flows });
      if (wasSignedIn) this.broadcast("signed-out");
    }
  }

  // --- Refresh -------------------------------------------------------------

  private async mayHaveSession(): Promise<boolean> {
    if (this.transport === "header") return Boolean((await this.store.get())?.refresh);
    return this.state.status !== "anonymous" && this.state.status !== "pending";
  }

  private lastRefresh(): number {
    if (this.transport === "cookie") {
      try { return Number(localStorage.getItem(`${this.channelName}:refreshed-at`)) || 0; } catch { /* fall through */ }
    }
    return this.lastRefreshLocal;
  }

  private markRefreshed() {
    this.lastRefreshLocal = Date.now();
    if (this.transport === "cookie") {
      try { localStorage.setItem(`${this.channelName}:refreshed-at`, String(this.lastRefreshLocal)); } catch { /* ignore */ }
    }
  }

  /**
   * Gets a new token pair. Resolves `true` if the caller should retry with
   * the current credentials, `false` if the session is over (state becomes
   * `anonymous`). Concurrent callers share one refresh.
   */
  refresh(startedAt = Date.now()): Promise<boolean> {
    if (!this.refreshing) {
      this.refreshing = this.withLock(() => this.doRefresh(startedAt)).finally(() => { this.refreshing = null; });
    }
    return this.refreshing;
  }

  private withLock<T>(fn: () => Promise<T>): Promise<T> {
    const locks = (globalThis as any).navigator?.locks;
    return locks?.request ? locks.request(`${this.channelName}:refresh`, fn) : fn();
  }

  private async doRefresh(startedAt: number): Promise<boolean> {
    // Another tab (cookie transport) or request already refreshed after the
    // failed request went out: just retry with what is there now.
    if (this.lastRefresh() > startedAt) return true;

    let body: Body;
    let tokens: Tokens | null = null;
    if (this.transport === "header") {
      tokens = await this.store.get();
      if (!tokens?.refresh) {
        await this.signedOut();
        return false;
      }
      body = { refresh_token: tokens.refresh };
    } else {
      body = {};
    }
    let res;
    try {
      res = await this.send("POST", `${this.baseUrl}/tokens/refresh`, body, { bearer: false });
    } catch {
      return false;   // offline: keep the session, the next call tries again
    }
    if (res.status === 200) {
      if (this.transport === "header") {
        const data = res.json.data ?? {};
        await this.store.set({ access: data.access_token, refresh: data.refresh_token ?? tokens!.refresh });
      }
      this.markRefreshed();
      return true;
    }
    if (res.status === 409) return true;      // a parallel refresh won; its tokens are in place
    if (res.status === 401) await this.signedOut();
    return false;
  }

  private async signedOut() {
    const wasSignedIn = this.state.status === "authenticated";
    this.sessionToken = null;
    if (this.transport === "header") await this.store.set(null);
    this.setState({ status: "anonymous", user: null, methods: [], pendingFlow: null });
    if (wasSignedIn) this.broadcast("signed-out");
  }

  // --- Tabs ----------------------------------------------------------------

  private broadcast(type: "signed-in" | "signed-out") {
    try { this.channel?.postMessage({ type }); } catch { /* closed */ }
  }

  private onTabMessage(message: { type?: string }) {
    if (message?.type === "signed-in" && this.state.status !== "authenticated") {
      this.setState({ status: "unknown" });
      void this.getSession();
    } else if (message?.type === "signed-out" && this.state.status === "authenticated") {
      if (this.transport === "cookie") {
        this.setState({ status: "anonymous", user: null, methods: [], pendingFlow: null });
      } else {
        void this.getSession();
      }
    }
  }

  /** Stops listening to other tabs. */
  close() {
    this.channel?.close();
  }

  // --- Session -------------------------------------------------------------

  getConfig() {
    return this.request("GET", "/config", { refresh: false });
  }

  /** Who is signed in. Call once on startup; the state leaves `unknown`. */
  getSession() {
    return this.request("GET", "/auth/session");
  }

  async logout() {
    const res = await this.request("DELETE", "/auth/session", { refresh: false });
    await this.signedOut();
    return res;
  }

  // --- Sign in -------------------------------------------------------------

  login(credentials: { email?: string; username?: string; password: string }) {
    return this.request("POST", "/auth/login", { body: credentials, refresh: false });
  }

  /** `extra` carries custom signup fields: the honeypot (leave empty) or `captcha_token`. */
  signup(fields: { email: string; password?: string; [extra: string]: unknown }) {
    return this.request("POST", "/auth/signup", { body: fields, refresh: false });
  }

  /** Finishes sign-in with a TOTP or recovery code (pending flow `mfa_authenticate`). */
  mfaAuthenticate(code: string) {
    return this.request("POST", "/auth/2fa/authenticate", { body: { code }, refresh: false });
  }

  /** Emails a sign-in code (needs `email_flows(login_code=True)` on the server). */
  requestLoginCode(email: string) {
    return this.request("POST", "/auth/code/request", { body: { email }, refresh: false });
  }

  confirmLoginCode(code: string) {
    return this.request("POST", "/auth/code/confirm", { body: { code }, refresh: false });
  }

  /** Signs in with a token from a provider SDK, e.g. Google's ID token. */
  providerToken(provider: string, token: { client_id: string; id_token?: string; access_token?: string }) {
    return this.request("POST", "/auth/provider/token", {
      body: { provider, process: "login", token }, refresh: false,
    });
  }

  // --- Email verification and password reset -------------------------------

  /** `key` is the code (code mode) or the key from the link (link mode). */
  verifyEmail(key: string) {
    return this.request("POST", "/auth/email/verify", { body: { key }, refresh: false });
  }

  resendEmailVerification() {
    return this.request("POST", "/auth/email/verify/resend", { refresh: false });
  }

  requestPasswordReset(email: string) {
    return this.request("POST", "/auth/password/request", { body: { email }, refresh: false });
  }

  /** Checks a reset code/key before asking for the new password. */
  checkPasswordReset(key: string) {
    return this.request("GET", "/auth/password/reset", { refresh: false, headers: { "X-Password-Reset-Key": key } });
  }

  resetPassword(key: string, password: string) {
    return this.request("POST", "/auth/password/reset", { body: { key, password }, refresh: false });
  }

  // --- Signed-in account ---------------------------------------------------

  /** Step-up before sensitive changes (pending flow `reauthenticate`). */
  reauthenticate(password: string) {
    return this.request("POST", "/auth/reauthenticate", { body: { password } });
  }

  mfaReauthenticate(code: string) {
    return this.request("POST", "/auth/2fa/reauthenticate", { body: { code } });
  }

  changePassword(currentPassword: string, newPassword: string) {
    return this.request("POST", "/account/password/change", {
      body: { current_password: currentPassword, new_password: newPassword },
    });
  }

  listEmails() {
    return this.request("GET", "/account/email");
  }

  addEmail(email: string) {
    return this.request("POST", "/account/email", { body: { email } });
  }

  removeEmail(email: string) {
    return this.request("DELETE", "/account/email", { body: { email } });
  }

  makePrimaryEmail(email: string) {
    return this.request("PATCH", "/account/email", { body: { email, primary: true } });
  }

  listSessions() {
    return this.request("GET", "/auth/sessions");
  }

  /** Signs out other devices by session id (from `listSessions`). */
  endSessions(ids: (string | number)[]) {
    return this.request("DELETE", "/auth/sessions", { body: { sessions: ids } });
  }

  listProviderAccounts() {
    return this.request("GET", "/account/providers");
  }

  disconnectProvider(provider: string, account: string) {
    return this.request("DELETE", "/account/providers", { body: { provider, account } });
  }

  // --- MFA -----------------------------------------------------------------

  listAuthenticators() {
    return this.request("GET", "/account/authenticators");
  }

  /** 404 with `meta.secret` + `meta.totp_url` when not set up yet: show the QR code. */
  getTotp() {
    return this.request("GET", "/account/authenticators/totp");
  }

  activateTotp(code: string) {
    return this.request("POST", "/account/authenticators/totp", { body: { code } });
  }

  deactivateTotp() {
    return this.request("DELETE", "/account/authenticators/totp");
  }

  getRecoveryCodes() {
    return this.request("GET", "/account/authenticators/recovery-codes");
  }

  regenerateRecoveryCodes() {
    return this.request("POST", "/account/authenticators/recovery-codes");
  }

  // --- Passkeys ------------------------------------------------------------

  /** Signs in with a passkey (browser prompt included). */
  async loginWithPasskey() {
    const options = await this.request("GET", "/auth/webauthn/login", { refresh: false });
    if (options.status !== 200) return options;
    const credential = await getCredential(options.data.request_options);
    return this.request("POST", "/auth/webauthn/login", { body: { credential }, refresh: false });
  }

  /** Finishes a pending `mfa_authenticate` step with a passkey instead of a code. */
  async mfaAuthenticateWithPasskey() {
    const options = await this.request("GET", "/auth/webauthn/authenticate", { refresh: false });
    if (options.status !== 200) return options;
    const credential = await getCredential(options.data.request_options);
    return this.request("POST", "/auth/webauthn/authenticate", { body: { credential }, refresh: false });
  }

  /**
   * Signs up with a passkey and no password. The server emails a code first
   * (pending flow `verify_email`); after `verifyEmail(code)` call
   * `finishPasskeySignup()`.
   */
  startPasskeySignup(email: string) {
    return this.request("POST", "/auth/webauthn/signup", { body: { email }, refresh: false });
  }

  async finishPasskeySignup(name = "Passkey") {
    const options = await this.request("GET", "/auth/webauthn/signup", { refresh: false });
    if (options.status !== 200) return options;
    const credential = await createCredential(options.data.creation_options);
    return this.request("PUT", "/auth/webauthn/signup", { body: { name, credential }, refresh: false });
  }

  /** Adds a passkey to the signed-in account. Needs a recent `reauthenticate`. */
  async addPasskey(name = "Passkey") {
    const options = await this.request("GET", "/account/authenticators/webauthn?passwordless");
    if (options.status !== 200) return options;
    const credential = await createCredential(options.data.creation_options);
    return this.request("POST", "/account/authenticators/webauthn", { body: { name, credential } });
  }

  removePasskeys(ids: (string | number)[]) {
    return this.request("DELETE", "/account/authenticators/webauthn", { body: { authenticators: ids } });
  }
}

export function createAuthClient(options?: AuthClientOptions): AuthClient {
  return new AuthClient(options);
}

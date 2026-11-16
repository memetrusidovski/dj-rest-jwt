/** How tokens travel. See the server's `dj_rest_jwt/transport.py`. */
export type Transport = "cookie" | "header";

/** Tokens held by the client in header transport. Cookie transport never sees them. */
export interface Tokens {
  access: string;
  refresh: string | null;
}

/**
 * Where header-transport tokens live. Use secure platform storage in native
 * apps (Keychain/Keystore). The default keeps them in memory only.
 */
export interface TokenStore {
  get(): Tokens | null | Promise<Tokens | null>;
  set(tokens: Tokens | null): void | Promise<void>;
}

export interface ApiError {
  code: string;
  message?: string;
  param?: string;
}

/** A step of allauth's authentication flow, e.g. `{id: "mfa_authenticate", is_pending: true}`. */
export interface Flow {
  id: string;
  is_pending?: boolean;
  types?: string[];
  provider?: { id: string; name: string; client_id?: string; flows?: string[] };
  [key: string]: unknown;
}

export interface User {
  id: number | string;
  email?: string;
  display?: string;
  has_usable_password?: boolean;
  [key: string]: unknown;
}

export interface Meta {
  is_authenticated?: boolean;
  session_token?: string;
  access_token?: string;
  refresh_token?: string;
  [key: string]: unknown;
}

/** allauth's response envelope: `{status, data, meta, errors}`. */
export interface ApiResponse<T = any> {
  status: number;
  data?: T;
  meta?: Meta;
  errors?: ApiError[];
}

export type AuthStatus = "unknown" | "anonymous" | "pending" | "authenticated";

export interface AuthState {
  /** `unknown` until the first `getSession()` answers. */
  status: AuthStatus;
  user: User | null;
  /** The step the user must finish next, e.g. `mfa_authenticate` or `verify_email`. */
  pendingFlow: Flow | null;
  /** Ways to sign in that the server offers (from the last auth response). */
  flows: Flow[];
  /** How the user signed in, e.g. `[{method: "password"}, {method: "mfa", type: "totp"}]`. */
  methods: Record<string, unknown>[];
}

export interface AuthClientOptions {
  /** Where `dj_rest_jwt.urls` is mounted, including `v1`. Default `/api/auth/v1`. */
  baseUrl?: string;
  /** Default `cookie` (browsers). Use `header` in native apps. */
  transport?: Transport;
  /** Header transport only. Default: in memory. */
  tokenStore?: TokenStore;
  /** Default: the global `fetch`. */
  fetch?: typeof fetch;
  /** Cookie transport: `include` lets an API on another subdomain set cookies (needs CORS). Default `include`. */
  credentials?: RequestCredentials;
  csrfCookieName?: string;
  csrfHeaderName?: string;
  /** Name for the cross-tab lock and broadcast channel. Change it only if two apps share an origin. */
  channelName?: string;
  /** Header transport: refresh this many seconds before the access token expires. Default 30. */
  refreshLeewaySeconds?: number;
}

/**
 * End-to-end: the client against the real demo backend, in both transports.
 *
 *   EMAIL_FILE_PATH=/tmp/mails python demo/backend/manage.py runserver 8765
 *   E2E_URL=http://localhost:8765 E2E_MAILS=/tmp/mails npx vitest run test/e2e.test.ts
 *
 * Skipped unless E2E_URL is set. Cookie transport runs through a small cookie
 * jar standing in for the browser.
 */
import { createHmac } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { createAuthClient, memoryStore, type Transport } from "../src";

const URL_ = process.env.E2E_URL;
const MAILS = process.env.E2E_MAILS ?? "";
const PASSWORD = "Correct-Horse-9-Battery";

/** A browser's cookie handling, as far as these tests need it. */
function cookieJar() {
  const jar = new Map<string, { value: string; path: string }>();
  const fetchWithCookies: typeof fetch = async (input, init = {}) => {
    const url = new URL(String(input));
    const headers = new Headers(init.headers);
    const cookie = [...jar].filter(([, c]) => url.pathname.startsWith(c.path)).map(([k, c]) => `${k}=${c.value}`);
    if (cookie.length && init.credentials !== "omit") headers.set("Cookie", cookie.join("; "));
    headers.set("Origin", url.origin);
    const res = await fetch(input, { ...init, headers });
    for (const line of res.headers.getSetCookie()) {
      const [pair, ...attrs] = line.split(";").map((s) => s.trim());
      const [name, ...rest] = pair.split("=");
      const value = rest.join("=").replace(/^"|"$/g, "");
      const path = attrs.find((a) => a.toLowerCase().startsWith("path="))?.slice(5) ?? "/";
      const expired = attrs.some((a) => /^max-age=0$/i.test(a)) || !value;
      if (expired) jar.delete(name); else jar.set(name, { value, path });
    }
    return res;
  };
  return { jar, fetch: fetchWithCookies };
}

function latestCode(email: string, after: number): string {
  for (let i = 0; i < 50; i++) {
    const files = readdirSync(MAILS)
      .map((f) => join(MAILS, f))
      .filter((f) => statSync(f).mtimeMs >= after)
      .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
    for (const file of files) {
      const text = readFileSync(file, "utf8");
      if (!text.includes(`To: ${email}`)) continue;
      const match = text.match(/^([A-Z0-9]{4}-[A-Z0-9]{4}|[0-9]{6})$/m);
      if (match) return match[1];
    }
  }
  throw new Error(`no code mailed to ${email}`);
}

function totp(secretB32: string, at = Date.now()): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secretB32.replace(/=+$/, "")) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30000)));
  const hmac = createHmac("sha1", key).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  return String((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

function setup(transport: Transport) {
  const { jar, fetch } = cookieJar();
  (globalThis as any).document = {
    get cookie() { return jar.has("csrftoken") ? `csrftoken=${jar.get("csrftoken")!.value}` : ""; },
  };
  const store = memoryStore();
  const client = createAuthClient({ baseUrl: `${URL_}/api/auth/v1`, transport, fetch, tokenStore: store });
  return { client, jar, store };
}

describe.skipIf(!URL_)("against the demo backend", () => {
  for (const transport of ["cookie", "header"] as const) {
    it(`${transport}: signup, refresh, step-up, reset, codes, MFA`, async () => {
      const { client, jar, store } = setup(transport);
      const email = `e2e-${transport}-${Date.now()}@example.com`;
      const api = (path: string, init?: RequestInit) => client.fetch(`${URL_}${path}`, init);

      // Sign up; the emailed code verifies and signs in.
      let t = Date.now() - 1000;
      let res = await client.signup({ email, password: PASSWORD });
      expect(client.getState().pendingFlow?.id).toBe("verify_email");
      res = await client.verifyEmail(latestCode(email, t));
      expect(res.status).toBe(200);
      expect(client.getState()).toMatchObject({ status: "authenticated", user: { email } });
      if (transport === "cookie") {
        expect(jar.has("access_token") && jar.has("refresh_token")).toBe(true);
        expect(JSON.stringify(res)).not.toMatch(/access_token|refresh_token|session_token/);
      } else {
        expect(jar.size).toBe(0);
        expect((await store.get())?.refresh).toBeTruthy();
      }
      expect((await api("/api/me")).status).toBe(200);

      // An expired/missing access token: parallel calls share one refresh.
      if (transport === "cookie") jar.delete("access_token");
      else await store.set({ ...(await store.get())!, access: "expired" });
      const results = await Promise.all([api("/api/me"), api("/api/me"), client.listSessions()]);
      expect(results.map((r) => r.status)).toEqual([200, 200, 200]);

      // Step-up: password change wants a fresh reauthentication.
      res = await client.changePassword(PASSWORD, `${PASSWORD}-2`);
      if (res.status === 401) {
        expect((await client.reauthenticate(PASSWORD)).status).toBe(200);
        res = await client.changePassword(PASSWORD, `${PASSWORD}-2`);
      }
      expect(res.status).toBe(200);
      expect((await api("/api/me")).status).toBe(200);   // this device stays signed in

      // Sign out: no refresh loop, API refuses.
      await client.logout();
      expect(client.getState().status).toBe("anonymous");
      expect((await api("/api/me")).status).toBe(401);

      // Password reset by code.
      t = Date.now() - 1000;
      await client.requestPasswordReset(email);
      const resetCode = latestCode(email, t);
      expect((await client.checkPasswordReset(resetCode)).status).toBe(200);
      res = await client.resetPassword(resetCode, `${PASSWORD}-3`);
      expect([200, 401]).toContain(res.status);
      expect(res.errors).toBeUndefined();

      // Passwordless sign-in code.
      t = Date.now() - 1000;
      await client.requestLoginCode(email);
      expect(client.getState().pendingFlow?.id).toBe("login_by_code");
      res = await client.confirmLoginCode(latestCode(email, t));
      expect(res.status).toBe(200);

      // TOTP, then a sign-in that asks for it.
      const setupRes = await client.getTotp();
      expect(setupRes.status).toBe(404);
      const secret = setupRes.meta!.secret as string;
      res = await client.activateTotp(totp(secret));
      if (res.status === 401) {
        await client.reauthenticate(`${PASSWORD}-3`);
        res = await client.activateTotp(totp(secret));
      }
      expect(res.status).toBe(200);
      // The same TOTP code can't be used twice, so finish the next sign-in
      // with a recovery code (generated on activation).
      res = await client.getRecoveryCodes();
      expect(res.status).toBe(200);
      const recoveryCode = res.data.unused_codes[0];
      await client.logout();
      res = await client.login({ email, password: `${PASSWORD}-3` });
      expect(res.status).toBe(401);
      expect(client.getState()).toMatchObject({ status: "pending", pendingFlow: { id: "mfa_authenticate" } });
      res = await client.mfaAuthenticate(recoveryCode);
      expect(res.status).toBe(200);
      expect((await api("/api/me")).status).toBe(200);
      await client.logout();
    }, 60_000);
  }
});

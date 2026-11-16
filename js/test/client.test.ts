import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createAuthClient } from "../src";

type Handler = (req: { method: string; url: string; headers: Headers; body: any }) => { status: number; body?: any };

function fakeServer(handler: Handler) {
  const calls: { method: string; url: string; headers: Headers; body: any }[] = [];
  const fetch = async (input: any, init: any = {}) => {
    const req = {
      method: (init.method ?? "GET").toUpperCase(),
      url: String(input),
      headers: new Headers(init.headers),
      body: init.body ? JSON.parse(init.body) : undefined,
    };
    calls.push(req);
    await new Promise((r) => setTimeout(r, 5));
    const { status, body } = handler(req);
    return new Response(body === undefined ? null : JSON.stringify(body), { status });
  };
  return { fetch: fetch as typeof globalThis.fetch, calls };
}

const user = { id: 1, email: "a@example.com" };
const signedIn = { status: 200, body: { status: 200, data: { user }, meta: { is_authenticated: true } } };
const signedOut = { status: 401, body: { status: 401, data: { flows: [{ id: "login" }] }, meta: { is_authenticated: false } } };

function jwt(expInSeconds: number) {
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expInSeconds }));
  return `h.${payload}.s`;
}

beforeEach(() => {
  (globalThis as any).document = { cookie: "csrftoken=csrf123" };
});
afterEach(() => {
  delete (globalThis as any).document;
});

describe("cookie transport", () => {
  it("refreshes once for concurrent 401s and retries each request", async () => {
    let fresh = false;
    const { fetch, calls } = fakeServer((req) => {
      if (req.url.endsWith("/tokens/refresh")) {
        fresh = true;
        return { status: 200, body: { status: 200, data: {} } };
      }
      if (req.url.endsWith("/auth/session")) return fresh ? signedIn : signedOut;
      return { status: fresh ? 200 : 401, body: {} };
    });
    const client = createAuthClient({ fetch, baseUrl: "http://api.test/api/auth/v1" });
    const [a, b, c] = await Promise.all([
      client.fetch("http://api.test/api/items"),
      client.fetch("http://api.test/api/orders"),
      client.getSession(),
    ]);
    expect([a.status, b.status, c.status]).toEqual([200, 200, 200]);
    expect(calls.filter((x) => x.url.endsWith("/tokens/refresh"))).toHaveLength(1);
    expect(client.getState()).toMatchObject({ status: "authenticated", user });
  });

  it("sends the CSRF token on unsafe methods, never a bearer token", async () => {
    const { fetch, calls } = fakeServer(() => ({ status: 200, body: {} }));
    const client = createAuthClient({ fetch, baseUrl: "http://api.test/api/auth/v1" });
    await client.fetch("http://api.test/api/items", { method: "POST" });
    await client.fetch("http://api.test/api/items");
    expect(calls[0].headers.get("X-CSRFToken")).toBe("csrf123");
    expect(calls[1].headers.get("X-CSRFToken")).toBeNull();
    expect(calls.some((x) => x.headers.has("Authorization"))).toBe(false);
  });

  it("treats 409 token_rotated as 'someone else refreshed' and retries", async () => {
    let n = 0;
    const { fetch } = fakeServer((req) => {
      if (req.url.endsWith("/tokens/refresh")) return { status: 409, body: { errors: [{ code: "token_rotated" }] } };
      return { status: n++ === 0 ? 401 : 200, body: {} };
    });
    const client = createAuthClient({ fetch, baseUrl: "http://api.test/api/auth/v1" });
    expect((await client.fetch("http://api.test/api/items")).status).toBe(200);
    expect(client.getState().status).not.toBe("anonymous");
  });

  it("signs out when the refresh token is rejected", async () => {
    const { fetch } = fakeServer((req) => {
      if (req.url.endsWith("/tokens/refresh")) return { status: 401, body: {} };
      if (req.url.endsWith("/auth/session")) return signedOut;
      return { status: 401, body: {} };
    });
    const client = createAuthClient({ fetch, baseUrl: "http://api.test/api/auth/v1" });
    await client.getSession();
    expect(client.getState().status).toBe("anonymous");
    // Known anonymous: no more refresh attempts.
    const res = await client.fetch("http://api.test/api/items");
    expect(res.status).toBe(401);
  });

  it("does not refresh on a pending sign-in step", async () => {
    const { fetch, calls } = fakeServer((req) => {
      if (req.url.endsWith("/auth/login")) {
        return {
          status: 401,
          body: {
            status: 401,
            data: { flows: [{ id: "mfa_authenticate", is_pending: true }] },
            meta: { is_authenticated: false, session_token: "pending-1" },
          },
        };
      }
      if (req.url.endsWith("/auth/2fa/authenticate")) {
        expect(req.headers.get("X-Session-Token")).toBe("pending-1");
        return signedIn;
      }
      return { status: 500 };
    });
    const client = createAuthClient({ fetch, baseUrl: "http://api.test/api/auth/v1" });
    await client.login({ email: "a@example.com", password: "pw" });
    expect(client.getState()).toMatchObject({ status: "pending", pendingFlow: { id: "mfa_authenticate" } });
    await client.mfaAuthenticate("123456");
    expect(client.getState().status).toBe("authenticated");
    expect(calls.some((x) => x.url.endsWith("/tokens/refresh"))).toBe(false);
  });
});

describe("header transport", () => {
  it("stores issued tokens, sends Bearer, and rotates them on refresh", async () => {
    let access = jwt(-10);   // already expired once the first request goes out
    const { fetch, calls } = fakeServer((req) => {
      expect(req.headers.get("X-Auth-Transport")).toBe("header");
      if (req.url.endsWith("/auth/login")) {
        return {
          status: 200,
          body: { status: 200, data: { user }, meta: { is_authenticated: true, access_token: access, refresh_token: "r1" } },
        };
      }
      if (req.url.endsWith("/tokens/refresh")) {
        expect(req.body).toEqual({ refresh_token: "r1" });
        access = jwt(300);
        return { status: 200, body: { status: 200, data: { access_token: access, refresh_token: "r2" } } };
      }
      return { status: req.headers.get("Authorization") === `Bearer ${access}` ? 200 : 401, body: {} };
    });
    const client = createAuthClient({ fetch, transport: "header", baseUrl: "http://api.test/api/auth/v1" });
    await client.login({ email: "a@example.com", password: "pw" });
    // Proactive: the access token is expired, so it refreshes before sending.
    expect((await client.fetch("http://api.test/api/items")).status).toBe(200);
    expect(calls.filter((x) => x.url.endsWith("/tokens/refresh"))).toHaveLength(1);
    expect(calls.every((x) => x.headers.get("X-CSRFToken") === null)).toBe(true);
  });

  it("never attaches the token to another origin", async () => {
    const { fetch, calls } = fakeServer((req) => {
      if (req.url.endsWith("/auth/login")) {
        return {
          status: 200,
          body: { status: 200, data: { user }, meta: { is_authenticated: true, access_token: jwt(300), refresh_token: "r" } },
        };
      }
      return { status: 200, body: {} };
    });
    const client = createAuthClient({ fetch, transport: "header", baseUrl: "http://api.test/api/auth/v1" });
    await client.login({ email: "a@example.com", password: "pw" });
    await client.fetch("https://evil.test/collect");
    await client.fetch("http://api.test/api/items");
    expect(calls[1].headers.has("Authorization")).toBe(false);
    expect(calls[2].headers.get("Authorization")).toMatch(/^Bearer /);
  });
});

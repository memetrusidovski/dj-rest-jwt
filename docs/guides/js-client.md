# JavaScript client

`dj-rest-jwt-client` is a small, dependency-free client for browsers and JavaScript apps (React
Native, Capacitor, Electron, Node). It wraps every allauth flow and handles the parts that are
easy to get wrong:

- **Refresh on 401, then retry once.** Concurrent requests share one refresh. Across browser
  tabs, refreshes are serialized with the Web Locks API, so tabs don't race each other's
  rotation.
- **Cross-tab state.** Signing in or out in one tab updates the others (BroadcastChannel).
- **CSRF** in cookie transport; **Bearer tokens** and proactive refresh before expiry in header
  transport. Tokens are only ever attached to the API's own origin.
- **Multi-step sign-in.** Carries allauth's short-lived `X-Session-Token` through MFA, email
  codes and passkey signup, and exposes the pending step as state.
- **Passkeys** with the browser's native WebAuthn JSON support and a fallback for older
  browsers.

## Create a client

=== "Browser SPA"

    ```ts
    import { createAuthClient } from "dj-rest-jwt-client";

    export const auth = createAuthClient({ baseUrl: "/api/auth/v1" });  // cookie transport
    ```

=== "Native app"

    ```ts
    import { createAuthClient } from "dj-rest-jwt-client";
    import * as SecureStore from "expo-secure-store";

    export const auth = createAuthClient({
      baseUrl: "https://api.example.com/api/auth/v1",
      transport: "header",
      tokenStore: {
        get: async () => JSON.parse((await SecureStore.getItemAsync("tokens")) ?? "null"),
        set: (t) => t ? SecureStore.setItemAsync("tokens", JSON.stringify(t)) : SecureStore.deleteItemAsync("tokens"),
      },
    });
    ```

| Option | Default | |
|---|---|---|
| `baseUrl` | `/api/auth/v1` | Where `dj_rest_jwt.urls` is mounted, plus `v1` |
| `transport` | `"cookie"` | `"header"` for native apps |
| `tokenStore` | in memory | Header transport only. `localStorageStore()` exists but is readable by XSS. |
| `credentials` | `"include"` | Cookie transport fetch credentials |
| `refreshLeewaySeconds` | `30` | Header transport: refresh this early |
| `fetch` | global `fetch` | |

## State

```ts
auth.getState();   // { status, user, pendingFlow, flows, methods }
const unsubscribe = auth.subscribe((state) => render(state));
await auth.getSession();   // call once on startup
```

`status` is `unknown` → `anonymous` | `pending` | `authenticated`. `pendingFlow.id` names the
step the user has to finish: `verify_email`, `mfa_authenticate`, `login_by_code`,
`mfa_signup_webauthn`, or `reauthenticate` (while signed in).

## Your own API

```ts
const res = await auth.fetch("/api/orders", { method: "POST", body: JSON.stringify(order),
  headers: { "Content-Type": "application/json" } });
```

`auth.fetch` is `fetch` plus credentials, CSRF, refresh-and-retry on 401.

## Flows

Every method returns allauth's response envelope `{status, data, meta, errors}`.

| Flow | Methods |
|---|---|
| Password sign-in | `login({email, password})`, then `mfaAuthenticate(code)` or `mfaAuthenticateWithPasskey()` if pending |
| Sign-in by email code | `requestLoginCode(email)`, `confirmLoginCode(code)` |
| Passkey sign-in | `loginWithPasskey()` |
| Social | `providerToken("google", {client_id, id_token})` |
| Signup | `signup({email, password, ...extraFields})`, `verifyEmail(code)`, `resendEmailVerification()` |
| Passkey-only signup | `startPasskeySignup(email)`, `verifyEmail(code)`, `finishPasskeySignup(name)` |
| Password reset | `requestPasswordReset(email)`, `checkPasswordReset(key)`, `resetPassword(key, password)` |
| Step-up | `reauthenticate(password)`, `mfaReauthenticate(code)` |
| Account | `changePassword`, `listEmails`, `addEmail`, `removeEmail`, `makePrimaryEmail` |
| Devices | `listSessions()`, `endSessions(ids)`, `logout()` |
| MFA | `getTotp()`, `activateTotp(code)`, `deactivateTotp()`, `getRecoveryCodes()`, `regenerateRecoveryCodes()` |
| Passkeys | `addPasskey(name)`, `removePasskeys(ids)`, `listAuthenticators()` |
| Anything else | `request(method, path, {body})` |

### Step-up re-authentication

Sensitive actions (adding a passkey, enabling TOTP, viewing recovery codes, changing the password)
answer `401` with a pending `reauthenticate` flow if the last explicit password or 2FA check is
old. Ask for the password, call `reauthenticate`, and retry. The demo's `useReauth` hook does
this in a few lines.

## React

```tsx
import { AuthProvider, useAuth } from "dj-rest-jwt-client/react";

<AuthProvider client={auth}><App /></AuthProvider>

function Header() {
  const { status, user, client } = useAuth();
  return status === "authenticated"
    ? <button onClick={() => client.logout()}>Sign out {user?.email}</button>
    : <a href="/login">Sign in</a>;
}
```

Other frameworks: `subscribe` + `getState` is all a store binding needs (Vue `shallowRef`,
Svelte `readable`, Solid `from`).

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { passkeysSupported } from "dj-rest-jwt-client";
import { useAuth } from "dj-rest-jwt-client/react";
import { Card, Errors, Field, Form, useAction } from "../ui";

export function Login() {
  const { client, status } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, errors, run } = useAction();

  useEffect(() => {
    if (status === "authenticated") navigate("/");
  }, [status, navigate]);

  return (
    <Card title="Sign in">
      <Form onSubmit={() => run(() => client.login({ email, password }))}>
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="username webauthn" autoFocus />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        <Errors errors={errors} />
        <button disabled={busy}>Sign in</button>
      </Form>
      <div className="alt">
        {passkeysSupported() && (
          <button className="secondary" disabled={busy} onClick={() => run(() => client.loginWithPasskey())}>
            Sign in with a passkey
          </button>
        )}
        <button
          className="secondary"
          disabled={busy || !email}
          title={email ? "" : "Enter your email first"}
          onClick={() => run(() => client.requestLoginCode(email))}
        >
          Email me a sign-in code
        </button>
        <GoogleButton />
      </div>
      <p className="muted"><Link to="/forgot-password">Forgot password?</Link> · <Link to="/signup">Create an account</Link></p>
    </Card>
  );
}

/**
 * "Sign in with Google" via Google Identity Services. Shown only when the
 * backend has a Google app configured (GOOGLE_CLIENT_ID). The ID token goes
 * to auth/provider/token; no redirect.
 */
function GoogleButton() {
  const { client } = useAuth();
  const ref = useRef<HTMLDivElement>(null);
  const [clientId, setClientId] = useState<string | null>(null);

  useEffect(() => {
    client.getConfig().then((res) => {
      const google = res.data?.socialaccount?.providers?.find((p: { id: string }) => p.id === "google");
      setClientId(google?.client_id ?? null);
    });
  }, [client]);

  useEffect(() => {
    if (!clientId || !ref.current) return;
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      const google = (window as any).google;
      google.accounts.id.initialize({
        client_id: clientId,
        callback: ({ credential }: { credential: string }) =>
          client.providerToken("google", { client_id: clientId, id_token: credential }),
      });
      google.accounts.id.renderButton(ref.current, { theme: "outline", size: "large" });
    };
    document.head.appendChild(script);
    return () => { script.remove(); };
  }, [clientId, client]);

  return clientId ? <div ref={ref} /> : null;
}

/** Pending flow `login_by_code`: the code from the sign-in email. */
export function LoginCode() {
  const { client } = useAuth();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const { busy, errors, run } = useAction();
  return (
    <Card title="Check your email">
      <p>We sent you a sign-in code.</p>
      <Form onSubmit={async () => {
        const res = await run(() => client.confirmLoginCode(code));
        if (res?.status === 200) navigate("/");
      }}>
        <Field label="Code" value={code} onChange={setCode} autoComplete="one-time-code" autoFocus />
        <Errors errors={errors} />
        <button disabled={busy}>Sign in</button>
      </Form>
    </Card>
  );
}

/** Pending flow `mfa_authenticate`: TOTP, recovery code, or a passkey. */
export function Mfa() {
  const { client, pendingFlow } = useAuth();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const { busy, errors, run } = useAction();
  const types = pendingFlow?.types ?? [];
  return (
    <Card title="Two-factor authentication">
      <Form onSubmit={async () => {
        const res = await run(() => client.mfaAuthenticate(code));
        if (res?.status === 200) navigate("/");
      }}>
        <Field label="Authenticator app or recovery code" value={code} onChange={setCode} autoComplete="one-time-code" autoFocus />
        <Errors errors={errors} />
        <button disabled={busy}>Verify</button>
      </Form>
      {types.includes("webauthn") && (
        <div className="alt">
          <button
            className="secondary"
            disabled={busy}
            onClick={async () => {
              const res = await run(() => client.mfaAuthenticateWithPasskey());
              if (res?.status === 200) navigate("/");
            }}
          >
            Use a passkey instead
          </button>
        </div>
      )}
    </Card>
  );
}

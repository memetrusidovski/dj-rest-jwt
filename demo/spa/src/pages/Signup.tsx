import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { passkeysSupported } from "dj-rest-jwt-client";
import { useAuth } from "dj-rest-jwt-client/react";
import { Card, Errors, Field, Form, useAction } from "../ui";

export function Signup() {
  const { client } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Honeypot: hidden from people, filled in by naive bots. The server's
  // DJ_REST_JWT["HONEYPOT_FIELD_NAME"] (default "website") rejects any value.
  const [website, setWebsite] = useState("");
  const { busy, errors, run } = useAction();

  return (
    <Card title="Create an account">
      <Form onSubmit={() => run(() => client.signup({ email, password, website }))}>
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" autoFocus />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
        <input
          className="honeypot" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true"
          value={website} onChange={(e) => setWebsite(e.target.value)}
        />
        <Errors errors={errors} />
        <button disabled={busy}>Sign up</button>
      </Form>
      {passkeysSupported() && (
        <div className="alt">
          <button
            className="secondary"
            disabled={busy || !email}
            title={email ? "" : "Enter your email first"}
            onClick={() => run(() => client.startPasskeySignup(email))}
          >
            Sign up with a passkey instead (no password)
          </button>
        </div>
      )}
      <p className="muted">Already have an account? <Link to="/login">Sign in</Link></p>
    </Card>
  );
}

/**
 * Pending flow `verify_email`. Code mode: the user types the emailed code.
 * Link mode: the email links to /verify-email/:key and this submits it.
 */
export function VerifyEmail() {
  const { client, status } = useAuth();
  const { key } = useParams();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const { busy, errors, run } = useAction();
  const sent = useRef(false);

  async function verify(value: string) {
    const res = await run(() => client.verifyEmail(value));
    if (res?.status === 200) navigate("/");
  }

  useEffect(() => {
    if (key && !sent.current) {
      sent.current = true;
      void verify(key);
    }
  }, [key]);

  if (key) {
    return (
      <Card title="Confirming your email…">
        <Errors errors={errors} />
        {status !== "authenticated" && !busy && !errors.length && <p>Email confirmed. <Link to="/login">Sign in</Link>.</p>}
      </Card>
    );
  }
  return (
    <Card title="Confirm your email">
      <p>We sent a code to your inbox. (The demo backend prints emails to its console.)</p>
      <Form onSubmit={() => verify(code)}>
        <Field label="Code" value={code} onChange={setCode} autoComplete="one-time-code" autoFocus />
        <Errors errors={errors} />
        <button disabled={busy}>Confirm</button>
      </Form>
      <button className="link" disabled={busy} onClick={() => run(() => client.resendEmailVerification())}>
        Send a new code
      </button>
    </Card>
  );
}

/** Pending flow `mfa_signup_webauthn`: create the passkey that replaces the password. */
export function PasskeySignup() {
  const { client } = useAuth();
  const navigate = useNavigate();
  const { busy, errors, run } = useAction();
  return (
    <Card title="Create your passkey">
      <p>Your email is confirmed. Now save a passkey on this device; you'll use it to sign in.</p>
      <Errors errors={errors} />
      <button
        disabled={busy}
        onClick={async () => {
          const res = await run(() => client.finishPasskeySignup("This device"));
          if (res?.status === 200) navigate("/");
        }}
      >
        Create passkey
      </button>
    </Card>
  );
}

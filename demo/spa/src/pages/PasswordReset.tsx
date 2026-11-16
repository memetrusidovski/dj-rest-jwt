import { useState } from "react";
import { Link, useParams } from "react-router";
import { useAuth } from "dj-rest-jwt-client/react";
import { Card, Errors, Field, Form, useAction } from "../ui";

/**
 * Code mode (the preset): ask for the email, then the code and the new
 * password on the same page.
 */
export function ForgotPassword() {
  const { client } = useAuth();
  const [email, setEmail] = useState("");
  const [requested, setRequested] = useState(false);
  const { busy, errors, run } = useAction();

  if (!requested) {
    return (
      <Card title="Reset your password">
        <Form onSubmit={async () => {
          const res = await run(() => client.requestPasswordReset(email));
          // 401 + pending `password_reset_by_code` in code mode, 200 in link mode.
          if (res && (res.status === 200 || res.status === 401)) setRequested(true);
        }}>
          <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" autoFocus />
          <Errors errors={errors} />
          <button disabled={busy}>Send reset email</button>
        </Form>
      </Card>
    );
  }
  return <NewPassword intro="If that address has an account, we emailed it a code." askForCode />;
}

/** Link mode: the email links here with the key in the URL. */
export function ResetPasswordFromLink() {
  const { key } = useParams();
  return <NewPassword intro="Choose a new password." resetKey={key} />;
}

function NewPassword({ intro, resetKey, askForCode }: { intro: string; resetKey?: string; askForCode?: boolean }) {
  const { client } = useAuth();
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const { busy, errors, run } = useAction();

  if (done) {
    return <Card title="Password changed"><p>You can now <Link to="/login">sign in</Link>.</p></Card>;
  }
  return (
    <Card title="Set a new password">
      <p>{intro}</p>
      <Form onSubmit={async () => {
        const res = await run(() => client.resetPassword(resetKey ?? code, password));
        // ACCOUNT_LOGIN_ON_PASSWORD_RESET is off in the preset, so a reset
        // answers 401 (not signed in) on success.
        if (res && (res.status === 200 || (res.status === 401 && !res.errors))) setDone(true);
      }}>
        {askForCode && <Field label="Code" value={code} onChange={setCode} autoComplete="one-time-code" autoFocus />}
        <Field label="New password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
        <Errors errors={errors} />
        <button disabled={busy}>Save password</button>
      </Form>
    </Card>
  );
}

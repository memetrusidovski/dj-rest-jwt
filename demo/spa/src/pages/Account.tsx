import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import type { ApiResponse } from "dj-rest-jwt-client";
import { passkeysSupported } from "dj-rest-jwt-client";
import { useAuth } from "dj-rest-jwt-client/react";
import { Card, Errors, Field, Form, useAction } from "../ui";

/**
 * Sensitive actions answer 401 + a pending `reauthenticate` flow when the
 * last explicit password/2FA check is too old. `withReauth` asks for the
 * password once and retries the action.
 */
function useReauth() {
  const { client } = useAuth();
  const [prompt, setPrompt] = useState<null | { retry: () => void }>(null);
  const withReauth = useCallback(
    async <T,>(action: () => Promise<ApiResponse<T>>): Promise<ApiResponse<T>> => {
      const res = await action();
      const needsReauth = res.status === 401 && res.data && (res.data as any).flows?.some(
        (f: { id: string; is_pending?: boolean }) => f.is_pending && f.id.includes("reauthenticate"),
      );
      if (!needsReauth) return res;
      return new Promise((resolve) => setPrompt({ retry: () => action().then(resolve) }));
    },
    [],
  );
  const dialog = prompt && (
    <ReauthDialog
      onDone={() => { const p = prompt; setPrompt(null); p.retry(); }}
      onCancel={() => setPrompt(null)}
      reauthenticate={(password) => client.reauthenticate(password)}
    />
  );
  return { withReauth, dialog };
}

function ReauthDialog({ onDone, onCancel, reauthenticate }: {
  onDone: () => void; onCancel: () => void; reauthenticate: (password: string) => Promise<ApiResponse>;
}) {
  const [password, setPassword] = useState("");
  const { busy, errors, run } = useAction();
  return (
    <div className="overlay">
      <Card title="Confirm it's you">
        <Form onSubmit={async () => {
          const res = await run(() => reauthenticate(password));
          if (res?.status === 200) onDone();
        }}>
          <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" autoFocus />
          <Errors errors={errors} />
          <button disabled={busy}>Continue</button>{" "}
          <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
        </Form>
      </Card>
    </div>
  );
}

export function Account() {
  const { withReauth, dialog } = useReauth();
  return (
    <>
      {dialog}
      <ChangePassword withReauth={withReauth} />
      <TwoFactor withReauth={withReauth} />
      <Passkeys withReauth={withReauth} />
      <Sessions />
    </>
  );
}

type WithReauth = ReturnType<typeof useReauth>["withReauth"];

function ChangePassword({ withReauth }: { withReauth: WithReauth }) {
  const { client } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [saved, setSaved] = useState(false);
  const { busy, errors, run } = useAction();
  return (
    <Card title="Password">
      <Form onSubmit={async () => {
        const res = await run(() => withReauth(() => client.changePassword(current, next)));
        setSaved(res?.status === 200);
      }}>
        <Field label="Current password" type="password" value={current} onChange={setCurrent} autoComplete="current-password" />
        <Field label="New password" type="password" value={next} onChange={setNext} autoComplete="new-password" />
        <Errors errors={errors} />
        <button disabled={busy}>Change password</button>
        {saved && <p className="ok">Saved. Your other devices are signed out; this one stays signed in.</p>}
      </Form>
    </Card>
  );
}

function TwoFactor({ withReauth }: { withReauth: WithReauth }) {
  const { client } = useAuth();
  const [totp, setTotp] = useState<ApiResponse | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const { busy, errors, run } = useAction();

  const load = useCallback(() => client.getTotp().then(setTotp), [client]);
  useEffect(() => { void load(); }, [load]);

  if (!totp) return <Card title="Authenticator app"><p className="muted">Loading…</p></Card>;
  const active = totp.status === 200;
  const secret = totp.meta?.secret as string | undefined;
  const url = totp.meta?.totp_url as string | undefined;

  return (
    <Card title="Authenticator app">
      {active ? (
        <>
          <p className="ok">On. Sign-in asks for a code from your app.</p>
          <button className="secondary" disabled={busy} onClick={async () => {
            const res = await run(() => withReauth(() => client.getRecoveryCodes()));
            if (res?.status === 200) setRecovery((res.data as any).unused_codes);
          }}>Show recovery codes</button>{" "}
          <button className="danger" disabled={busy} onClick={async () => {
            await run(() => withReauth(() => client.deactivateTotp()));
            setRecovery(null);
            void load();
          }}>Turn off</button>
          {recovery && <pre>{recovery.join("\n")}</pre>}
        </>
      ) : (
        <>
          <p>Scan with Google Authenticator, 1Password, Authy, … then enter the 6-digit code.</p>
          {url && <QRCodeSVG value={url} size={160} />}
          {secret && <p className="muted">Or enter the key: <code>{secret}</code></p>}
          <Form onSubmit={async () => {
            const res = await run(() => withReauth(() => client.activateTotp(code)));
            if (res?.status === 200) { setCode(""); void load(); }
          }}>
            <Field label="Code" value={code} onChange={setCode} autoComplete="one-time-code" />
            <button disabled={busy}>Turn on</button>
          </Form>
        </>
      )}
      <Errors errors={errors} />
    </Card>
  );
}

function Passkeys({ withReauth }: { withReauth: WithReauth }) {
  const { client } = useAuth();
  const [list, setList] = useState<{ id: number; name: string; created_at: number }[]>([]);
  const { busy, errors, run } = useAction();

  const load = useCallback(async () => {
    const res = await client.listAuthenticators();
    setList((res.data ?? []).filter((a: { type: string }) => a.type === "webauthn"));
  }, [client]);
  useEffect(() => { void load(); }, [load]);

  return (
    <Card title="Passkeys">
      {list.length ? (
        <ul className="rows">
          {list.map((p) => (
            <li key={p.id}>
              <span>{p.name} <span className="muted">· added {new Date(p.created_at * 1000).toLocaleDateString()}</span></span>
              <button className="link danger" disabled={busy} onClick={async () => {
                await run(() => withReauth(() => client.removePasskeys([p.id])));
                void load();
              }}>Remove</button>
            </li>
          ))}
        </ul>
      ) : <p className="muted">No passkeys yet.</p>}
      {passkeysSupported() && (
        <button disabled={busy} onClick={async () => {
          const res = await run(() => withReauth(() => client.addPasskey(navigator.platform || "Passkey")));
          if (res?.status === 200) void load();
        }}>Add a passkey</button>
      )}
      <Errors errors={errors} />
    </Card>
  );
}

function Sessions() {
  const { client } = useAuth();
  const [sessions, setSessions] = useState<any[]>([]);
  const { busy, errors, run } = useAction();

  const load = useCallback(async () => {
    const res = await client.listSessions();
    setSessions(res.data ?? []);
  }, [client]);
  useEffect(() => { void load(); }, [load]);

  const others = sessions.filter((s) => !s.is_current).map((s) => s.id);
  return (
    <Card title="Signed-in devices">
      <ul className="rows">
        {sessions.map((s) => (
          <li key={s.id}>
            <span>
              {s.user_agent || "Unknown device"} <span className="muted">· {s.ip} · last seen{" "}
              {new Date((s.last_seen_at ?? s.created_at) * 1000).toLocaleString()}</span>
              {s.is_current && <strong> (this device)</strong>}
            </span>
            {!s.is_current && (
              <button className="link danger" disabled={busy} onClick={async () => {
                await run(() => client.endSessions([s.id]));
                void load();
              }}>Sign out</button>
            )}
          </li>
        ))}
      </ul>
      {others.length > 0 && (
        <button className="secondary" disabled={busy} onClick={async () => {
          await run(() => client.endSessions(others));
          void load();
        }}>Sign out all other devices</button>
      )}
      <Errors errors={errors} />
    </Card>
  );
}

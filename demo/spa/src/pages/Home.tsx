import { useState } from "react";
import { Link } from "react-router";
import { useAuth } from "dj-rest-jwt-client/react";
import { Card } from "../ui";

export function Home() {
  const { status, user, client } = useAuth();
  const [result, setResult] = useState<string>("");

  if (status === "unknown") return <p className="muted">Loading…</p>;
  if (status !== "authenticated") {
    return (
      <Card title="Welcome">
        <p>
          A React SPA on <code>dj-rest-jwt-client</code>. Tokens live in httpOnly cookies; this page
          never sees them. Access tokens last 5 minutes and refresh on their own, so you stay signed
          in for as long as you come back within 30 days.
        </p>
        <p><Link to="/login">Sign in</Link> or <Link to="/signup">create an account</Link>.</p>
      </Card>
    );
  }

  async function callApi() {
    // client.fetch adds the CSRF header, refreshes on 401 and retries once.
    const res = await client.fetch("/api/me");
    setResult(`${res.status} ${JSON.stringify(await res.json(), null, 2)}`);
  }

  return (
    <Card title={`Hello, ${user?.display ?? user?.email}`}>
      <p>Call your own DRF API. Wait 5 minutes for the access token to expire and call it again:
        the client refreshes and retries without you noticing.</p>
      <button onClick={callApi}>GET /api/me</button>
      {result && <pre>{result}</pre>}
      <p><Link to="/account">Security settings →</Link></p>
    </Card>
  );
}

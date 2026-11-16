import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { AuthProvider, useAuth } from "dj-rest-jwt-client/react";
import { auth } from "./auth";
import { Account } from "./pages/Account";
import { Home } from "./pages/Home";
import { Login, LoginCode, Mfa } from "./pages/Login";
import { ForgotPassword, ResetPasswordFromLink } from "./pages/PasswordReset";
import { PasskeySignup, Signup, VerifyEmail } from "./pages/Signup";
import "./styles.css";

/** Where each pending sign-in step is handled. */
const FLOW_ROUTES: Record<string, string> = {
  verify_email: "/verify-email",
  mfa_authenticate: "/mfa",
  login_by_code: "/login/code",
  mfa_signup_webauthn: "/signup/passkey",
};

/** Sends the user to whatever step allauth says is next. */
function FlowRedirect() {
  const { pendingFlow, status } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    const target = pendingFlow && FLOW_ROUTES[pendingFlow.id];
    if (status === "pending" && target && !pathname.startsWith(target)) navigate(target);
  }, [pendingFlow, status, pathname, navigate]);
  return null;
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "unknown") return <p className="muted">Loading…</p>;
  return status === "authenticated" ? children : <Navigate to="/login" replace />;
}

function Nav() {
  const { status, user, client } = useAuth();
  return (
    <header className="nav">
      <Link to="/" className="brand">dj-rest-jwt demo</Link>
      <nav>
        {status === "authenticated" ? (
          <>
            <Link to="/account">{user?.email ?? "Account"}</Link>
            <button className="link" onClick={() => client.logout()}>Sign out</button>
          </>
        ) : (
          <>
            <Link to="/login">Sign in</Link>
            <Link to="/signup">Sign up</Link>
          </>
        )}
      </nav>
    </header>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Nav />
      <FlowRedirect />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/login/code" element={<LoginCode />} />
          <Route path="/mfa" element={<Mfa />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/signup/passkey" element={<PasskeySignup />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/verify-email/:key" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password/:key" element={<ResetPasswordFromLink />} />
          <Route path="/account" element={<RequireAuth><Account /></RequireAuth>} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider client={auth}>
      <App />
    </AuthProvider>
  </StrictMode>,
);

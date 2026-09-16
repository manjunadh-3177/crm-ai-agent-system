export function PublicAuthPage({
  checking,
  demoAvailable,
  message,
  auth0Configured,
  onEnterDemoWorkspace,
  onLogin,
  onSignup,
}: {
  checking: boolean;
  demoAvailable: boolean;
  message: string | null;
  auth0Configured: boolean;
  onEnterDemoWorkspace: () => void;
  onLogin: () => void;
  onSignup: () => void;
}) {
  return (
    <main className="auth-page">
      <div className="auth-shell">
        <section className="auth-hero">
          <div className="auth-hero-copy">
            <p className="sidebar-eyebrow">Acufy CRM</p>
            <h1>Agentic sales follow-up with human approval built in.</h1>
            <p className="auth-tagline">
              Multi-agent CRM workflows, approval queues, compliance checks, and live team updates in one clean workspace.
            </p>
            <div className="auth-highlights">
              <span>Live approvals</span>
              <span>Swarm agents</span>
              <span>Pipeline intelligence</span>
            </div>
          </div>
        </section>

        <section className="auth-card">
          <div className="auth-card-header">
            <p className="content-eyebrow">Workspace Access</p>
            <h2>Sign in to your workspace</h2>
            <p>Use demo mode locally or continue with real Auth0 sign-in for your team workspace.</p>
          </div>

          <div className="auth-card-panel">
            <div className="auth-actions">
              {demoAvailable ? (
                <button className="primary-button auth-button auth-primary-action" onClick={onEnterDemoWorkspace} type="button">
                  Enter Demo Workspace
                </button>
              ) : null}
              <button className="text-button auth-button" disabled={!auth0Configured} onClick={onLogin} type="button">
                Login
              </button>
              <button className="text-button auth-button" disabled={!auth0Configured} onClick={onSignup} type="button">
                Sign Up
              </button>
            </div>

            <div className="auth-support-copy">
              <div className="auth-support-item">
                <strong>Secure Auth0 sign-in</strong>
                <span>Bring your own identity provider when your frontend env is configured.</span>
              </div>
              <div className="auth-support-item">
                <strong>Local demo workspace</strong>
                <span>Explore the CRM experience instantly without leaving your dev environment.</span>
              </div>
            </div>
          </div>

          {checking ? <p className="auth-helper">Checking for an existing session...</p> : null}
          {message ? <p className="auth-helper auth-message">{message}</p> : null}
          {!auth0Configured ? (
            <p className="auth-helper">
              Auth0 login is disabled locally until <code>frontend/.env</code> has valid <code>VITE_AUTH0_*</code> values.
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

import type { PageProps } from "../types/appState";

export function EmailsPage(props: PageProps) {
  const { data, loading } = props;

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>📧 Email History</h3>
            <p className="subtle-text">All outbound emails sent from the CRM.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table email-history-table">
            <thead>
              <tr>
                <th>Sent At</th>
                <th>Recipient</th>
                <th>Subject</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "2rem" }}>
                    Loading emails...
                  </td>
                </tr>
              ) : data.emails.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "2rem" }}>
                    No emails sent yet.
                  </td>
                </tr>
              ) : (
                data.emails.map((email) => (
                  <tr key={email.id}>
                    <td>{new Date(email.created_at).toLocaleString()}</td>
                    <td className="email-history-recipient">{email.recipient_email}</td>
                    <td className="email-history-subject">{email.subject}</td>
                    <td>
                      <span className={`status-pill ${email.status === "sent" ? "won" : "lost"}`}>
                        {email.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

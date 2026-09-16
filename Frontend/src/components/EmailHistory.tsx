import type { EmailMessage } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

export function EmailHistory({ emails }: { emails: EmailMessage[] }) {
  if (emails.length === 0) {
    return <p className="modal-copy">No emails sent yet.</p>;
  }

  return (
    <div className="agent-activity-list">
      {emails.map((email) => (
        <div key={email.id} className="agent-activity-item" style={{ borderLeft: "4px solid #ef4444" }}>
          <div className="meeting-row-header">
            <strong>📧 {email.subject}</strong>
            <span className={`status-pill ${email.status === "sent" ? "won" : "lost"}`}>{email.status}</span>
          </div>
          <span>To: {email.recipient_email}</span>
          <span>{formatDateTime(email.created_at)}</span>
        </div>
      ))}
    </div>
  );
}

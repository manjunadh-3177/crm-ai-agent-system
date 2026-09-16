import { useEffect, useState } from "react";
import type { Approval } from "../lib/api";
import { EmailBodyPreview } from "./EmailBodyPreview";

export function ApprovalDraftModal({
  approval,
  saving,
  onSave,
  onClose,
}: {
  approval: Approval;
  saving: boolean;
  onSave: (subject: string, body: string) => Promise<void>;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(approval.subject);
  const [body, setBody] = useState(approval.body);

  useEffect(() => {
    setSubject(approval.subject);
    setBody(approval.body);
    setEditing(false);
  }, [approval.body, approval.subject, approval.id]);

  async function handleCopy() {
    await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <p className="content-eyebrow">✅ Pending Approval</p>
            <h3>{approval.contact_name}</h3>
          </div>
          <div className="action-row">
            <button className="text-button" onClick={() => setEditing((current) => !current)} type="button">
              {editing ? "❌ Cancel Edit" : "✏️ Edit"}
            </button>
            <button className="text-button" onClick={() => void handleCopy()} type="button">
              📋 Copy
            </button>
            <button className="text-button" onClick={onClose} type="button">
              ❌ Close
            </button>
          </div>
        </div>

        <div className="modal-body">
          <div className="priority-badge medium">{approval.status}</div>
          <div>
            <h4>Subject</h4>
            {editing ? (
              <input
                className="modal-input"
                onChange={(event) => setSubject(event.target.value)}
                value={subject}
              />
            ) : (
              <p className="modal-copy">{subject}</p>
            )}
          </div>
          <div>
            <h4>Body</h4>
            {editing ? (
              <textarea
                className="modal-textarea"
                onChange={(event) => setBody(event.target.value)}
                rows={10}
                value={body}
              />
            ) : (
              <EmailBodyPreview body={body} />
            )}
          </div>
          {editing ? (
            <div className="form-actions">
              <button
                className="primary-button"
                disabled={saving || !subject.trim() || !body.trim()}
                onClick={() => void onSave(subject, body)}
                type="button"
              >
                {saving ? "💾 Saving..." : "💾 Save Changes"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

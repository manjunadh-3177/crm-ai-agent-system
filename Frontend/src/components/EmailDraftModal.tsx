import type { Contact, EmailDraft } from "../lib/api";
import { EmailBodyPreview } from "./EmailBodyPreview";

export function EmailDraftModal({
  contact,
  draft,
  loading,
  onClose,
}: {
  contact: Contact;
  draft: EmailDraft | null;
  loading: boolean;
  onClose: () => void;
}) {
  async function handleCopy() {
    if (!draft) {
      return;
    }
    await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`);
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <p className="content-eyebrow">✉️ Draft Email</p>
            <h3>
              {contact.first_name} {contact.last_name}
            </h3>
          </div>
          <div className="action-row">
            {draft ? (
              <button className="text-button" onClick={() => void handleCopy()} type="button">
                📋 Copy
              </button>
            ) : null}
            <button className="text-button" onClick={onClose} type="button">
              ❌ Close
            </button>
          </div>
        </div>

        {loading ? (
          <p className="modal-copy">Generating draft...</p>
        ) : draft ? (
          <div className="modal-body">
            <div className="priority-badge low">{draft.tone}</div>
            <div>
              <h4>Subject</h4>
              <p className="modal-copy">{draft.subject}</p>
            </div>
            <div>
              <h4>Body</h4>
              <EmailBodyPreview body={draft.body} />
            </div>
          </div>
        ) : (
          <p className="modal-copy">No draft available.</p>
        )}
      </div>
    </div>
  );
}

import type { Deal, ProposalDraft } from "../lib/api";

export function ProposalDraftModal({
  deal,
  draft,
  loading,
  onClose,
}: {
  deal: Deal;
  draft: ProposalDraft | null;
  loading: boolean;
  onClose: () => void;
}) {
  async function handleCopy() {
    if (!draft) {
      return;
    }
    await navigator.clipboard.writeText(draft.content);
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card proposal-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <p className="content-eyebrow">📝 Proposal Draft</p>
            <h3>{deal.name}</h3>
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
          <p className="modal-copy">Generating proposal draft...</p>
        ) : draft ? (
          <div className="modal-body">
            <div className="priority-badge medium">{draft.document.status}</div>
            <div>
              <h4>{draft.title}</h4>
              <pre className="draft-body proposal-body">{draft.content}</pre>
            </div>
          </div>
        ) : (
          <p className="modal-copy">No proposal draft available.</p>
        )}
      </div>
    </div>
  );
}

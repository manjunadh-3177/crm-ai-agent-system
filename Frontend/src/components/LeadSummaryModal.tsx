import type { Contact, LeadSummary } from "../lib/api";

export function LeadSummaryModal({
  contact,
  summary,
  loading,
  onClose,
}: {
  contact: Contact;
  summary: LeadSummary | null;
  loading: boolean;
  onClose: () => void;
}) {
  const leadTemperature = (contact.lead_tier || "cold").toLowerCase();

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <p className="content-eyebrow">LeadQualifierAgent</p>
            <h3>
              {contact.first_name} {contact.last_name}
            </h3>
          </div>
          <button className="text-button" onClick={onClose} type="button">
            Close
          </button>
        </div>

        {loading ? (
          <p className="modal-copy">Analyzing lead profile...</p>
        ) : (
          <div className="modal-body">
            <div className="swarm-metrics-grid">
              <div className="agent-activity-item">
                <strong>Lead Score</strong>
                <span>{contact.lead_score}/100</span>
              </div>
              <div className="agent-activity-item">
                <strong>Temperature</strong>
                <span className={`status-pill ${leadTemperature}`}>{contact.lead_tier || "Cold"}</span>
              </div>
            </div>
            <div>
              <h4>Reasoning</h4>
              <p className="modal-copy">{contact.lead_reason || "No lead reasoning captured yet."}</p>
            </div>
            <div>
              <h4>Summary</h4>
              <p className="modal-copy">{summary?.summary || "No summary available."}</p>
            </div>
            <div>
              <h4>Recommended Next Action</h4>
              <p className="modal-copy">{summary?.recommended_next_action || "No next action available."}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

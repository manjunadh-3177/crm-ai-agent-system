import type { PageProps } from "../types/appState";
import { getRunStatusClass, formatDateTime } from "../lib/formatters";

export function ApprovalsPage({
  data,
  loading,
  approvalSubmittingId,
  onApprove,
  onApproveAndSendSms,
  onReject,
  onViewApprovalDraft,
}: PageProps) {
  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>Approvals</h3>
            <p className="subtle-text">Review pending AI-generated outreach before it goes out.</p>
          </div>
        </div>
        {loading ? (
          <p className="modal-copy">Loading approvals...</p>
        ) : data.approvals.length === 0 ? (
          <p className="modal-copy">No approvals waiting right now.</p>
        ) : (
          <div className="agent-activity-list">
            {data.approvals.map((approval) => (
              <div key={approval.id} className="agent-activity-item">
                <div className="swarm-feed-row">
                  <strong>{approval.contact_name}</strong>
                  <span className={`history-pill ${getRunStatusClass(approval.status)}`}>{approval.status}</span>
                </div>
                <span>{approval.subject}</span>
                {approval.sms_body ? (
                  <small className="truncate-line" title={approval.sms_body}>SMS: {approval.sms_body}</small>
                ) : null}
                <small>{formatDateTime(approval.created_at)}</small>
                <div className="action-row">
                  <button className="text-button" onClick={() => onViewApprovalDraft(approval)} type="button">
                    Review Draft
                  </button>
                  {approval.status === "pending" ? (
                    <>
                      <button
                        className="text-button approve-button"
                        disabled={approvalSubmittingId === approval.id}
                        onClick={() => void onApprove(approval.id)}
                        type="button"
                      >
                        {approvalSubmittingId === approval.id ? "Working..." : "Approve"}
                      </button>
                      <button
                        className="text-button approve-button"
                        disabled={approvalSubmittingId === approval.id || !approval.sms_body}
                        onClick={() => void onApproveAndSendSms(approval)}
                        type="button"
                      >
                        {approvalSubmittingId === approval.id ? "Working..." : "Approve + Send SMS"}
                      </button>
                      <button
                        className="text-button danger"
                        disabled={approvalSubmittingId === approval.id}
                        onClick={() => void onReject(approval.id)}
                        type="button"
                      >
                        Reject
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

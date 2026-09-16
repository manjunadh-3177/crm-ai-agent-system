import type { DataState } from "../types/appState";
import { formatExecutionStatus, formatDateTime } from "../lib/formatters";

export function ApprovalHistoryPage({
  data,
  loading,
  approvalSubmittingId,
  onRetryApprovalSend,
  onCancelApprovalSend,
}: {
  data: DataState;
  loading: boolean;
  approvalSubmittingId: string | null;
  onRetryApprovalSend: (approvalId: string) => Promise<void>;
  onCancelApprovalSend: (approvalId: string) => Promise<void>;
}) {
  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <h3>📜 Approval History</h3>
          <p className="subtle-text">Review previously decided AI actions and their delivery status.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Contact</th>
                <th>Email</th>
                <th>Subject</th>
                <th>Execution Result</th>
                <th>Actions</th>
                <th>Decided</th>
                <th>Executed</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={8}>
                    Loading history...
                  </td>
                </tr>
              ) : data.approvalHistory.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={8}>
                    No approval history yet.
                  </td>
                </tr>
              ) : (
                data.approvalHistory.map((approval) => {
                  const contact = data.contacts.find((c) => c.id === approval.contact_id);
                  const canRetry = approval.status === "approved" && approval.execution_status !== "sent";
                  const canCancel = approval.status === "approved" && (!approval.execution_status || ["queued", "sending"].includes(approval.execution_status));
                  return (
                    <tr key={approval.id}>
                      <td>
                        <span className={`history-pill ${approval.status}`}>
                          {approval.status}
                        </span>
                      </td>
                      <td>{approval.contact_name}</td>
                      <td>{contact?.email || "-"}</td>
                      <td>{approval.subject}</td>
                      <td>
                        {approval.execution_status ? (
                          <div className="history-detail">
                            <strong>{formatExecutionStatus(approval.execution_status)}</strong>
                            {approval.execution_detail?.includes("redirected inbox") && (
                              <span className="pill pill-warning" style={{ fontSize: '0.7rem', padding: '1px 4px', marginBottom: '2px', display: 'inline-block' }}>
                                Redirected Inbox
                              </span>
                            )}
                            {approval.execution_detail && <span>{approval.execution_detail}</span>}
                            {approval.provider_message_id && <span>ID: {approval.provider_message_id}</span>}
                          </div>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>
                        <div className="action-row compact-actions">
                          {canRetry ? (
                            <button
                              className="text-button"
                              disabled={approvalSubmittingId === approval.id}
                              onClick={() => void onRetryApprovalSend(approval.id)}
                              type="button"
                            >
                              Retry Send
                            </button>
                          ) : null}
                          {canCancel ? (
                            <button
                              className="text-button danger"
                              disabled={approvalSubmittingId === approval.id}
                              onClick={() => void onCancelApprovalSend(approval.id)}
                              type="button"
                            >
                              Cancel Queue
                            </button>
                          ) : null}
                        </div>
                      </td>
                      <td>{approval.decided_at ? formatDateTime(approval.decided_at) : "-"}</td>
                      <td>{approval.executed_at ? formatDateTime(approval.executed_at) : "-"}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

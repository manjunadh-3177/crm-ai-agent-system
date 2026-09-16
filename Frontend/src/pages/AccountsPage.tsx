import type { Note, ResearchInsight } from "../lib/api";
import { NoteSection } from "../components/NoteList";
import { formatDateTime, formatCurrency, formatDate, formatRoleLabel, parseResearchInsightNote } from "../lib/formatters";
import type { PageProps } from "../types/appState";

export function AccountsPage({
  data,
  loading,
  accountDetail,
  accountDetailLoading,
  selectedAccountId,
  onSelectAccount,
  onCreateNote,
  onDeleteNote,
  accountResearch,
  accountResearchLoading,
  onAccountResearch,
}: PageProps) {
  const latestSavedAccountResearch = accountDetail
    ? data.activityFeed
        .filter((item) => item.type === "note" && item.entity_type === "account" && item.entity_id === accountDetail.id)
        .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
        .map((item) => parseResearchInsightNote(item.description))
        .find((item): item is ResearchInsight => Boolean(item)) ?? null
    : null;
  const visibleAccountResearch = accountResearch?.status === "completed" ? accountResearch : latestSavedAccountResearch;
  const accountResearchMessage =
    accountResearch?.status === "queued"
      ? "Research refresh queued. Showing the latest saved insight below."
      : accountResearch?.status === "skipped"
        ? (latestSavedAccountResearch ? "No new insight was generated. Showing the latest saved insight below." : accountResearch.reason)
        : accountResearch?.status === "error" && latestSavedAccountResearch
          ? "Latest saved insight is shown below."
          : null;

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <h3>Accounts</h3>
          <p className="subtle-text">Open an account to see a full 360-degree B2B workspace.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Website</th>
                <th>Industry</th>
                <th>Created</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={5}>
                    Loading accounts...
                  </td>
                </tr>
              ) : data.accounts.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={5}>
                    No accounts found.
                  </td>
                </tr>
              ) : (
                data.accounts.map((account) => (
                  <tr key={account.id}>
                    <td>{account.name}</td>
                    <td>{account.domain ?? "-"}</td>
                    <td>{account.industry ?? "-"}</td>
                    <td>{formatDateTime(account.created_at)}</td>
                    <td>
                      <button className="text-button" onClick={() => onSelectAccount(account.id)} type="button">
                        {selectedAccountId === account.id ? "Selected" : "🔍 Open"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>Account 360</h3>
            <p className="subtle-text">
              {accountDetail ? accountDetail.name : "Select an account from the list above."}
            </p>
          </div>
        </div>

        {selectedAccountId === null ? (
          <p className="modal-copy">Choose an account to load the full B2B workspace view.</p>
        ) : accountDetailLoading ? (
          <p className="modal-copy">Loading account details...</p>
        ) : accountDetail ? (
          <div className="stack">
            <div className="detail-grid account-overview-grid">
              <div className="agent-activity-item">
                <strong>Company</strong>
                <span>{accountDetail.name}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Website</strong>
                <span>{accountDetail.website ?? "-"}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Industry</strong>
                <span>{accountDetail.industry ?? "-"}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Size</strong>
                <span>{accountDetail.size ?? "-"}</span>
              </div>
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>Research Insights</h3>
                <button
                  className="text-button"
                  onClick={() => void onAccountResearch(accountDetail.id)}
                  disabled={accountResearchLoading === accountDetail.id}
                  type="button"
                >
                  {accountResearchLoading === accountDetail.id ? "🧠 Analyzing..." : "🧠 Refresh Research"}
                </button>
              </div>

              {accountResearchMessage ? <p className="modal-copy">{accountResearchMessage}</p> : null}

              {visibleAccountResearch ? (
                <div className="research-card">
                  <div className="research-main">
                    <p className="research-summary">{visibleAccountResearch.research_summary}</p>
                    <div className="research-grid">
                      <div className="research-item">
                        <strong>Industry</strong>
                        <span>{visibleAccountResearch.industry}</span>
                      </div>
                      <div className="research-item">
                        <strong>Estimated Size</strong>
                        <span>{visibleAccountResearch.company_size_guess}</span>
                      </div>
                      <div className="research-item">
                        <strong>Confidence</strong>
                        <span>{visibleAccountResearch.confidence_score}%</span>
                      </div>
                    </div>
                  </div>
                  <div className="research-angle">
                    <strong>Recommended Outreach Angle</strong>
                    <p>{visibleAccountResearch.outreach_angle}</p>
                  </div>
                </div>
              ) : accountResearch && accountResearch.status === "error" ? (
                <p className="error-pill">{accountResearch.reason}</p>
              ) : (
                <p className="modal-copy">Click <strong>Refresh Research</strong> to generate AI-powered company insights.</p>
              )}
            </div>


            <div className="timeline-section">
              <div className="form-header">
                <h3>Contacts</h3>
              </div>
              {accountDetail.contacts.length === 0 ? (
                <p className="modal-copy">No related contacts yet.</p>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Phone</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accountDetail.contacts.map((contact) => (
                        <tr key={contact.id}>
                          <td>{contact.first_name} {contact.last_name}</td>
                          <td>{contact.email}</td>
                          <td>{contact.phone ?? "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>Deals</h3>
              </div>
              <div className="account-deals-grid">
                <div className="agent-activity-item">
                  <strong>Open Deals</strong>
                  {accountDetail.open_deals.length === 0 ? (
                    <small>No open deals.</small>
                  ) : (
                    <div className="account-list">
                      {accountDetail.open_deals.map((deal) => (
                        <div key={deal.id} className="account-list-item">
                          <strong>{deal.name}</strong>
                          <span>{deal.stage}</span>
                          <small>
                            {formatCurrency(deal.amount, "USD")} | {deal.probability ?? "-"}% |{" "}
                            {deal.expected_close_date ? formatDate(deal.expected_close_date) : "No close date"}
                          </small>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="agent-activity-item">
                  <strong>Closed Deals</strong>
                  {accountDetail.closed_deals.length === 0 ? (
                    <small>No closed deals.</small>
                  ) : (
                    <div className="account-list">
                      {accountDetail.closed_deals.map((deal) => (
                        <div key={deal.id} className="account-list-item">
                          <strong>{deal.name}</strong>
                          <span>{deal.stage}</span>
                          <small>
                            {formatCurrency(deal.amount, "USD")} | Updated {formatDateTime(deal.updated_at)}
                          </small>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>Stakeholders</h3>
              </div>
              {accountDetail.stakeholders.length === 0 ? (
                <p className="modal-copy">No stakeholders linked to this account yet.</p>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Deal</th>
                        <th>Contact</th>
                        <th>Role</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accountDetail.stakeholders.map((stakeholder, index) => (
                        <tr key={`${stakeholder.deal_name}-${stakeholder.contact_name}-${stakeholder.role}-${index}`}>
                          <td>{stakeholder.deal_name}</td>
                          <td>{stakeholder.contact_name}</td>
                          <td>{formatRoleLabel(stakeholder.role)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>Linked Tasks</h3>
              </div>
              {data.tasks.filter(t => t.account_id === accountDetail.id).length === 0 ? (
                <p className="modal-copy">No tasks linked to this account.</p>
              ) : (
                <div className="agent-activity-list">
                  {data.tasks.filter(t => t.account_id === accountDetail.id).map(task => (
                    <div key={task.id} className="agent-activity-item">
                      <div className="meeting-row-header">
                        <strong>{task.title}</strong>
                        <span className={`status-pill ${task.status}`}>{task.status}</span>
                      </div>
                      {task.due_at && <span>Due: {formatDateTime(task.due_at)}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <NoteSection
              entityType="account"
              entityId={accountDetail.id}
              notes={data.activityFeed.filter(item => item.type === "note").map(item => ({
                id: item.id,
                team_id: data.me?.team_id || "",
                body: item.description,
                entity_type: item.entity_type || "",
                entity_id: item.entity_id || "",
                created_by_user_id: item.actor_id,
                created_at: item.time,
                updated_at: item.time
              })) as Note[]}
              onCreateNote={onCreateNote}
              onDeleteNote={onDeleteNote}
            />

            <div className="agent-activity-item">
              <strong>Recent Activity</strong>
              <span>
                {accountDetail.activity_summary.last_activity_at
                  ? formatDateTime(accountDetail.activity_summary.last_activity_at)
                  : "-"}
              </span>
            </div>
          </div>
        ) : (
          <p className="modal-copy">Unable to load this account.</p>
        )}
      </div>
    </section>
  );
}

import { useMemo } from "react";

import type { DealStakeholder, Note } from "../lib/api";
import { NoteSection } from "../components/NoteList";
import { EmailHistory } from "../components/EmailHistory";
import { normalizeStageName, formatCurrency, formatRoleLabel, formatDateTime } from "../lib/formatters";
import { STAKEHOLDER_ROLE_OPTIONS } from "../types/appState";
import type { PageProps } from "../types/appState";

export function DealsPage({
  data,
  loading,
  dealForm,
  lineItemForm,
  dealSubmitting,
  lineItemSubmitting,
  bulkSubmitting,
  onDealFormChange,
  onLineItemFormChange,
  onCreateDeal,
  onMoveDealStage,
  onBulkMoveDeals,
  onSelectDeal,
  onAddLineItem,
  onAddStakeholder,
  onUpdateLineItem,
  onUpdateStakeholder,
  onDeleteLineItem,
  onDeleteStakeholder,
  onGenerateProposal,
  onGenerateNurtureNow,
  onOpenScheduler,
  selectedDeal,
  stakeholderForm,
  selectedDealIds,
  onSelectedDealIdsChange,
  bulkStageId,
  onBulkStageIdChange,
  onStakeholderFormChange,
  dealTimeline,
  dealTimelineLoading,
  lineItemUpdatingId,
  stakeholderUpdatingId,
  lineItemDrafts,
  onLineItemDraftChange,
  stakeholderSubmitting,
  onCreateNote,
  onDeleteNote,
  nurtureStatus,
}: PageProps) {
  const selectedDealTotal = selectedDeal
    ? selectedDeal.line_items.reduce((sum, item) => sum + Number(item.subtotal), 0)
    : 0;
  const uniqueStages = useMemo(() => {
    const seen = new Set<string>();
    return data.stages.filter((stage) => {
      const key = normalizeStageName(stage.name);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [data.stages]);
  const selectedDealHasPendingNurture = selectedDeal
    ? nurtureStatus.pending_deal_ids.includes(selectedDeal.id)
    : false;
  const availableStakeholderContacts = selectedDeal
    ? data.contacts.filter(
      (contact) => !selectedDeal.stakeholders.some((stakeholder) => stakeholder.contact_id === contact.id),
    )
    : [];

  return (
    <section className="stack">
      <form className="panel-card form-card" onSubmit={onCreateDeal}>
        <div className="form-header">
          <h3>💼 New Deal</h3>
        </div>
        <div className="form-grid">
          <label>
            Deal Name
            <input
              required
              value={dealForm.name}
              onChange={(event) => onDealFormChange((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label>
            Amount
            <input
              min="0"
              step="0.01"
              type="number"
              value={dealForm.amount}
              onChange={(event) => onDealFormChange((current) => ({ ...current, amount: event.target.value }))}
            />
          </label>
          <label>
            Currency
            <input
              maxLength={3}
              value={dealForm.currency}
              onChange={(event) => onDealFormChange((current) => ({ ...current, currency: event.target.value }))}
            />
          </label>
          <label>
            Probability
            <input
              max="100"
              min="0"
              type="number"
              value={dealForm.probability}
              onChange={(event) =>
                onDealFormChange((current) => ({ ...current, probability: event.target.value }))
              }
            />
          </label>
          <label>
            Expected Close Date
            <input
              type="date"
              value={dealForm.expected_close_date}
              onChange={(event) =>
                onDealFormChange((current) => ({ ...current, expected_close_date: event.target.value }))
              }
            />
          </label>
          <label>
            Stage
            <select
              required
              value={dealForm.stage_id}
              onChange={(event) => onDealFormChange((current) => ({ ...current, stage_id: event.target.value }))}
            >
              <option value="">Select stage</option>
              {uniqueStages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {stage.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Contact
            <select
              value={dealForm.contact_id}
              onChange={(event) => onDealFormChange((current) => ({ ...current, contact_id: event.target.value }))}
            >
              <option value="">No contact</option>
              {data.contacts.map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {contact.first_name} {contact.last_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Account
            <select
              value={dealForm.account_id}
              onChange={(event) => onDealFormChange((current) => ({ ...current, account_id: event.target.value }))}
            >
              <option value="">No account</option>
              {data.accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-actions">
          <button className="primary-button" disabled={dealSubmitting} type="submit">
            {dealSubmitting ? "💾 Saving..." : "💼 Add Deal"}
          </button>
        </div>
      </form>

      <div className="panel-card">
        <div className="form-header bulk-toolbar">
          <div>
            <h3>💼 Deals</h3>
            <p className="subtle-text">{selectedDealIds.length} selected</p>
          </div>
          <div className="bulk-actions-row">
            <select value={bulkStageId} onChange={(event) => onBulkStageIdChange(event.target.value)}>
              <option value="">Move selected to...</option>
              {uniqueStages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {stage.name}
                </option>
              ))}
            </select>
            <button
              className="text-button"
              disabled={selectedDealIds.length === 0 || !bulkStageId || bulkSubmitting === "deals"}
              onClick={() => void onBulkMoveDeals()}
              type="button"
            >
              {bulkSubmitting === "deals" ? "📈 Updating..." : "📈 Bulk Move"}
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    checked={data.deals.length > 0 && selectedDealIds.length === data.deals.length}
                    onChange={(event) =>
                      onSelectedDealIdsChange(event.target.checked ? data.deals.map((deal) => deal.id) : [])
                    }
                    type="checkbox"
                  />
                </th>
                <th>Health</th>
                <th>Deal Name</th>
                <th>Amount</th>
                <th>Stage</th>
                <th>Owner</th>
                <th>Line Items</th>
                <th>Move Stage</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={8}>
                    Loading deals...
                  </td>
                </tr>
              ) : data.deals.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={8}>
                    No deals found.
                  </td>
                </tr>
              ) : (
                data.deals.map((deal) => (
                  <tr key={deal.id}>
                    <td>
                      <input
                        checked={selectedDealIds.includes(deal.id)}
                        onChange={(event) =>
                          onSelectedDealIdsChange((current) =>
                            event.target.checked
                              ? [...current, deal.id]
                              : current.filter((id) => id !== deal.id),
                          )
                        }
                        type="checkbox"
                      />
                    </td>
                    <td>
                      <span className={`status-pill ${deal.deal_health}`}>{deal.deal_health}</span>
                    </td>
                    <td>{deal.name}</td>
                    <td>{formatCurrency(deal.amount, deal.currency)}</td>
                    <td>{deal.stage.name}</td>
                    <td>{deal.owner?.full_name ?? "-"}</td>
                    <td>{deal.line_items.length}</td>
                    <td>
                      <select
                        value={deal.stage_id}
                        onChange={(event) => void onMoveDealStage(deal.id, event.target.value)}
                      >
                        {uniqueStages.map((stage) => (
                          <option key={stage.id} value={stage.id}>
                            {stage.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button className="text-button" onClick={() => onSelectDeal(deal.id)} type="button">
                        {selectedDeal?.id === deal.id ? "Selected" : "🔍 Open"}
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
                <h3>💼 Deal Detail</h3>
            <p className="subtle-text">
              {selectedDeal
                ? `${selectedDeal.name} | ${selectedDeal.account?.name ?? selectedDeal.contact?.email ?? "Direct deal"}`
                : "Select a deal to manage stakeholders, line items, and proposals."}
              </p>
          </div>
          {selectedDeal ? (
            <div className="action-row">
              {selectedDealHasPendingNurture ? (
                <span className="status-pill warm">Nurture Suggested</span>
              ) : null}
              <button
                className="text-button"
                onClick={() =>
                  onOpenScheduler({
                    contactId: selectedDeal.contact_id,
                    dealId: selectedDeal.id,
                    accountId: selectedDeal.account_id,
                    label: selectedDeal.name,
                  })
                }
                type="button"
              >
                🤝 Schedule Meeting
              </button>
              <button
                className="text-button"
                onClick={() => void onGenerateNurtureNow({ dealId: selectedDeal.id })}
                type="button"
              >
                🤖 Generate Follow-up Now
              </button>
              <button className="primary-button" onClick={() => void onGenerateProposal()} type="button">
                📄 Generate Proposal
              </button>
            </div>
          ) : null}
        </div>

        {selectedDeal ? (
          <div className="stack">
            <div className="detail-grid">
              <div className="agent-activity-item">
                <strong>Current Amount</strong>
                <span>{formatCurrency(selectedDeal.amount, selectedDeal.currency)}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Line Item Total</strong>
                <span>{formatCurrency(selectedDealTotal, selectedDeal.currency)}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Contact</strong>
                <span>
                  {selectedDeal.contact
                    ? `${selectedDeal.contact.first_name} ${selectedDeal.contact.last_name}`
                    : "-"}
                </span>
              </div>
              <div className="agent-activity-item">
                <strong>Account</strong>
                <span>{selectedDeal.account?.name ?? "-"}</span>
              </div>
              <div className="agent-activity-item" style={{ gridColumn: "1 / -1", background: "rgba(255, 255, 255, 0.5)", border: "1px dashed #9bd3c9" }}>
                <strong>Deal Orchestrator (Health)</strong>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "8px" }}>
                  <span className={`status-pill ${selectedDeal.deal_health}`}>{selectedDeal.deal_health}</span>
                  <span style={{ fontSize: "0.9rem", fontWeight: "600", color: "#475569" }}>{selectedDeal.deal_reason}</span>
                </div>
                <div style={{ marginTop: "12px", padding: "8px", background: "rgba(155, 211, 201, 0.1)", borderRadius: "6px", fontSize: "0.85rem" }}>
                  <strong>Recommended:</strong> {selectedDeal.deal_health === "healthy" ? "Keep momentum." : selectedDeal.deal_health === "at_risk" ? "Send a check-in email." : "High priority follow-up needed."}
                </div>
              </div>
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>👥 Stakeholders</h3>
                <p className="subtle-text">Contacts attached to this account-linked deal.</p>
              </div>
              {selectedDeal.account_id ? (
                <>
                  <form className="form-grid compact-form" onSubmit={onAddStakeholder}>
                    <label>
                      Contact
                      <select
                        required
                        value={stakeholderForm.contact_id}
                        onChange={(event) =>
                          onStakeholderFormChange((current) => ({ ...current, contact_id: event.target.value }))
                        }
                      >
                        <option value="">Select contact</option>
                        {availableStakeholderContacts.map((contact) => (
                          <option key={contact.id} value={contact.id}>
                            {contact.first_name} {contact.last_name} ({contact.email})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Role
                      <select
                        value={stakeholderForm.role}
                        onChange={(event) =>
                          onStakeholderFormChange((current) => ({
                            ...current,
                            role: event.target.value as DealStakeholder["role"],
                          }))
                        }
                      >
                        {STAKEHOLDER_ROLE_OPTIONS.map((role) => (
                          <option key={role} value={role}>
                            {formatRoleLabel(role)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="form-actions inline-actions">
                      <button
                        className="primary-button"
                        disabled={!stakeholderForm.contact_id || stakeholderSubmitting}
                        type="submit"
                      >
                        {stakeholderSubmitting ? "➕ Adding..." : "➕ Add Stakeholder"}
                      </button>
                    </div>
                  </form>

                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Contact Name</th>
                          <th>Email</th>
                          <th>Role</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedDeal.stakeholders.length === 0 ? (
                          <tr>
                            <td className="empty-cell" colSpan={4}>
                              No stakeholders yet.
                            </td>
                          </tr>
                        ) : (
                          selectedDeal.stakeholders.map((stakeholder) => (
                            <tr key={stakeholder.id}>
                              <td>
                                {stakeholder.contact.first_name} {stakeholder.contact.last_name}
                              </td>
                              <td>{stakeholder.contact.email}</td>
                              <td>
                                <select
                                  value={stakeholder.role}
                                  onChange={(event) =>
                                    void onUpdateStakeholder(
                                      stakeholder,
                                      event.target.value as DealStakeholder["role"],
                                    )
                                  }
                                >
                                  {STAKEHOLDER_ROLE_OPTIONS.map((role) => (
                                    <option key={role} value={role}>
                                      {formatRoleLabel(role)}
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td>
                                <button
                                  className="text-button danger"
                                  onClick={() => void onDeleteStakeholder(stakeholder.id)}
                                  type="button"
                                >
                                  {stakeholderUpdatingId === stakeholder.id ? "Working..." : "🗑️ Remove"}
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="modal-copy">Stakeholders are available for account-linked deals only.</p>
              )}
            </div>

            <form className="form-grid compact-form" onSubmit={onAddLineItem}>
              <label>
                Product
                <select
                  required
                  value={lineItemForm.product_id}
                  onChange={(event) =>
                    onLineItemFormChange((current) => ({ ...current, product_id: event.target.value }))
                  }
                >
                  <option value="">Select product</option>
                  {data.products
                    .filter((product) => product.currency === selectedDeal.currency)
                    .map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.sku})
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Quantity
                <input
                  min="0"
                  step="0.01"
                  type="number"
                  value={lineItemForm.quantity}
                  onChange={(event) =>
                    onLineItemFormChange((current) => ({ ...current, quantity: event.target.value }))
                  }
                />
              </label>
              <label>
                Unit Price Override
                <input
                  min="0"
                  step="0.01"
                  type="number"
                  value={lineItemForm.unit_price}
                  onChange={(event) =>
                    onLineItemFormChange((current) => ({ ...current, unit_price: event.target.value }))
                  }
                />
              </label>
              <div className="form-actions inline-actions">
                <button className="primary-button" disabled={lineItemSubmitting} type="submit">
                  {lineItemSubmitting ? "➕ Adding..." : "➕ Add Product"}
                </button>
              </div>
            </form>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Subtotal</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedDeal.line_items.length === 0 ? (
                    <tr>
                      <td className="empty-cell" colSpan={5}>
                        No line items yet.
                      </td>
                    </tr>
                  ) : (
                    selectedDeal.line_items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          {item.product.name}
                          <div className="subtle-text">{item.product.sku}</div>
                        </td>
                        <td>
                          <input
                            className="table-input"
                            min="0"
                            step="0.01"
                            type="number"
                            value={lineItemDrafts[item.id]?.quantity ?? String(item.quantity)}
                            onChange={(event) =>
                              onLineItemDraftChange((current) => ({
                                ...current,
                                [item.id]: {
                                  quantity: event.target.value,
                                  unit_price: current[item.id]?.unit_price ?? String(item.unit_price),
                                },
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            className="table-input"
                            min="0"
                            step="0.01"
                            type="number"
                            value={lineItemDrafts[item.id]?.unit_price ?? String(item.unit_price)}
                            onChange={(event) =>
                              onLineItemDraftChange((current) => ({
                                ...current,
                                [item.id]: {
                                  quantity: current[item.id]?.quantity ?? String(item.quantity),
                                  unit_price: event.target.value,
                                },
                              }))
                            }
                          />
                        </td>
                        <td>{formatCurrency(item.subtotal, item.currency)}</td>
                        <td>
                          <div className="action-row">
                            <button
                              className="text-button"
                              onClick={() => void onUpdateLineItem(item)}
                              type="button"
                            >
                              {lineItemUpdatingId === item.id ? "💾 Saving..." : "💾 Save"}
                            </button>
                            <button
                              className="text-button danger"
                              onClick={() => void onDeleteLineItem(item.id)}
                              type="button"
                            >
                              {lineItemUpdatingId === item.id ? "Working..." : "🗑️ Remove"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>Linked Tasks</h3>
              </div>
              {data.tasks.filter(t => t.deal_id === selectedDeal.id).length === 0 ? (
                <p className="modal-copy">No tasks linked to this deal.</p>
              ) : (
                <div className="agent-activity-list">
                  {data.tasks.filter(t => t.deal_id === selectedDeal.id).map(task => (
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
              entityType="deal"
              entityId={selectedDeal.id}
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

            <div className="timeline-section">
              <div className="form-header">
                <h3>📧 Email Timeline</h3>
              </div>
              <EmailHistory emails={data.emails.filter(e => e.deal_id === selectedDeal.id)} />
            </div>

            <div className="timeline-section">
              <div className="form-header">
                <h3>⚡ Timeline</h3>
                <p className="subtle-text">Newest deal activity first.</p>
              </div>
              <div className="agent-activity-list">
                {dealTimelineLoading ? (
                  <p className="modal-copy">Loading timeline...</p>
                ) : dealTimeline.length === 0 ? (
                  <p className="modal-copy">No timeline activity yet.</p>
                ) : (
                  dealTimeline.map((item) => (
                    <div key={item.id} className="agent-activity-item">
                      <strong>{item.type}</strong>
                      <span>{formatDateTime(item.time)}</span>
                      <small>{item.description}</small>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="modal-copy">Pick a deal from the table above to manage stakeholders, products, totals, and proposals.</p>
        )}
      </div>
    </section>
  );
}

import type { PageProps } from "../types/appState";

export function ContactsPage({
  data,
  loading,
  contactForm,
  contactSubmitting,
  bulkSubmitting,
  onContactFormChange,
  onCreateContact,
  onDeleteContact,
  onBulkDeleteContacts,
  onLoadLeadSummary,
  onLoadEmailDraft,
  onRunAllContactAgents,
  onOpenScheduler,
  summaryLoadingId,
  draftLoadingId,
  runningContactAgentId,
  linkedDealsByContact,
  selectedContactIds,
  onSelectedContactIdsChange,
  nurtureStatus,
}: PageProps) {
  const hasPendingNurtureForContact = (contactId: string) =>
    nurtureStatus.pending_contact_ids.includes(contactId);

  return (
    <section className="stack">
      <form className="panel-card form-card" onSubmit={onCreateContact}>
        <div className="form-header">
          <h3>New Contact</h3>
        </div>
        <div className="form-grid">
          <label>
            First Name
            <input
              required
              value={contactForm.first_name}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, first_name: event.target.value }))
              }
            />
          </label>
          <label>
            Last Name
            <input
              required
              value={contactForm.last_name}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, last_name: event.target.value }))
              }
            />
          </label>
          <label>
            Email
            <input
              required
              type="email"
              value={contactForm.email}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>
          <label>
            Phone
            <input
              value={contactForm.phone}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, phone: event.target.value }))
              }
            />
          </label>
          <label className="checkbox-field">
            <input
              checked={contactForm.consent_sms}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, consent_sms: event.target.checked }))
              }
              type="checkbox"
            />
            Consent SMS
          </label>
          <label className="checkbox-field">
            <input
              checked={contactForm.consent_email}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, consent_email: event.target.checked }))
              }
              type="checkbox"
            />
            Consent Email
          </label>
          <label>
            Job Title
            <input
              value={contactForm.job_title}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, job_title: event.target.value }))
              }
            />
          </label>
          <label>
            Account
            <select
              value={contactForm.account_id}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, account_id: event.target.value }))
              }
            >
              <option value="">No Account</option>
              {data.accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>{acc.name}</option>
              ))}
            </select>
          </label>
          <label>
            Preferred Timezone
            <input
              placeholder="America/New_York"
              value={contactForm.preferred_timezone}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, preferred_timezone: event.target.value }))
              }
            />
          </label>
          <label>
            Working Days
            <input
              placeholder="Mon-Fri"
              value={contactForm.working_days}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, working_days: event.target.value }))
              }
            />
          </label>
          <label>
            Working Hours Start
            <input
              placeholder="09:00"
              value={contactForm.working_hours_start}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, working_hours_start: event.target.value }))
              }
            />
          </label>
          <label>
            Working Hours End
            <input
              placeholder="17:00"
              value={contactForm.working_hours_end}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, working_hours_end: event.target.value }))
              }
            />
          </label>
          <label>
            Preferred Meeting Windows
            <input
              placeholder="10:00-12:00; 14:00-16:00"
              value={contactForm.preferred_meeting_windows}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, preferred_meeting_windows: event.target.value }))
              }
            />
          </label>
          <label>
            Blocked Days
            <input
              placeholder="2026-05-01, Sun"
              value={contactForm.blocked_days}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, blocked_days: event.target.value }))
              }
            />
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            Description / Bio
            <textarea
              style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #cbd5e1" }}
              rows={3}
              value={contactForm.description}
              onChange={(event) =>
                onContactFormChange((current) => ({ ...current, description: event.target.value }))
              }
            />
          </label>
        </div>
        <div className="form-actions">
          <button className="primary-button" disabled={contactSubmitting} type="submit">
            {contactSubmitting ? "Saving..." : "Add Contact"}
          </button>
        </div>
      </form>

      <div className="panel-card">
        <div className="form-header bulk-toolbar">
          <div>
            <h3>Contacts</h3>
            <p className="subtle-text">{selectedContactIds.length} selected</p>
          </div>
          <button
            className="text-button danger"
            disabled={selectedContactIds.length === 0 || bulkSubmitting === "contacts"}
            onClick={() => void onBulkDeleteContacts()}
            type="button"
          >
            {bulkSubmitting === "contacts" ? "Deleting..." : "Bulk Delete"}
          </button>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    checked={data.contacts.length > 0 && selectedContactIds.length === data.contacts.length}
                    onChange={(event) =>
                      onSelectedContactIdsChange(event.target.checked ? data.contacts.map((contact) => contact.id) : [])
                    }
                    type="checkbox"
                  />
                </th>
                <th>Tier</th>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Consent SMS</th>
                <th>Consent Email</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={7}>
                    Loading contacts...
                  </td>
                </tr>
              ) : data.contacts.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={7}>
                    No contacts found.
                  </td>
                </tr>
              ) : (
                data.contacts.map((contact) => {
                  const linkedDeal = linkedDealsByContact.get(contact.id);

                  return (
                    <tr key={contact.id}>
                      <td>
                        <input
                          checked={selectedContactIds.includes(contact.id)}
                          onChange={(event) =>
                            onSelectedContactIdsChange((current) =>
                              event.target.checked
                                ? [...current, contact.id]
                                : current.filter((id) => id !== contact.id),
                            )
                          }
                          type="checkbox"
                        />
                      </td>
                      <td>
                        <span className={`status-pill ${contact.lead_tier?.toLowerCase()}`}>{contact.lead_tier || "Unscored"}</span>
                      </td>
                      <td>
                        {contact.first_name} {contact.last_name}
                        {hasPendingNurtureForContact(contact.id) ? (
                          <div className="subtle-text">
                            <span className="status-pill warm">Nurture Suggested</span>
                          </div>
                        ) : null}
                        {linkedDeal ? <div className="subtle-text">Deal: {linkedDeal.name}</div> : null}
                      </td>
                      <td>{contact.email}</td>
                      <td>{contact.phone ?? "-"}</td>
                      <td>{contact.consent_sms ? "Yes" : "No"}</td>
                      <td>{contact.consent_email ? "Yes" : "No"}</td>
                      <td>
                        <div className="action-row contact-agent-actions">
                          <button
                            className="text-button agent-action-button"
                            onClick={() => void onLoadLeadSummary(contact)}
                            title="LeadQualifierAgent: show lead score, hot-warm-cold classification, and reasoning."
                            type="button"
                          >
                            {summaryLoadingId === contact.id ? "Analyzing..." : "LeadQualifierAgent"}
                          </button>
                          <button
                            className="text-button agent-action-button"
                            onClick={() => void onLoadEmailDraft(contact)}
                            title="NurturerAgent: generate an outreach draft approval item."
                            type="button"
                          >
                            {draftLoadingId === contact.id ? "Drafting..." : "NurturerAgent"}
                          </button>
                          <button
                            className="text-button agent-action-button"
                            onClick={() =>
                              onOpenScheduler({
                                contactId: contact.id,
                                accountId: contact.account_id,
                                dealId: linkedDeal?.id ?? null,
                                label: `${contact.first_name} ${contact.last_name}`,
                              })
                            }
                            title="SchedulerAgent: open mutual free slots and the booking modal."
                            type="button"
                          >
                            SchedulerAgent
                          </button>
                          <button
                            className="primary-button agent-action-button"
                            disabled={runningContactAgentId === contact.id}
                            onClick={() => void onRunAllContactAgents(contact)}
                            title="Run LeadQualifierAgent, NurturerAgent, and SchedulerAgent sequentially."
                            type="button"
                          >
                            {runningContactAgentId === contact.id ? "Running agents..." : "Run All Agents"}
                          </button>
                          <button
                            className="text-button danger"
                            onClick={() => void onDeleteContact(contact.id)}
                            type="button"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
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

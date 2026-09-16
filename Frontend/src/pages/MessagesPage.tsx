import { useState, type FormEvent } from "react";

import type { SMSMessage } from "../lib/api";
import { sendSms, markSmsRead, assignSmsContact, createSmsTask } from "../lib/api";
import type { PageProps } from "../types/appState";
import { findLatestSmsReadyApproval, formatDateTime } from "../lib/formatters";

export function MessagesPage(props: PageProps) {
  const { data, loading, onReloadData } = props;
  const [activeTab, setActiveTab] = useState<"inbox" | "sent" | "compose">("inbox");
  const [composeTo, setComposeTo] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeContactId, setComposeContactId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageNotice, setPageNotice] = useState<string | null>(null);

  const inboxMessages = data.smsMessages.filter((message) => message.direction === "inbound");
  const sentMessages = data.smsMessages.filter((message) => message.direction === "outbound");

  function peerNumberFor(message: SMSMessage) {
    return message.direction === "outbound" ? message.to_number : message.from_number;
  }

  function openReply(message: SMSMessage) {
    setActiveTab("compose");
    setComposeTo(peerNumberFor(message));
    setComposeBody("");
    setComposeContactId(message.contact_id ?? "");
  }

  function handleUseLatestDraftEmail() {
    const latestApproval = findLatestSmsReadyApproval(
      [...data.approvals, ...data.approvalHistory],
      data.contacts,
      composeContactId || undefined,
    );

    if (!latestApproval) {
      setPageError("No recent draft email with SMS-ready content was found.");
      return;
    }

    const contact = data.contacts.find((item) => item.id === latestApproval.contact_id);
    if (!contact?.phone) {
      setPageError("The latest draft contact does not have a phone number.");
      return;
    }

    setComposeContactId(contact.id);
    setComposeTo(contact.phone);
    setComposeBody(latestApproval.sms_body || "");
    setPageError(null);
    setPageNotice(`Loaded latest draft email content for ${latestApproval.contact_name}.`);
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setPageError(null);
    setPageNotice(null);
    try {
      const result = await sendSms({
        to_number: composeTo.trim(),
        body: composeBody.trim(),
        contact_id: composeContactId || undefined,
      });
      setComposeBody("");
      if (result.status === "Failed") {
        setPageError(result.error_detail || "SMS delivery failed.");
      } else {
        setPageNotice(result.status === "Sent" ? "SMS sent successfully." : "SMS queued for delivery.");
      }
      setActiveTab("sent");
      await onReloadData();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to send SMS.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMarkRead(messageId: string) {
    setPageError(null);
    try {
      await markSmsRead(messageId);
      await onReloadData();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to mark SMS as read.");
    }
  }

  async function handleAssignContact(messageId: string, contactId: string) {
    if (!contactId) return;
    setPageError(null);
    try {
      await assignSmsContact(messageId, contactId);
      await onReloadData();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to assign contact.");
    }
  }

  async function handleCreateTask(messageId: string) {
    setPageError(null);
    setPageNotice(null);
    try {
      await createSmsTask(messageId);
      setPageNotice("Task created from SMS.");
      await onReloadData();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to create task.");
    }
  }

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>Messages</h3>
            <p className="subtle-text">Twilio SMS inbox, sent history, and fast reply tools.</p>
          </div>
        </div>
        <div className="message-tabs">
          {(["inbox", "sent", "compose"] as const).map((tab) => (
            <button
              key={tab}
              className={`message-tab-button ${activeTab === tab ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
              type="button"
            >
              {tab === "inbox" ? "Inbox" : tab === "sent" ? "Sent" : "Compose"}
            </button>
          ))}
        </div>
        {pageError ? <p className="error-text">{pageError}</p> : null}
        {pageNotice ? <p className="success-text">{pageNotice}</p> : null}

        {activeTab === "compose" ? (
          <form className="stack" onSubmit={handleSend}>
            <div className="form-grid">
              <label>
                To Number
                <input value={composeTo} onChange={(event) => setComposeTo(event.target.value)} required />
              </label>
              <label>
                Contact
                <select value={composeContactId} onChange={(event) => setComposeContactId(event.target.value)}>
                  <option value="">Auto match by phone</option>
                  {data.contacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contact.first_name} {contact.last_name}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ gridColumn: "1 / -1" }}>
                Message
                <textarea rows={5} value={composeBody} onChange={(event) => setComposeBody(event.target.value)} required />
              </label>
            </div>
            <div className="form-actions">
              <button className="text-button" onClick={handleUseLatestDraftEmail} type="button">
                Use Latest Draft Email
              </button>
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting ? "Sending..." : "Send SMS"}
              </button>
            </div>
          </form>
        ) : (
          <div className="message-thread-list">
            {loading ? (
              <p className="modal-copy">Loading messages...</p>
            ) : (activeTab === "inbox" ? inboxMessages : sentMessages).length === 0 ? (
              <p className="modal-copy">No messages here yet.</p>
            ) : (
              (activeTab === "inbox" ? inboxMessages : sentMessages).map((message) => (
                <article key={message.id} className="message-card">
                  <div className="message-card-head">
                    <div>
                      <strong>{peerNumberFor(message)}</strong>
                      <p className="subtle-text">
                        {formatDateTime(message.received_at ?? message.sent_at ?? message.created_at)} · {message.thread_id}
                      </p>
                    </div>
                    <span className={`status-pill ${message.status === "Sent" ? "won" : message.status === "Failed" ? "lost" : "pending"}`}>
                      {message.status}
                    </span>
                  </div>
                  <p className="message-body-preview">{message.body}</p>
                  {message.error_detail ? (
                    <div className="message-suggestion">
                      <strong>Failure Reason</strong>
                      <span>{message.error_detail}</span>
                    </div>
                  ) : null}
                  {message.agent_suggestion ? (
                    <div className="message-suggestion">
                      <strong>Agent Suggestion</strong>
                      <span>{message.agent_suggestion}</span>
                    </div>
                  ) : null}
                  <div className="message-meta-row">
                    <span>{message.contact ? `${message.contact.first_name} ${message.contact.last_name}` : "Unassigned contact"}</span>
                    {message.provider_sid ? <span>Provider SID: {message.provider_sid}</span> : null}
                    {!message.is_read && activeTab === "inbox" ? <span className="history-pill pending">Unread</span> : null}
                  </div>
                  <div className="message-actions-row">
                    <button className="text-button" onClick={() => openReply(message)} type="button">
                      Reply
                    </button>
                    <select
                      value={message.contact_id ?? ""}
                      onChange={(event) => void handleAssignContact(message.id, event.target.value)}
                    >
                      <option value="">{message.contact_id ? "Assigned" : "Assign contact"}</option>
                      {data.contacts.map((contact) => (
                        <option key={contact.id} value={contact.id}>
                          {contact.first_name} {contact.last_name}
                        </option>
                      ))}
                    </select>
                    <button className="text-button" onClick={() => void handleCreateTask(message.id)} type="button">
                      Create task
                    </button>
                    {activeTab === "inbox" ? (
                      <button className="text-button" onClick={() => void handleMarkRead(message.id)} type="button">
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </article>
              ))
            )}
          </div>
        )}
      </div>
    </section>
  );
}

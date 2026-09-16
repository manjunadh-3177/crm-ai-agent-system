import type { Dispatch, FormEvent, SetStateAction } from "react";

import type { DataState, MeetingFormState } from "../types/appState";

type MeetingComposerModalProps = {
  open: boolean;
  selectedMeetingId: string | null;
  meetingForm: MeetingFormState;
  meetingSubmitting: boolean;
  data: DataState;
  onClose: () => void;
  onCreateMeeting: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onMeetingFormChange: Dispatch<SetStateAction<MeetingFormState>>;
};

export function MeetingComposerModal({
  open,
  selectedMeetingId,
  meetingForm,
  meetingSubmitting,
  data,
  onClose,
  onCreateMeeting,
  onMeetingFormChange,
}: MeetingComposerModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card meeting-modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>{selectedMeetingId ? "✏️ Edit Meeting" : "🤝 Schedule New Meeting"}</h3>
            <p className="subtle-text">Create or update a meeting without leaving the calendar.</p>
          </div>
          <button className="text-button" onClick={onClose} type="button">
            ❌ Close
          </button>
        </div>
        <form className="crm-form" onSubmit={onCreateMeeting}>
          <div className="form-grid">
            <div className="form-group">
              <label>Title</label>
              <input
                required
                value={meetingForm.title}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, title: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Type</label>
              <select
                value={meetingForm.meeting_type}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, meeting_type: event.target.value })}
              >
                <option value="call">Call</option>
                <option value="demo">Demo</option>
                <option value="followup">Follow-up</option>
                <option value="internal">Internal</option>
              </select>
            </div>
            <div className="form-group">
              <label>Starts At</label>
              <input
                required
                type="datetime-local"
                value={meetingForm.starts_at}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, starts_at: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Ends At</label>
              <input
                required
                type="datetime-local"
                value={meetingForm.ends_at}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, ends_at: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Location</label>
              <input
                value={meetingForm.location}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, location: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Reminder (mins)</label>
              <input
                type="number"
                value={meetingForm.reminder_minutes}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, reminder_minutes: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Link Contact</label>
              <select
                value={meetingForm.contact_id}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, contact_id: event.target.value })}
              >
                <option value="">None</option>
                {data.contacts.map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.first_name} {contact.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Link Deal</label>
              <select
                value={meetingForm.deal_id}
                onChange={(event) => onMeetingFormChange({ ...meetingForm, deal_id: event.target.value })}
              >
                <option value="">None</option>
                {data.deals.map((deal) => (
                  <option key={deal.id} value={deal.id}>
                    {deal.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group full-width">
            <label>Description</label>
            <textarea
              rows={3}
              value={meetingForm.description}
              onChange={(event) => onMeetingFormChange({ ...meetingForm, description: event.target.value })}
            />
          </div>
          <div className="form-actions">
            <button className="text-button" onClick={onClose} type="button">
              ❌ Cancel
            </button>
            <button className="primary-button" disabled={meetingSubmitting} type="submit">
              {meetingSubmitting ? "💾 Saving..." : selectedMeetingId ? "💾 Update Meeting" : "🤝 Schedule Meeting"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

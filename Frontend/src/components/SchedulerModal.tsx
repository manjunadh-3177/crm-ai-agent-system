import type { Dispatch, SetStateAction } from "react";

import type { SchedulerAvailabilitySummary, SchedulerSuggestedSlot } from "../lib/api";

type SchedulerModalProps = {
  open: boolean;
  loading: boolean;
  durationMinutes: string;
  suggestions: SchedulerSuggestedSlot[];
  yourAvailability: SchedulerAvailabilitySummary | null;
  customerAvailability: SchedulerAvailabilitySummary | null;
  message: string | null;
  targetLabel: string;
  bookingStart: string | null;
  selectedStart: string | null;
  onClose: () => void;
  onDurationChange: Dispatch<SetStateAction<string>>;
  onSelectSlot: Dispatch<SetStateAction<string | null>>;
  onSuggestSlots: () => void;
  onBookSlot: (slot: SchedulerSuggestedSlot) => Promise<void>;
};

export function SchedulerModal({
  open,
  loading,
  durationMinutes,
  suggestions,
  yourAvailability,
  customerAvailability,
  message,
  targetLabel,
  bookingStart,
  selectedStart,
  onClose,
  onDurationChange,
  onSelectSlot,
  onSuggestSlots,
  onBookSlot,
}: SchedulerModalProps) {
  if (!open) return null;
  const selectedSlot = suggestions.find((slot) => slot.starts_at === selectedStart) ?? null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card scheduler-modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Meeting Scheduler</h3>
            <p className="subtle-text">
              SchedulerAgent will match your free time with {targetLabel || "this record"} and show mutual windows only.
            </p>
          </div>
          <button className="text-button" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <div className="stack">
          <div className="scheduler-toolbar">
            <div>
              <strong>Meeting Length</strong>
              <p className="subtle-text">Searches the next 7 days for overlapping availability.</p>
            </div>
            <div className="filter-row">
              <select value={durationMinutes} onChange={(event) => onDurationChange(event.target.value)}>
                <option value="30">30 minutes</option>
                <option value="45">45 minutes</option>
                <option value="60">60 minutes</option>
              </select>
              <button className="primary-button" disabled={loading} onClick={onSuggestSlots} type="button">
                {loading ? "Finding Slots..." : "Find Mutual Slots"}
              </button>
            </div>
          </div>
          <div className="scheduler-sections">
            <section className="scheduler-section-card">
              <div className="scheduler-section-head">
                <span className="scheduler-section-kicker">Section A</span>
                <strong>My Availability</strong>
              </div>
              <p className="scheduler-availability-summary">
                {yourAvailability?.summary ?? "Your availability will appear after we run the match."}
              </p>
            </section>
            <section className="scheduler-section-card">
              <div className="scheduler-section-head">
                <span className="scheduler-section-kicker">Section B</span>
                <strong>Customer Availability</strong>
              </div>
              <p className="scheduler-availability-summary">
                {customerAvailability?.summary ?? "Customer preferences will appear here after matching."}
              </p>
            </section>
          </div>
          <div className="scheduler-section-card">
            <div className="scheduler-section-head">
              <span className="scheduler-section-kicker">Section C</span>
              <strong>Mutual Slots</strong>
            </div>
            <p className="subtle-text">{message ?? "Run the scheduler to see overlapping meeting times."}</p>
            <div className="scheduler-slot-list">
              {suggestions.length === 0 ? (
                <p className="subtle-text">No mutual slots yet. Generate slots to continue.</p>
              ) : (
                suggestions.map((slot) => (
                  <div
                    key={slot.starts_at}
                    className={`scheduler-slot-button ${selectedStart === slot.starts_at ? "selected" : ""}`}
                  >
                    <div className="scheduler-slot-grid">
                      <div>
                        <span className="scheduler-slot-label">Your Time</span>
                        <strong>{slot.your_time_label}</strong>
                        <span className="subtle-text">{slot.your_timezone}</span>
                      </div>
                      <div>
                        <span className="scheduler-slot-label">Customer Time</span>
                        <strong>{slot.customer_time_label}</strong>
                        <span className="subtle-text">{slot.customer_timezone}</span>
                      </div>
                      <div>
                        <span className="scheduler-slot-label">Duration</span>
                        <strong>{slot.duration_minutes} min</strong>
                        <span className="subtle-text">{slot.label}</span>
                      </div>
                    </div>
                    <button className="secondary-button" onClick={() => onSelectSlot(slot.starts_at)} type="button">
                      {selectedStart === slot.starts_at ? "Selected" : "Select Slot"}
                    </button>
                  </div>
                ))
              )}
            </div>
            <div className="form-actions scheduler-actions">
              <button
                className="primary-button"
                disabled={!selectedSlot || bookingStart === selectedSlot.starts_at}
                onClick={() => selectedSlot && void onBookSlot(selectedSlot)}
                type="button"
              >
                {selectedSlot && bookingStart === selectedSlot.starts_at ? "Sending Invite..." : "Send Invite"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

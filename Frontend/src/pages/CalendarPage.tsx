import { getMeetingIcsUrl } from "../lib/api";
import { getCalendarStart, isSameDay, getMeetingStatusClass, formatDateTime } from "../lib/formatters";
import type { PageProps } from "../types/appState";

export function CalendarPage(props: PageProps) {
  const {
    data,
    loading,
    onCompleteMeeting,
    onCancelMeeting,
    onDeleteMeeting,
    onEditMeeting,
    selectedMeetingId,
    onSelectMeeting,
    calendarMonth,
    onCalendarMonthChange,
    meetingFilters,
    onMeetingFiltersChange,
    onOpenMeetingComposerForDate,
  } = props;

  const filteredMeetings = data.meetings.filter((meeting) => {
    if (meetingFilters.status && meeting.status !== meetingFilters.status) return false;
    if (meetingFilters.type && meeting.meeting_type !== meetingFilters.type) return false;
    if (meetingFilters.date && !meeting.starts_at.startsWith(meetingFilters.date)) return false;
    return true;
  });
  const calendarStart = getCalendarStart(calendarMonth);
  const calendarDays = Array.from({ length: 42 }, (_, index) => {
    const day = new Date(calendarStart);
    day.setDate(calendarStart.getDate() + index);
    return day;
  });
  const selectedMeeting = data.meetings.find((meeting) => meeting.id === selectedMeetingId) ?? null;
  const monthMeetings = filteredMeetings.filter((meeting) => {
    const meetingDate = new Date(meeting.starts_at);
    return (
      meetingDate.getFullYear() === calendarMonth.getFullYear() &&
      meetingDate.getMonth() === calendarMonth.getMonth()
    );
  });

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header calendar-toolbar">
          <div>
            <h3>📅 Calendar Hub</h3>
            <p className="subtle-text">Visual team calendar with fast meeting booking.</p>
          </div>
          <div className="calendar-toolbar-actions">
            <button
              className="text-button"
              onClick={() =>
                onCalendarMonthChange((current) => new Date(current.getFullYear(), current.getMonth() - 1, 1))
              }
              type="button"
            >
              Prev
            </button>
            <button className="text-button" onClick={() => onCalendarMonthChange(new Date())} type="button">
              Today
            </button>
            <button
              className="text-button"
              onClick={() =>
                onCalendarMonthChange((current) => new Date(current.getFullYear(), current.getMonth() + 1, 1))
              }
              type="button"
            >
              Next
            </button>
            <button className="primary-button" onClick={() => onOpenMeetingComposerForDate(new Date())} type="button">
              🤝 New Meeting
            </button>
          </div>
        </div>
        <div className="calendar-summary-row">
          <div className="agent-activity-item current-month-summary">
            <strong>{calendarMonth.toLocaleString(undefined, { month: "long", year: "numeric" })}</strong>
            <span>{monthMeetings.length} meetings in view</span>
          </div>
          <div className="agent-activity-item">
            <strong>Scheduled</strong>
            <span>{monthMeetings.filter((meeting) => meeting.status === "scheduled").length}</span>
          </div>
          <div className="agent-activity-item">
            <strong>Filters</strong>
            <div className="filter-row compact-filter-row">
              <select
                value={meetingFilters.status}
                onChange={(event) => onMeetingFiltersChange({ ...meetingFilters, status: event.target.value })}
              >
                <option value="">All Statuses</option>
                <option value="scheduled">Scheduled</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <select
                value={meetingFilters.type}
                onChange={(event) => onMeetingFiltersChange({ ...meetingFilters, type: event.target.value })}
              >
                <option value="">All Types</option>
                <option value="call">Call</option>
                <option value="demo">Demo</option>
                <option value="followup">Follow-up</option>
                <option value="internal">Internal</option>
              </select>
              <input
                type="date"
                value={meetingFilters.date}
                onChange={(event) => onMeetingFiltersChange({ ...meetingFilters, date: event.target.value })}
              />
            </div>
          </div>
        </div>

        {loading ? (
          <p className="modal-copy">Loading calendar...</p>
        ) : (
          <div className="calendar-shell">
            <div className="calendar-main">
              <div className="calendar-grid calendar-grid-header">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label) => (
                  <div key={label} className="calendar-weekday">
                    {label}
                  </div>
                ))}
              </div>
              <div className="calendar-grid calendar-grid-body">
                {calendarDays.map((day) => {
                  const dayMeetings = filteredMeetings
                    .filter((meeting) => isSameDay(new Date(meeting.starts_at), day))
                    .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
                  const isCurrentMonth = day.getMonth() === calendarMonth.getMonth();
                  const isToday = isSameDay(day, new Date());

                  return (
                    <div
                      key={day.toISOString()}
                      className={`calendar-day-cell${isCurrentMonth ? " current-month" : " outside-month"}${isToday ? " today" : ""}`}
                      onClick={() => onOpenMeetingComposerForDate(day)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onOpenMeetingComposerForDate(day);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="calendar-day-header">
                        <span className="calendar-day-number">{day.getDate()}</span>
                      </div>
                      <div className="calendar-day-meetings">
                        {dayMeetings.length === 0 ? (
                          <span className="calendar-empty">No meetings</span>
                        ) : (
                          dayMeetings.map((meeting) => (
                            <button
                              key={meeting.id}
                              className={`calendar-meeting-chip ${getMeetingStatusClass(meeting.status)}${selectedMeetingId === meeting.id ? " active" : ""}`}
                              onClick={(event) => {
                                event.stopPropagation();
                                onSelectMeeting(meeting.id);
                              }}
                              type="button"
                            >
                              <span className="calendar-meeting-time">
                                {new Date(meeting.starts_at).toLocaleTimeString([], {
                                  hour: "numeric",
                                  minute: "2-digit",
                                })}
                              </span>
                              <span className="calendar-meeting-title">{meeting.title}</span>
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <aside className="calendar-detail-panel panel-card">
              {selectedMeeting ? (
                <div className="stack">
                  <div className="form-header">
                    <div>
                      <h3>{selectedMeeting.title}</h3>
                      <p className="subtle-text">
                        {formatDateTime(selectedMeeting.starts_at)} - {formatDateTime(selectedMeeting.ends_at)}
                      </p>
                    </div>
                    <span className={`status-pill ${selectedMeeting.status}`}>{selectedMeeting.status}</span>
                  </div>
                  <div className="detail-grid compact-detail-grid">
                    <div className="agent-activity-item">
                      <strong>Type</strong>
                      <span>{selectedMeeting.meeting_type}</span>
                    </div>
                    <div className="agent-activity-item">
                      <strong>Timezone</strong>
                      <span>{selectedMeeting.timezone}</span>
                    </div>
                    <div className="agent-activity-item">
                      <strong>Contact</strong>
                      <span>
                        {selectedMeeting.contact
                          ? `${selectedMeeting.contact.first_name} ${selectedMeeting.contact.last_name}`
                          : "-"}
                      </span>
                    </div>
                    <div className="agent-activity-item">
                      <strong>Deal</strong>
                      <span>{selectedMeeting.deal?.name ?? "-"}</span>
                    </div>
                    <div className="agent-activity-item">
                      <strong>Account</strong>
                      <span>{selectedMeeting.account?.name ?? "-"}</span>
                    </div>
                    <div className="agent-activity-item">
                      <strong>Location</strong>
                      <span>{selectedMeeting.location ?? "-"}</span>
                    </div>
                  </div>
                  {selectedMeeting.description ? (
                    <div className="agent-activity-item">
                      <strong>Description</strong>
                      <span>{selectedMeeting.description}</span>
                    </div>
                  ) : null}
                  <div className="action-row wrap-actions">
                    {selectedMeeting.status === "scheduled" ? (
                      <>
                        <button className="text-button" onClick={() => void onCompleteMeeting(selectedMeeting.id)} type="button">
                          ✅ Complete
                        </button>
                        <button className="text-button" onClick={() => void onCancelMeeting(selectedMeeting.id)} type="button">
                          ❌ Cancel
                        </button>
                      </>
                    ) : null}
                    <button className="text-button" onClick={() => onEditMeeting(selectedMeeting)} type="button">
                      ✏️ Edit
                    </button>
                    <button className="text-button danger-text" onClick={() => void onDeleteMeeting(selectedMeeting.id)} type="button">
                      🗑️ Delete
                    </button>
                    <a href={getMeetingIcsUrl(selectedMeeting.id)} className="text-button" download>
                      ICS
                    </a>
                  </div>
                </div>
              ) : (
                <div className="empty-calendar-detail">
                  <h3>Meeting Details</h3>
                  <p className="subtle-text">Click a meeting in the calendar to review or update it.</p>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </section>
  );
}

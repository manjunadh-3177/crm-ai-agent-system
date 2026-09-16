import type { PageProps } from "../types/appState";
import { getActivityColor, getActivityIcon, getRelativeTime } from "../lib/formatters";

export function NotificationsPage(props: PageProps) {
  const { data, loading, onMarkNotificationRead, onMarkAllNotificationsRead } = props;

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header bulk-toolbar">
          <div>
            <h3>🔔 Notification Center</h3>
            <p className="subtle-text">Alerts and tasks requiring your attention.</p>
          </div>
          <button
            className="text-button"
            onClick={() => void onMarkAllNotificationsRead()}
            disabled={loading || data.notifications.filter(n => !n.is_read).length === 0}
          >
            ✓ Mark all as read
          </button>
        </div>
        <div className="agent-activity-list" style={{ marginTop: "16px" }}>
          {loading ? (
            <p className="modal-copy">Loading notifications...</p>
          ) : data.notifications.length === 0 ? (
            <p className="modal-copy">You're all caught up! No notifications yet.</p>
          ) : (
            data.notifications.map((n) => (
              <div
                key={n.id}
                className="agent-activity-item"
                style={{
                  borderLeft: n.is_read ? "4px solid #cbd5e1" : `4px solid ${getActivityColor(n.type)}`,
                  opacity: n.is_read ? 0.7 : 1,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div className="meeting-row-header">
                    <strong>{getActivityIcon(n.type)} {n.title}</strong>
                    {!n.is_read && <span className="status-pill open" style={{ padding: "2px 6px", fontSize: "10px" }}>New</span>}
                  </div>
                  <span style={{ display: "block", margin: "4px 0" }}>{n.message}</span>
                  <small className="subtle-text">{getRelativeTime(n.created_at)}</small>
                </div>
                {!n.is_read && (
                  <button className="text-button" onClick={() => void onMarkNotificationRead(n.id)}>
                    Mark read
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

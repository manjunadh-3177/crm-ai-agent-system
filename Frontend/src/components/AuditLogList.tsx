import type { AuditLog } from "../lib/api";
import { formatActionLabel, formatDateTime } from "../lib/formatters";

export function AuditLogList({
  logs,
  loading,
  emptyText,
}: {
  logs: AuditLog[];
  loading: boolean;
  emptyText: string;
}) {
  if (loading && logs.length === 0) {
    return <p className="modal-copy">Loading logs...</p>;
  }

  if (logs.length === 0) {
    return <p className="modal-copy">{emptyText}</p>;
  }

  return (
    <div className="agent-activity-list run-log-list">
      {logs.map((log) => (
        <div key={log.id} className="agent-activity-item">
          <div className="swarm-feed-row">
            <strong>{formatActionLabel(log.action)}</strong>
            <span className="history-pill pending">{log.actor_type}</span>
          </div>
          <span>{log.entity_type}{log.entity_id ? ` / ${log.entity_id}` : ""}</span>
          <small>{formatDateTime(log.created_at)}</small>
        </div>
      ))}
    </div>
  );
}

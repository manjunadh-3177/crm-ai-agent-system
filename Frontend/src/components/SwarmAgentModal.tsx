import type { Dispatch, SetStateAction } from "react";

import type { AuditLog, SwarmAgentStatus, SwarmEvent, SwarmJobsResponse } from "../lib/api";
import {
  formatDateTime,
  formatJobLabel,
  getAgentStateProgress,
  getRunStatusClass,
  getStateStepClass,
  isJobRelatedToAgent,
  safeNumber,
} from "../lib/formatters";

export function SwarmAgentModal({
  agent,
  swarmEvents,
  swarmJobs,
  auditLogs,
  activeTab,
  running,
  onChangeTab,
  onClose,
  onRun,
}: {
  agent: SwarmAgentStatus;
  swarmEvents: SwarmEvent[];
  swarmJobs: SwarmJobsResponse | null;
  auditLogs: AuditLog[];
  activeTab: "live" | "history" | "metrics" | "logs";
  running: boolean;
  onChangeTab: Dispatch<SetStateAction<"live" | "history" | "metrics" | "logs">>;
  onClose: () => void;
  onRun: () => void;
}) {
  const normalizedAgentName = agent.name.toLowerCase();
  const relevantEvents = swarmEvents.filter((event) => {
    const haystack = `${event.source} ${event.type} ${event.message}`.toLowerCase();
    return haystack.includes(normalizedAgentName);
  });
  const relevantLogs = auditLogs.filter((log) => {
    const haystack = `${log.action} ${JSON.stringify(log.metadata_json ?? {})}`.toLowerCase();
    return haystack.includes(normalizedAgentName);
  });
  const relevantJobs = [
    ...(swarmJobs?.running_jobs ?? []),
    ...(swarmJobs?.queued_jobs ?? []),
    ...(swarmJobs?.completed_jobs ?? []).slice(0, 8),
  ].filter((job) => isJobRelatedToAgent(job, normalizedAgentName));
  const latestRun = agent.run_history[0] ?? null;
  const liveState = running ? "running" : latestRun?.status ?? agent.status;
  const stepState = getAgentStateProgress(liveState);
  const runDurations = agent.run_history.map((run) => safeNumber(run.duration)).filter(Boolean);
  const avgDuration = runDurations.length
    ? Math.round(runDurations.reduce((sum, duration) => sum + duration, 0) / runDurations.length)
    : 0;
  const modalTabs: Array<{ id: "live" | "history" | "metrics" | "logs"; label: string }> = [
    { id: "live", label: "Live Output" },
    { id: "history", label: "Run History" },
    { id: "metrics", label: "Metrics" },
    { id: "logs", label: "Logs/Trace" },
  ];

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card swarm-agent-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header swarm-agent-modal-header">
          <div>
            <p className="content-eyebrow">Agent Console</p>
            <h3>{agent.name}</h3>
            <div className="swarm-agent-modal-meta">
              <span className={`agent-status-badge ${getRunStatusClass(agent.status)}`}>{running ? "running" : agent.status}</span>
              <span>Last run: {agent.last_run_at ? formatDateTime(agent.last_run_at) : "-"}</span>
            </div>
          </div>
          <div className="swarm-agent-modal-controls">
            <button className="primary-button agent-action-button" disabled={running} onClick={onRun} type="button">
              {running ? "Running..." : "Run Now"}
            </button>
            <button className="text-button agent-action-button" onClick={onClose} type="button">
              Close
            </button>
          </div>
        </div>

        <div className="swarm-agent-tabs" role="tablist" aria-label="Agent tabs">
          {modalTabs.map((tab) => (
            <button
              key={tab.id}
              className={`swarm-agent-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => onChangeTab(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="modal-body swarm-agent-modal-body">
          {activeTab === "live" ? (
            <div className="stack">
              <div className="swarm-state-rail" aria-label="Agent run states">
                {(["Queued", "Running", stepState.finalLabel] as const).map((label, index) => (
                  <div key={`${label}-${index}`} className={`swarm-state-step ${getStateStepClass(label, stepState.finalLabel, running)}`}>
                    <span>{index + 1}</span>
                    <strong>{label}</strong>
                  </div>
                ))}
              </div>
              <div className="agent-activity-item swarm-live-output-card">
                <strong>Latest Output</strong>
                <span>{latestRun?.output || agent.last_output || "No output has been recorded yet."}</span>
                <small>
                  {latestRun?.created_at ? `${formatDateTime(latestRun.created_at)} / ${latestRun.trigger}` : agent.last_trigger || "Waiting for next run"}
                </small>
              </div>
              <div className="swarm-live-grid">
                {(relevantEvents.length ? relevantEvents : swarmEvents.slice(0, 6)).slice(0, 8).map((event) => (
                  <div key={event.id} className="agent-activity-item">
                    <div className="swarm-feed-row">
                      <strong>{event.message}</strong>
                      <span className={`history-pill ${event.level === "error" ? "rejected" : "approved"}`}>{event.source}</span>
                    </div>
                    <span>{event.type}</span>
                    <small>{formatDateTime(event.created_at)}</small>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === "history" ? (
            <div className="agent-activity-list run-log-list">
              {agent.run_history.length === 0 ? (
                <p className="modal-copy">No run history recorded for this agent yet.</p>
              ) : (
                agent.run_history.map((run) => (
                  <div key={run.run_id} className="agent-activity-item">
                    <div className="swarm-feed-row">
                      <strong>{formatDateTime(run.created_at)}</strong>
                      <span className={`history-pill ${getRunStatusClass(run.status)}`}>{run.status}</span>
                    </div>
                    <span>{run.trigger}</span>
                    <span>{run.output || run.final_result || "No output captured."}</span>
                    <small>{run.duration ? `${run.duration} ms` : "Duration unavailable"} / Records affected: {run.records_affected ?? 0}</small>
                  </div>
                ))
              )}
            </div>
          ) : null}

          {activeTab === "metrics" ? (
            <div className="swarm-metrics-grid">
              <div className="agent-activity-item">
                <strong>Runs Today</strong>
                <span>{agent.runs_today}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Completed</strong>
                <span>{agent.success_count}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Failed</strong>
                <span>{agent.failure_count}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Average Duration</strong>
                <span>{avgDuration ? `${avgDuration} ms` : "-"}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Current Trigger</strong>
                <span>{agent.last_trigger || "-"}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Current Action</strong>
                <span>{agent.last_action || "-"}</span>
              </div>
            </div>
          ) : null}

          {activeTab === "logs" ? (
            <div className="swarm-log-columns swarm-agent-log-columns">
              <div>
                <h4>Events</h4>
                <div className="agent-activity-list run-log-list">
                  {(relevantEvents.length ? relevantEvents : swarmEvents.slice(0, 10)).map((event) => (
                    <div key={event.id} className="agent-activity-item">
                      <strong>{event.message}</strong>
                      <span>{event.type}</span>
                      <small>{formatDateTime(event.created_at)}</small>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h4>Jobs + Trace</h4>
                <div className="agent-activity-list run-log-list">
                  {relevantJobs.length === 0 && relevantLogs.length === 0 ? (
                    <p className="modal-copy">No agent-specific jobs or trace logs found yet.</p>
                  ) : null}
                  {relevantJobs.map((job) => (
                    <div key={`${job.job_id ?? job.function}-${job.enqueue_time ?? job.finish_time ?? job.status}`} className="agent-activity-item">
                      <strong>{formatJobLabel(job.function)}</strong>
                      <span>{job.result || job.status}</span>
                      <small>{job.finish_time ? formatDateTime(job.finish_time) : job.enqueue_time ? formatDateTime(job.enqueue_time) : "Waiting"}</small>
                    </div>
                  ))}
                  {relevantLogs.map((log) => (
                    <div key={log.id} className="agent-activity-item">
                      <strong>{log.action}</strong>
                      <span>{log.entity_type}{log.entity_id ? ` / ${log.entity_id}` : ""}</span>
                      <small>{formatDateTime(log.created_at)}</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

import { useState, type Dispatch, type SetStateAction } from "react";
import type { GraphRun, SwarmStatusResponse, SwarmEvent, SwarmJobsResponse } from "../lib/api";
import type { DataState } from "../types/appState";
import {
  safeNumber,
  getAgentIcon,
  getRunStatusClass,
  formatAgentStatusLabel,
  formatDateTime,
  formatJobLabel,
} from "../lib/formatters";
import { AuditLogList } from "../components/AuditLogList";
import { SwarmAgentModal } from "../components/SwarmAgentModal";

export function GraphRunsPage({
  runs,
  loading,
  swarmStatus,
  swarmEvents,
  swarmJobs,
  runningSwarmAgents,
  onRunSwarmAgent,
  selectedRun,
  selectedRunId,
  selectedRunLoading,
  onSelectRun,
  data,
}: {
  runs: GraphRun[];
  loading: boolean;
  swarmStatus: SwarmStatusResponse | null;
  swarmEvents: SwarmEvent[];
  swarmJobs: SwarmJobsResponse | null;
  runningSwarmAgents: Record<string, boolean>;
  onRunSwarmAgent: (agentName: string) => Promise<void>;
  selectedRun: GraphRun | null;
  selectedRunId: string | null;
  selectedRunLoading: boolean;
  onSelectRun: Dispatch<SetStateAction<string | null>>;
  data: DataState;
}) {
  const [agentModalName, setAgentModalName] = useState<string | null>(null);
  const [agentModalTab, setAgentModalTab] = useState<"live" | "history" | "metrics" | "logs">("live");
  const agents = swarmStatus?.agents ?? [];
  const todaysRuns = agents.reduce((sum, agent) => sum + safeNumber(agent.runs_today), 0);
  const completedRuns = agents.reduce((sum, agent) => sum + safeNumber(agent.success_count), 0);
  const failedRuns = agents.reduce((sum, agent) => sum + safeNumber(agent.failure_count), 0);
  const runDurations = agents.flatMap((agent) => agent.run_history.map((run) => safeNumber(run.duration)).filter(Boolean));
  const avgDuration = runDurations.length
    ? Math.round(runDurations.reduce((sum, duration) => sum + duration, 0) / runDurations.length)
    : 0;
  const health = swarmStatus?.health;
  const queuedJobs = swarmJobs?.queued_jobs ?? [];
  const completedJobs = swarmJobs?.completed_jobs ?? [];
  const runningCount = swarmJobs?.counts.running ?? health?.running_count ?? 0;
  const activeRules = data.automations.length;
  const enabledRules = data.automations.filter((rule) => rule.is_enabled).length;
  const queueItems = [
    ...queuedJobs.map((job) => ({ ...job, bucket: "Queued" })),
    ...completedJobs.slice(0, 8).map((job) => ({ ...job, bucket: job.status === "failed" ? "Failed" : "Completed" })),
  ];
  const agentAuditLogs = data.auditLogs.filter((log) => log.action.startsWith("agent.") || log.action.startsWith("automation."));
  const systemAuditLogs = data.auditLogs.filter((log) => !log.action.startsWith("agent.") && !log.action.startsWith("automation."));
  const selectedAgent = agents.find((agent) => agent.name === agentModalName) ?? null;

  function openAgentModal(agentName: string, tab: "live" | "history" | "metrics" | "logs" = "live") {
    setAgentModalName(agentName);
    setAgentModalTab(tab);
  }

  async function handleRunAgentWithModal(agentName: string) {
    openAgentModal(agentName, "live");
    await onRunSwarmAgent(agentName);
  }

  return (
    <section className="stack">
      <div className="card-grid">
        <article className="summary-card">
          <p>Total Runs Today</p>
          <strong>{todaysRuns}</strong>
        </article>
        <article className="summary-card">
          <p>Completed</p>
          <strong>{completedRuns}</strong>
        </article>
        <article className="summary-card">
          <p>Failed</p>
          <strong>{failedRuns}</strong>
        </article>
        <article className="summary-card">
          <p>Avg Duration</p>
          <strong>{avgDuration} ms</strong>
        </article>
        <article className="summary-card">
          <p>Active Rules</p>
          <strong>{activeRules}</strong>
        </article>
        <article className="summary-card">
          <p>Enabled Rules</p>
          <strong>{enabledRules}</strong>
        </article>
      </div>

      <div className="swarm-top-grid">
        <section className="panel-card swarm-agents-panel">
          <div className="form-header">
            <div>
              <h3>Agent Fleet</h3>
              <p className="subtle-text">Premium fleet layout with clean status cards and deeper detail reserved for the modal.</p>
            </div>
          </div>
          {loading && !swarmStatus ? (
            <p className="modal-copy">Loading agents...</p>
          ) : swarmStatus?.agents.length ? (
            <div className="swarm-agent-grid">
              {swarmStatus.agents.map((agent) => (
                <article
                  key={agent.name}
                  className="swarm-agent-card"
                  onClick={() => openAgentModal(agent.name)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openAgentModal(agent.name);
                    }
                  }}
                >
                  <div className="swarm-agent-header">
                    <div className="swarm-agent-title">
                      <span className="swarm-agent-icon" aria-hidden="true">{getAgentIcon(agent.name)}</span>
                      <div>
                        <strong>{agent.name}</strong>
                        <small className="swarm-agent-summary" title={agent.last_action || agent.last_trigger || "No recent activity"}>
                          {agent.last_action || agent.last_trigger || "No recent activity"}
                        </small>
                      </div>
                    </div>
                    <span className={`agent-status-badge ${getRunStatusClass(agent.status)}`}>{formatAgentStatusLabel(agent.status)}</span>
                  </div>
                  <div className="swarm-agent-stats">
                    <div className="swarm-agent-stat">
                      <span>Today Runs</span>
                      <strong>{agent.runs_today}</strong>
                    </div>
                    <div className="swarm-agent-stat">
                      <span>Completed</span>
                      <strong>{agent.success_count}</strong>
                    </div>
                    <div className="swarm-agent-stat">
                      <span>Failed</span>
                      <strong>{agent.failure_count}</strong>
                    </div>
                  </div>
                  <div className="swarm-agent-last-run">
                    <span>Last run</span>
                    <strong>{agent.last_run_at ? formatDateTime(agent.last_run_at) : "-"}</strong>
                  </div>
                  <div className="swarm-agent-actions">
                    <button
                      className="primary-button agent-action-button"
                      disabled={Boolean(runningSwarmAgents[agent.name])}
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleRunAgentWithModal(agent.name);
                      }}
                      title="Run this agent and open the live output modal."
                      type="button"
                    >
                      {runningSwarmAgents[agent.name] ? "Running..." : "Run Now"}
                    </button>
                    <button
                      className="text-button agent-action-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        openAgentModal(agent.name, "live");
                      }}
                      title="Open live output, history, metrics, and logs for this agent."
                      type="button"
                    >
                      Details
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="modal-copy">No agent activity has been recorded yet.</p>
          )}
        </section>

        <aside className="panel-card swarm-health-card">
          <div className="form-header">
            <div>
              <h3>Health</h3>
              <p className="subtle-text">Realtime platform health and queue conditions.</p>
            </div>
          </div>
          <div className="swarm-health-list">
            <div className="agent-activity-item">
              <strong>Redis</strong>
              <span className={`history-pill ${health?.redis === "connected" ? "approved" : "pending"}`}>{health?.redis ?? "-"}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Workers</strong>
              <span className={`history-pill ${health?.workers === "online" ? "approved" : "pending"}`}>{health?.workers ?? "-"}</span>
            </div>
            <div className="agent-activity-item">
              <strong>AI Gateway</strong>
              <span className={`history-pill ${health?.ai === "ok" ? "approved" : "pending"}`}>{health?.ai ?? "-"}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Queued Jobs</strong>
              <span>{swarmJobs?.counts.queued ?? 0}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Running Jobs</strong>
              <span>{runningCount}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Provider</strong>
              <span>{health?.provider ? `${health.provider} / ${health.model}` : "-"}</span>
            </div>
          </div>
          {health?.worker_heartbeat ? <p className="subtle-text">{health.worker_heartbeat}</p> : null}
        </aside>
      </div>

      <div className="swarm-console-grid">
        <div className="panel-card">
          <div className="form-header">
            <div>
              <h3>Live Activity</h3>
              <p className="subtle-text">Recent autonomous actions, approvals, and queue outcomes across the workspace.</p>
            </div>
          </div>
          {loading && swarmEvents.length === 0 ? (
            <p className="modal-copy">Loading activity...</p>
          ) : swarmEvents.length === 0 ? (
            <p className="modal-copy">No autonomous activity has been recorded yet.</p>
          ) : (
            <div className="agent-activity-list run-log-list">
              {swarmEvents.map((event) => (
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
          )}
        </div>

        <div className="panel-card">
          <div className="form-header">
            <div>
              <h3>Queue Panel</h3>
              <p className="subtle-text">Pending, completed, and failed background jobs from Redis + ARQ.</p>
            </div>
          </div>
          <div className="card-grid swarm-mini-grid">
            <article className="summary-card compact-summary-card">
              <p>Queued</p>
              <strong>{swarmJobs?.counts.queued ?? 0}</strong>
            </article>
            <article className="summary-card compact-summary-card">
              <p>Running</p>
              <strong>{runningCount}</strong>
            </article>
            <article className="summary-card compact-summary-card">
              <p>Completed</p>
              <strong>{swarmJobs?.counts.completed ?? 0}</strong>
            </article>
            <article className="summary-card compact-summary-card">
              <p>Failed</p>
              <strong>{swarmJobs?.counts.failed ?? 0}</strong>
            </article>
          </div>
          {queueItems.length === 0 ? (
            <p className="modal-copy">No queue jobs are visible yet.</p>
          ) : (
            <div className="agent-activity-list run-log-list">
              {queueItems.map((job) => (
                <div key={`${job.bucket}-${job.job_id ?? job.function}`} className="agent-activity-item">
                  <div className="swarm-feed-row">
                    <strong>{formatJobLabel(job.function)}</strong>
                    <span className={`history-pill ${getRunStatusClass(job.status)}`}>{job.bucket}</span>
                  </div>
                  <span>{job.job_id ? `Job ${job.job_id.slice(0, 8)}...` : "Pending job"}</span>
                  <small>
                    {job.finish_time ? formatDateTime(job.finish_time) : job.enqueue_time ? formatDateTime(job.enqueue_time) : "Waiting"}
                    {job.result ? ` / ${job.result}` : ""}
                  </small>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <details className="panel-card ops-section">
        <summary>System Logs / Agent Logs</summary>
        <div className="ops-section-body swarm-log-columns">
          <div>
            <h3>Agent Logs</h3>
            <AuditLogList logs={agentAuditLogs.slice(0, 20)} loading={loading} emptyText="No agent logs yet." />
          </div>
          <div>
            <h3>System Logs</h3>
            <AuditLogList logs={systemAuditLogs.slice(0, 20)} loading={loading} emptyText="No system logs yet." />
          </div>
        </div>
      </details>

      <div className="panel-card">
        <div className="form-header">
          <h3>Live Runs</h3>
          <p className="subtle-text">Auto-refreshing every 5 seconds while this page is open.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Graph</th>
                <th>Event</th>
                <th>Status</th>
                <th>Result</th>
                <th>Duration</th>
                <th>Started At</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={7}>
                    Loading swarm runs...
                  </td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={7}>
                    No graph runs yet.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr
                    key={run.id}
                    className={run.id === selectedRunId ? "selected-row" : undefined}
                    onClick={() => onSelectRun(run.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{run.id.slice(0, 8)}...</td>
                    <td>{run.graph_name}</td>
                    <td>{run.event_name}</td>
                    <td><span className={`history-pill ${getRunStatusClass(run.status)}`}>{run.status}</span></td>
                    <td>{run.result || "-"}</td>
                    <td>{run.duration_ms ? `${run.duration_ms} ms` : "-"}</td>
                    <td>{formatDateTime(run.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRun ? (
        <div className="panel-card">
          <div className="form-header">
            <div>
              <h3>Run Trace</h3>
              <p className="subtle-text">Detailed node-by-node trace for the selected graph run.</p>
            </div>
          </div>
          {selectedRunLoading ? (
            <p className="modal-copy">Loading selected run...</p>
          ) : (
            <div className="agent-activity-list run-log-list">
              {selectedRun.logs.length === 0 ? (
                <p className="modal-copy">No trace steps were recorded for this run.</p>
              ) : (
                selectedRun.logs.map((log, index) => (
                  <div key={`${log.time}-${log.action}-${index}`} className="agent-activity-item">
                    <div className="swarm-feed-row">
                      <strong>{log.action}</strong>
                      <span className="history-pill pending">{formatDateTime(log.time)}</span>
                    </div>
                    <span>{log.message}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ) : null}

      {selectedAgent ? (
        <SwarmAgentModal
          agent={selectedAgent}
          swarmEvents={swarmEvents}
          swarmJobs={swarmJobs}
          auditLogs={agentAuditLogs}
          activeTab={agentModalTab}
          running={Boolean(runningSwarmAgents[selectedAgent.name])}
          onChangeTab={setAgentModalTab}
          onClose={() => setAgentModalName(null)}
          onRun={() => void handleRunAgentWithModal(selectedAgent.name)}
        />
      ) : null}
    </section>
  );
}

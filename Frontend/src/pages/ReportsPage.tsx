import type { Dispatch, SetStateAction } from "react";

import type { ReportPeriod, ReportsPerformance, ReportsPipeline, ReportsSummary } from "../lib/api";
import { formatCurrency, getReportPeriodLabel } from "../lib/formatters";

export function ReportsPage({
  summary,
  pipeline,
  performance,
  loading,
  period,
  customRange,
  onRefresh,
  onPeriodChange,
  onCustomRangeChange,
}: {
  summary: ReportsSummary | null;
  pipeline: ReportsPipeline | null;
  performance: ReportsPerformance | null;
  loading: boolean;
  period: ReportPeriod;
  customRange: { startDate: string; endDate: string };
  onRefresh: (period?: ReportPeriod) => Promise<void>;
  onPeriodChange: Dispatch<SetStateAction<ReportPeriod>>;
  onCustomRangeChange: Dispatch<SetStateAction<{ startDate: string; endDate: string }>>;
}) {
  const periodLabel = getReportPeriodLabel(period);
  const pipelineStages = pipeline?.stages ?? pipeline?.deals_by_stage ?? [];

  return (
    <section className="stack">
      <div className="panel-card form-card">
        <div className="form-header bulk-toolbar">
          <div>
            <h3>Reports</h3>
            <p className="subtle-text">Pipeline and performance reporting for {periodLabel.toLowerCase()}.</p>
          </div>
          <div className="action-row">
            <select value={period} onChange={(event) => onPeriodChange(event.target.value as ReportPeriod)}>
              <option value="today">Today</option>
              <option value="last_7_days">Last 7 Days</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="this_month">This Month</option>
              <option value="last_quarter">Last Quarter</option>
              <option value="this_year">This Year</option>
              <option value="custom">Custom Range</option>
            </select>
            {period === "custom" ? (
              <>
                <input
                  type="date"
                  value={customRange.startDate}
                  onChange={(event) => onCustomRangeChange((current) => ({ ...current, startDate: event.target.value }))}
                />
                <input
                  type="date"
                  value={customRange.endDate}
                  onChange={(event) => onCustomRangeChange((current) => ({ ...current, endDate: event.target.value }))}
                />
              </>
            ) : null}
            <button className="primary-button" onClick={() => void onRefresh(period)} type="button">
              {loading ? "Refreshing..." : "Refresh Reports"}
            </button>
          </div>
        </div>
      </div>

      <div className="reports-grid">
        <div className="panel-card agent-card">
          <div className="form-header">
            <div>
              <h3>Pipeline</h3>
              <p className="subtle-text">Current stage volume and total value.</p>
            </div>
          </div>
          {loading && !pipeline ? (
            <p className="modal-copy">Loading pipeline report...</p>
          ) : pipelineStages.length === 0 ? (
            <p className="modal-copy">No pipeline data yet.</p>
          ) : (
            <div className="reports-stage-list">
              {pipelineStages.map((stage) => (
                <div key={stage.stage} className="reports-stage-item">
                  <div className="reports-stage-meta">
                    <strong>{stage.stage}</strong>
                    <span>{stage.count} deals ? {formatCurrency(stage.total_value, "USD")}</span>
                  </div>
                  <div className="reports-stage-bar">
                    <div className="reports-stage-bar-fill" style={{ width: `${Math.max(10, Math.min(100, stage.count * 12))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel-card agent-card">
          <div className="form-header">
            <div>
              <h3>Performance</h3>
              <p className="subtle-text">{periodLabel} outcomes from completed work.</p>
            </div>
          </div>
          {loading && !performance ? (
            <p className="modal-copy">Loading performance report...</p>
          ) : performance ? (
            <div className="insights-grid reports-mini-grid">
              <div className="agent-activity-item">
                <strong>Revenue</strong>
                <span>{formatCurrency(performance.won_revenue, "USD")}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Closed Deals</strong>
                <span>{performance.closed_deals}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Tasks Completed</strong>
                <span>{performance.tasks_completed}</span>
              </div>
              <div className="agent-activity-item">
                <strong>Meetings Completed</strong>
                <span>{performance.meetings_completed}</span>
              </div>
            </div>
          ) : (
            <p className="modal-copy">No performance data yet.</p>
          )}
        </div>
      </div>

      <div className="panel-card agent-card">
        <div className="form-header">
          <div>
            <h3>Snapshot</h3>
            <p className="subtle-text">Top-level CRM counts for the selected reporting period.</p>
          </div>
        </div>
        {summary ? (
          <div className="insights-grid">
            <div className="agent-activity-item">
              <strong>Total Contacts</strong>
              <span>{summary.total_contacts}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Open Deals</strong>
              <span>{summary.open_deals}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Won Deals</strong>
              <span>{summary.won_deals}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Lost Deals</strong>
              <span>{summary.lost_deals}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Tasks Pending</strong>
              <span>{summary.tasks_pending}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Upcoming Meetings</strong>
              <span>{summary.meetings_upcoming}</span>
            </div>
          </div>
        ) : (
          <p className="modal-copy">No summary report yet.</p>
        )}
      </div>
    </section>
  );
}

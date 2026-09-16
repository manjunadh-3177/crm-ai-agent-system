import type { ForecastResponse, NurtureStatus } from "../lib/api";
import type { DataState } from "../types/appState";
import { formatCurrency } from "../lib/formatters";

export function DashboardPage({
  data,
  loading,
  forecast,
  forecastLoading,
  nurtureStatus,
  onRefreshForecast,
  viewerRole,
}: {
  data: DataState;
  loading: boolean;
  forecast: ForecastResponse | null;
  forecastLoading: boolean;
  nurtureStatus: NurtureStatus;
  onRefreshForecast: () => Promise<void>;
  viewerRole: string;
}) {
  const isAdmin = viewerRole === "admin";
  const canSeeManagerInsights = viewerRole === "admin" || viewerRole === "manager";
  const cards = [
    { label: "Teams", value: data.teams.length },
    { label: "Contacts", value: data.contacts.length },
    { label: "Accounts", value: data.accounts.length },
    { label: "Products", value: data.products.length },
    { label: "Deals", value: data.deals.length },
    { label: "Approvals", value: data.approvals.length },
    { label: "Pending Nurture", value: nurtureStatus.pending_count },
    ...(isAdmin ? [{ label: "Audit Logs", value: data.auditLogs.length }] : []),
  ];

  return (
    <section className="stack">
      <div className="card-grid swarm-kpi-row">
        {cards.map((card) => (
          <article key={card.label} className="summary-card">
            <p>{card.label}</p>
            <strong>{loading ? "..." : card.value}</strong>
          </article>
        ))}
      </div>

      <div className="reports-grid">
        <div className="panel-card agent-card">
          <div className="form-header bulk-toolbar">
            <div>
              <h3>Workspace Snapshot</h3>
              <p className="subtle-text">Live operating view of pipeline, tasks, meetings, and AI workflow activity.</p>
            </div>
          </div>
          <div className="insights-grid">
            <div className="agent-activity-item">
              <strong>Open Deals</strong>
              <span>{data.deals.filter((deal) => !deal.stage.is_closed).length}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Upcoming Meetings</strong>
              <span>{data.upcomingMeetings.length}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Open Tasks</strong>
              <span>{data.tasks.filter((task) => task.status === "open").length}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Recent AI Runs</strong>
              <span>{data.workflowRuns.length}</span>
            </div>
          </div>
        </div>

        <div className="panel-card agent-card">
          <div className="form-header bulk-toolbar">
            <div>
              <h3>Manager Forecast</h3>
              <p className="subtle-text">Weighted pipeline, risk flags, and action recommendations.</p>
            </div>
            {canSeeManagerInsights ? (
              <button className="text-button" onClick={() => void onRefreshForecast()} type="button">
                {forecastLoading ? "Refreshing..." : "Refresh"}
              </button>
            ) : null}
          </div>
          {!canSeeManagerInsights ? (
            <p className="modal-copy">Manager forecast is available to managers and admins.</p>
          ) : forecastLoading && !forecast ? (
            <p className="modal-copy">Loading forecast...</p>
          ) : forecast ? (
            <div className="stack">
              <div className="insights-grid">
                <div className="agent-activity-item">
                  <strong>Total Pipeline</strong>
                  <span>{formatCurrency(forecast.metrics.total_pipeline_value, "USD")}</span>
                </div>
                <div className="agent-activity-item">
                  <strong>Weighted Pipeline</strong>
                  <span>{formatCurrency(forecast.metrics.weighted_pipeline_value, "USD")}</span>
                </div>
                <div className="agent-activity-item">
                  <strong>Average Deal Size</strong>
                  <span>{formatCurrency(forecast.metrics.avg_deal_size, "USD")}</span>
                </div>
                <div className="agent-activity-item">
                  <strong>Close Estimate</strong>
                  <span>{formatCurrency(forecast.metrics.close_this_month_estimate, "USD")}</span>
                </div>
              </div>
              <div className="agent-activity-item insight-wide">
                <strong>Summary</strong>
                <span>{forecast.summary}</span>
              </div>
            </div>
          ) : (
            <p className="modal-copy">No forecast available yet.</p>
          )}
        </div>
      </div>
    </section>
  );
}

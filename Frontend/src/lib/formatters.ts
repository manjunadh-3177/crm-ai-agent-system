import type {
  ActivityFeedItem,
  Approval,
  AutomationRule,
  Contact,
  ReportPeriod,
  ResearchInsight,
  SwarmJob,
} from "./api";
import type { Page } from "../types/appState";

export function isBusinessActivity(item: ActivityFeedItem): boolean {
  if (item.type === "note") return true;
  const systemPrefixes = ["agent.", "graph.", "automation.executed", "health.", "swarm."];
  const title = item.title.toLowerCase();
  return !systemPrefixes.some((p) => title.startsWith(p));
}

export function formatActionLabel(action: string): string {
  const mapping: Record<string, string> = {
    "approval.approved": "Approval completed",
    "approval.rejected": "Approval rejected",
    "deal.stage_changed": "Deal moved stage",
    "deal.created": "New deal created",
    "deal.updated": "Deal updated",
    "draft.updated": "Draft updated",
    "email.execution_blocked": "Email blocked by compliance",
    "task.completed": "Task completed",
    "task.created": "Task scheduled",
    "meeting.created": "Meeting scheduled",
    "meeting.completed": "Meeting completed",
    "contact.created": "New contact added",
    "contact.updated": "Contact updated",
    "note.created": "New note added",
    "agent.lead_qualified": "Lead qualified",
    "agent.deal_orchestrated": "Deal health checked",
    "stakeholder.created": "Stakeholder added",
  };
  return mapping[action] || action.split(".").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" ");
}

export function getRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 0) return "just now";
  if (diffInSeconds < 60) return "just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 172800) return "yesterday";
  return date.toLocaleDateString();
}

export function getActivityIcon(action: string): string {
  if (action.startsWith("approval.")) return "✔";
  if (action.startsWith("deal.")) return "📈";
  if (action.startsWith("task.")) return "📝";
  if (action.startsWith("meeting.")) return "📅";
  if (action.startsWith("email.")) return "📧";
  if (action.startsWith("contact.")) return "👤";
  if (action.startsWith("note.")) return "📓";
  if (action.startsWith("agent.")) return "🤖";
  if (action.startsWith("nurture.")) return "🌱";
  if (action.startsWith("lead.")) return "🔥";
  return "🔔";
}

export function getActivityColor(action: string): string {
  if (action.startsWith("approval.")) return "#10b981";
  if (action.startsWith("deal.")) return "#3b82f6";
  if (action.startsWith("task.")) return "#f59e0b";
  if (action.startsWith("meeting.")) return "#8b5cf6";
  if (action.startsWith("email.")) return "#ef4444";
  if (action.startsWith("contact.")) return "#6366f1";
  if (action.startsWith("note.")) return "#64748b";
  if (action.startsWith("agent.")) return "#9bd3c9";
  if (action.startsWith("nurture.")) return "#10b981";
  if (action.startsWith("lead.")) return "#f43f5e";
  return "#94a3b8";
}

export function formatActivityDescription(item: ActivityFeedItem): string {
  const action = item.title;
  const desc = item.description;

  if (action === "approval.approved") return "You approved an email draft";
  if (action === "deal.stage_changed") return desc || "Deal moved to a new stage";
  if (action === "draft.updated") return "AI draft was updated";
  if (action === "email.execution_blocked") return "Email blocked by compliance rules";

  return desc;
}

export function normalizeStageName(stage: string | null | undefined): string {
  return (stage ?? "").trim().toLowerCase();
}

export function safeNumber(value: unknown): number {
  return Number(value || 0);
}

export function getReportPeriodLabel(period: ReportPeriod): string {
  const labels: Record<ReportPeriod, string> = {
    today: "Today",
    last_7_days: "Last 7 Days",
    last_30_days: "Last 30 Days",
    this_month: "This Month",
    last_quarter: "Last Quarter",
    this_year: "This Year",
    custom: "Custom Range",
  };
  return labels[period];
}

export function splitUnsubscribeFooter(body: string): { body: string; unsubscribeUrl: string | null } {
  const match = body.match(/\n?---\s*\nTo stop emails, click Unsubscribe:\s*(https?:\/\/\S+)/i);
  if (!match) {
    return { body, unsubscribeUrl: null };
  }
  return {
    body: body.slice(0, match.index).trimEnd(),
    unsubscribeUrl: match[1],
  };
}

export function formatExecutionStatus(status: string | null): string {
  if (!status) return "-";
  switch (status) {
    case "sent": return "✅ Delivered";
    case "queued": return "Queued";
    case "sending": return "Sending";
    case "failed": return "❌ Send Failed";
    case "blocked_compliance": return "🚫 Blocked (Compliance)";
    case "provider_failed": return "❌ Provider Failed";
    case "stub_sent": return "🧪 Sent (Dev Stub)";
    case "cancelled": return "Cancelled";
    case "pending": return "⏳ Pending";
    default:
      return status.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  }
}

export function findLatestSmsReadyApproval(approvals: Approval[], contacts: Contact[], contactId?: string | null): Approval | null {
  const approvalPool = contactId
    ? approvals.filter((approval) => approval.contact_id === contactId)
    : approvals;
  for (const approval of approvalPool) {
    const contact = contacts.find((item) => item.id === approval.contact_id);
    if (approval.sms_body && contact?.phone) {
      return approval;
    }
  }
  return null;
}

export function getAgentIcon(agentName: string): string {
  const label = agentName.toLowerCase();
  if (label.includes("lead")) return "LS";
  if (label.includes("nurture") || label.includes("email")) return "NU";
  if (label.includes("schedule") || label.includes("meeting")) return "SC";
  if (label.includes("follow")) return "FA";
  return "AG";
}

export function formatAgentStatusLabel(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "success" || normalized === "completed") return "Success";
  if (normalized === "running") return "Running";
  if (normalized === "error" || normalized === "failed") return "Error";
  return "Idle";
}

export function getAgentStateProgress(status: string): { finalLabel: "Completed" | "Failed" } {
  const normalized = status.toLowerCase();
  return {
    finalLabel: normalized === "failed" || normalized === "error" ? "Failed" : "Completed",
  };
}

export function getStateStepClass(label: string, finalLabel: "Completed" | "Failed", running: boolean): string {
  if (label === "Queued") {
    return "done";
  }
  if (label === "Running") {
    return running ? "active" : "done";
  }
  if (label === finalLabel) {
    return running ? "pending" : finalLabel === "Failed" ? "failed" : "done";
  }
  return "pending";
}

export function isJobRelatedToAgent(job: SwarmJob, normalizedAgentName: string): boolean {
  const haystack = `${job.function ?? ""} ${job.result ?? ""} ${job.job_id ?? ""}`.toLowerCase();
  return haystack.includes(normalizedAgentName.replace(/agent/g, "").trim());
}

export function parseResearchInsightNote(noteBody: string): ResearchInsight | null {
  const text = (noteBody || "").trim();
  if (!text || !text.toLowerCase().includes("research insights")) {
    return null;
  }

  const summary = text.match(/Summary:\s*(.+)/i)?.[1]?.trim();
  const industry = text.match(/Industry:\s*(.+)/i)?.[1]?.trim();
  const companySize = text.match(/Company Size:\s*(.+)/i)?.[1]?.trim();
  const outreachAngle = text.match(/Outreach Angle:\s*(.+)/i)?.[1]?.trim();
  const confidenceRaw = text.match(/Confidence:\s*(\d+)%?/i)?.[1];
  const confidence = confidenceRaw ? Number(confidenceRaw) : undefined;

  if (!summary && !industry && !companySize && !outreachAngle && confidence === undefined) {
    return null;
  }

  return {
    status: "completed",
    research_summary: summary,
    industry,
    company_size_guess: companySize,
    outreach_angle: outreachAngle,
    confidence_score: confidence,
  };
}

export function formatRoleLabel(role: string): string {
  return role
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function getRunStatusClass(status: string): string {
  if (status === "completed" || status === "success") {
    return "approved";
  }
  if (status === "failed" || status === "error") {
    return "rejected";
  }
  if (status === "running") {
    return "running";
  }
  if (status === "disabled") {
    return "disabled";
  }
  return "pending";
}

export function formatJobLabel(functionName: string | null): string {
  if (!functionName) {
    return "Background job";
  }

  const labels: Record<string, string> = {
    send_email_job: "send_email_job",
    auto_contact_draft_job: "auto_contact_draft_job",
    nurture_scan_job: "nurture_scan_job",
    research_job: "research_job",
    csv_import_job: "csv_import_job",
    notification_job: "notification_job",
  };

  return labels[functionName] ?? functionName;
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
  }).format(new Date(value));
}

export function formatDateForInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function getCalendarStart(date: Date): Date {
  const start = new Date(date.getFullYear(), date.getMonth(), 1);
  start.setDate(start.getDate() - start.getDay());
  return start;
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function getMeetingStatusClass(status: string): string {
  if (status === "completed") return "status-completed";
  if (status === "cancelled") return "status-cancelled";
  return "status-scheduled";
}

export function formatCurrency(amount: number | null, currency: string): string {
  if (amount === null) {
    return "-";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function getConditionPlaceholder(condition: string): string {
  if (condition === "lead_tier_equals") return "Hot, Warm, or Cold";
  if (condition === "stage_equals") return "Won, Proposal, or Negotiation";
  if (condition === "deal_health_equals") return "healthy, at_risk, or stalled";
  return "";
}

export function getTriggerBadgeColor(trigger: string): string {
  if (trigger.startsWith("deal")) return "#3b82f6";
  if (trigger.startsWith("task")) return "#f59e0b";
  if (trigger.startsWith("meeting")) return "#8b5cf6";
  if (trigger.startsWith("approval")) return "#10b981";
  if (trigger.startsWith("contact")) return "#6366f1";
  if (trigger.startsWith("lead")) return "#f43f5e";
  return "#64748b";
}

export function formatRunStats(rule: AutomationRule): string {
  if (rule.run_count === 0) return "Never run";
  const d = rule.last_run_at ? new Date(rule.last_run_at) : null;
  const ago = d ? getRelativeTime(rule.last_run_at!) : "Unknown";
  return `${rule.run_count} run${rule.run_count !== 1 ? "s" : ""} · Last: ${ago}`;
}

export function getPageTitle(page: Page): string {
  switch (page) {
    case "dashboard":
      return "Dashboard";
    case "reports":
      return "Reports";
    case "accounts":
      return "Accounts";
    case "contacts":
      return "Contacts";
    case "products":
      return "Products";
    case "deals":
      return "Deals";
    case "pipeline":
      return "Pipeline";
    case "calendar":
      return "Calendar Hub";
    case "import-export":
      return "Import / Export";
    case "approvals":
      return "Approvals";
    case "approval-history":
      return "Approval History";
    case "graph-runs":
      return "Swarm console";
    case "tasks":
      return "Tasks Hub";
    case "activity-feed":
      return "Activity Feed";
    case "messages":
      return "Messages";
    case "emails":
      return "Emails";
    case "notifications":
      return "Notifications";
    default:
      return "Acufy CRM";
  }
}

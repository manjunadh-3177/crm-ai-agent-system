const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const AI_BASE_URL = "http://127.0.0.1:8000";
const ADMIN_BASE_URL = "http://127.0.0.1:8000/admin";

export type Team = {
  id: string;
  name: string;
  timezone: string;
  created_at: string;
  updated_at: string;
};

export type Me = {
  user_id: string;
  email: string;
  team_id: string;
  team_name: string;
  role: string;
  full_name: string | null;
  auth_disabled: boolean;
};

export type Contact = {
  id: string;
  team_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  consent_sms: boolean;
  consent_email: boolean;
  job_title: string | null;
  description: string | null;
  account_id: string | null;
  lead_score: number;
  lead_tier: string | null;
  lead_reason: string | null;
  preferred_timezone: string | null;
  working_days: string | null;
  working_hours_start: string | null;
  working_hours_end: string | null;
  preferred_meeting_windows: string | null;
  blocked_days: string | null;
  created_at: string;
  updated_at: string;
};

export type Account = {
  id: string;
  team_id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  created_at: string;
  updated_at: string;
};

export type AccountDetailContact = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
};

export type AccountDetailOpenDeal = {
  id: string;
  name: string;
  amount: number | null;
  stage: string;
  probability: number | null;
  expected_close_date: string | null;
};

export type AccountDetailClosedDeal = {
  id: string;
  name: string;
  amount: number | null;
  stage: string;
  updated_at: string;
};

export type AccountDetailStakeholder = {
  deal_name: string;
  contact_name: string;
  role: string;
};

export type AccountActivitySummary = {
  total_contacts: number;
  total_open_deals: number;
  pipeline_value: number;
  won_value: number;
  last_activity_at: string | null;
};

export type AccountDetail = {
  id: string;
  name: string;
  website: string | null;
  industry: string | null;
  size: string | null;
  created_at: string;
  contacts: AccountDetailContact[];
  open_deals: AccountDetailOpenDeal[];
  closed_deals: AccountDetailClosedDeal[];
  stakeholders: AccountDetailStakeholder[];
  activity_summary: AccountActivitySummary;
};

export type Product = {
  id: string;
  team_id: string;
  name: string;
  sku: string;
  description: string | null;
  price: number;
  currency: string;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Stage = {
  id: string;
  team_id: string;
  name: string;
  position: number;
  is_closed: boolean;
  created_at: string;
  updated_at: string;
};

export type DealOwner = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

export type DealLineItem = {
  id: string;
  team_id: string;
  deal_id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  currency: string;
  created_at: string;
  updated_at: string;
  product: Product;
};

export type DealStakeholder = {
  id: string;
  team_id: string;
  deal_id: string;
  contact_id: string;
  role: "decision_maker" | "champion" | "influencer" | "blocker" | "end_user";
  created_at: string;
  updated_at: string;
  contact: Contact;
};

export type Deal = {
  id: string;
  team_id: string;
  name: string;
  amount: number | null;
  currency: string;
  probability: number | null;
  expected_close_date: string | null;
  owner_user_id: string | null;
  stage_id: string;
  contact_id: string | null;
  account_id: string | null;
  deal_health: string;
  deal_reason: string | null;
  created_at: string;
  updated_at: string;
  stage: Stage;
  owner: DealOwner | null;
  contact?: Contact | null;
  account?: Account | null;
  line_items: DealLineItem[];
  stakeholders: DealStakeholder[];
};

export type ContactCreateInput = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  consent_sms: boolean;
  consent_email: boolean;
  job_title?: string;
  description?: string;
  account_id?: string;
  preferred_timezone?: string | null;
  working_days?: string | null;
  working_hours_start?: string | null;
  working_hours_end?: string | null;
  preferred_meeting_windows?: string | null;
  blocked_days?: string | null;
};

export type ContactUpdateInput = Partial<Omit<ContactCreateInput, "team_id">>;

export type DealCreateInput = {
  name: string;
  amount: number | null;
  currency: string;
  probability: number | null;
  expected_close_date: string | null;
  owner_user_id: string | null;
  stage_id: string;
  contact_id: string | null;
  account_id: string | null;
};

export type DealUpdateInput = Partial<Omit<DealCreateInput, "team_id">>;

export type ProductCreateInput = {
  name: string;
  sku: string;
  description: string | null;
  price: number;
  currency: string;
  custom_fields: Record<string, unknown>;
};

export type ProductUpdateInput = Partial<ProductCreateInput>;

export type DealLineItemCreateInput = {
  product_id: string;
  quantity: number;
  unit_price?: number | null;
};

export type DealLineItemUpdateInput = {
  quantity?: number;
  unit_price?: number;
};

export type DealStakeholderCreateInput = {
  contact_id: string;
  role: DealStakeholder["role"];
};

export type DealStakeholderUpdateInput = {
  role: DealStakeholder["role"];
};

export type ProposalDocument = {
  id: string;
  team_id: string;
  deal_id: string | null;
  contact_id: string | null;
  account_id: string | null;
  title: string;
  document_type: string;
  content_format: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProposalDraft = {
  document: ProposalDocument;
  title: string;
  content: string;
  content_format: string;
};

export type Meeting = {
  id: string;
  team_id: string;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  timezone: string;
  status: string;
  location: string | null;
  meeting_type: string;
  reminder_minutes: number | null;
  contact_id: string | null;
  deal_id: string | null;
  account_id: string | null;
  created_at: string;
  updated_at: string;
  contact?: Contact | null;
  deal?: Deal | null;
  account?: Account | null;
};

export type MeetingCreateInput = {
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  timezone?: string;
  location: string | null;
  meeting_type: string;
  reminder_minutes: number | null;
  contact_id: string | null;
  deal_id: string | null;
  account_id: string | null;
};

export type MeetingUpdateInput = Partial<MeetingCreateInput>;

export type SchedulerSuggestedSlot = {
  starts_at: string;
  ends_at: string;
  label: string;
  your_time_label: string;
  customer_time_label: string;
  your_timezone: string;
  customer_timezone: string;
  duration_minutes: number;
};

export type SchedulerAvailabilitySummary = {
  timezone: string;
  working_days: string;
  working_hours_start: string;
  working_hours_end: string;
  preferred_meeting_windows: string | null;
  blocked_days: string | null;
  summary: string;
};

export type SchedulerSuggestResponse = {
  slots: SchedulerSuggestedSlot[];
  message: string;
  your_availability: SchedulerAvailabilitySummary;
  customer_availability: SchedulerAvailabilitySummary;
};

export type Task = {
  id: string;
  team_id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  priority: "low" | "med" | "high";
  status: "open" | "done" | "cancelled";
  contact_id: string | null;
  deal_id: string | null;
  account_id: string | null;
  assigned_user_id: string | null;
  created_at: string;
  updated_at: string;
  contact?: Contact | null;
  deal?: Deal | null;
  account?: Account | null;
};

export type TaskCreateInput = {
  title: string;
  description: string | null;
  due_at: string | null;
  priority: Task["priority"];
  status: Task["status"];
  contact_id: string | null;
  deal_id: string | null;
  account_id: string | null;
  assigned_user_id: string | null;
};

export type TaskUpdateInput = Partial<TaskCreateInput>;

export type DealTimelineItem = {
  id: string;
  type: string;
  time: string;
  description: string;
};

export type BulkOperationResult = {
  processed: number;
  skipped: number;
};

export type ImportRowError = {
  row_number: number;
  message: string;
  row: Record<string, string>;
};

export type ImportResult = {
  entity: string;
  created: number;
  skipped: number;
  failed: number;
  errors: ImportRowError[];
};

export type LeadSummary = {
  summary: string;
  recommended_next_action: string;
  priority: "low" | "medium" | "high";
};

export type EmailDraft = {
  subject: string;
  body: string;
  tone: "professional";
};

export type Note = {
  id: string;
  team_id: string;
  body: string;
  entity_type: string;
  entity_id: string;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type NoteCreateInput = {
  body: string;
  entity_type: string;
  entity_id: string;
};

export type NoteUpdateInput = {
  body?: string;
};

export type ActivityFeedItem = {
  id: string;
  type: "audit_log" | "note";
  time: string;
  title: string;
  description: string;
  actor_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  metadata_json: any | null;
};

export type AutomationRule = {
  id: string;
  team_id: string;
  name: string;
  description: string | null;
  trigger_type: string;
  conditions_json: { type: string; value?: string };
  action_type: string;
  action_payload_json: Record<string, string>;
  is_enabled: boolean;
  run_count: number;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AutomationRuleCreateInput = {
  name: string;
  description?: string;
  trigger_type: string;
  conditions_json?: { type: string; value?: string };
  action_type: string;
  action_payload_json?: Record<string, string>;
  is_enabled?: boolean;
};

export type AutomationRuleUpdateInput = {
  name?: string;
  description?: string;
  trigger_type?: string;
  conditions_json?: { type: string; value?: string };
  action_type?: string;
  action_payload_json?: Record<string, string>;
  is_enabled?: boolean;
};

export type ContactMemory = {
  contact_id: string;
  relationship_status: string;
  last_contacted_at: string | null;
  common_topics: string[];
  responsiveness: string;
  recommended_tone: string;
};

export type Approval = {
  id: string;
  type: "email";
  status: "pending" | "approved" | "rejected";
  contact_id: string;
  deal_id: string | null;
  draft_id: string;
  created_at: string;
  decided_at: string | null;
  decision_notes: string | null;
  executed_at: string | null;
  execution_status: string | null;
  provider_message_id: string | null;
  execution_detail: string | null;
  contact_name: string;
  subject: string;
  body: string;
  sms_body: string | null;
};

export type ReportPeriod =
  | "today"
  | "last_7_days"
  | "last_30_days"
  | "this_month"
  | "last_quarter"
  | "this_year"
  | "custom";

export type ReportFilter = {
  period: ReportPeriod;
  startDate?: string;
  endDate?: string;
};

export type AuditLog = {
  id: string;
  team_id: string | null;
  actor_type: "user" | "system" | "ai";
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type GraphRun = {
  id: string;
  graph_name: string;
  event_name: string;
  deal_id: string | null;
  status: string;
  result: string;
  duration_ms: number;
  created_at: string;
  approval_id: string | null;
  logs: GraphRunLog[];
};

export type GraphRunLog = {
  time: string;
  action: string;
  message: string;
};

export type SwarmAgentStatus = {
  name: string;
  status: "idle" | "running" | "error" | "success";
  last_run_at: string | null;
  last_trigger: string;
  last_action: string;
  last_output: string;
  runs_today: number;
  success_count: number;
  failure_count: number;
  run_history: SwarmAgentRunHistory[];
};

export type SwarmAgentRunHistory = {
  run_id: string;
  duration?: number;
  final_result?: string;
  current_node?: string | null;
  completed_nodes?: string[];
  failed_node?: string | null;
  status: string;
  trigger: string;
  output: string;
  records_affected: number | null;
  created_at: string;
};

export type SwarmAgentRunResponse = {
  status: string;
  summary: string;
  records_affected: number;
  message: string;
  run_id: string;
};

export type SwarmHealth = {
  redis: string;
  workers: string;
  queue_enabled: boolean;
  running_count: number;
  queued_count: number;
  worker_heartbeat: string | null;
  ai: string;
  provider: string | null;
  model: string | null;
};

export type SwarmStatusResponse = {
  generated_at: string;
  health: SwarmHealth;
  agents: SwarmAgentStatus[];
};

export type SwarmEvent = {
  id: string;
  source: string;
  type: string;
  message: string;
  created_at: string;
  level: string;
};

export type SwarmJob = {
  job_id: string | null;
  function: string | null;
  status: string;
  enqueue_time: string | null;
  finish_time: string | null;
  success: boolean | null;
  result: string | null;
};

export type SwarmJobsResponse = {
  health: {
    status: string;
    redis: string;
    arq?: string;
    queue_enabled: boolean;
    workers: string;
    running_count: number;
    queued_count: number;
    worker_heartbeat: string | null;
    detail?: string;
  };
  counts: {
    queued: number;
    running: number;
    completed: number;
    failed: number;
  };
  queued_jobs: SwarmJob[];
  running_jobs: SwarmJob[];
  completed_jobs: SwarmJob[];
};

export type ForecastStageMetric = {
  stage: string;
  count: number;
};

export type ForecastDealItem = {
  id: string;
  name: string;
  amount: number | null;
  currency: string;
  probability: number | null;
  stage: string;
  owner: string | null;
  expected_close_date: string | null;
  last_activity_at: string | null;
  stalled_days: number | null;
};

export type ForecastWinLossMetric = {
  count: number;
  total_value: number;
};

export type ForecastMetrics = {
  deals_by_stage: ForecastStageMetric[];
  total_pipeline_value: number;
  weighted_pipeline_value: number;
  avg_deal_size: number;
  stalled_deals: ForecastDealItem[];
  won_this_month: ForecastWinLossMetric;
  lost_this_month: ForecastWinLossMetric;
  close_this_month_estimate: number;
  top_open_deals: ForecastDealItem[];
};

export type ForecastResponse = {
  metrics: ForecastMetrics;
  summary: string;
  risks: string[];
  opportunities: string[];
  recommended_actions: string[];
};

export type ReportsSummary = {
  total_contacts: number;
  open_deals: number;
  won_deals: number;
  lost_deals: number;
  tasks_pending: number;
  meetings_upcoming: number;
  pipeline_value: number;
};

export type ReportsPipelineStage = {
  stage: string;
  count: number;
  total_value: number;
};

export type ReportsPipeline = {
  deals_by_stage: ReportsPipelineStage[];
  stages: ReportsPipelineStage[];
};

export type ReportsPerformance = {
  period: ReportPeriod | string;
  closed_deals: number;
  won_revenue: number;
  meetings_completed: number;
  tasks_completed: number;
};

export type NurturePendingItem = {
  approval_id: string;
  contact_id: string;
  deal_id: string | null;
  created_at: string;
};

export type NurtureStatus = {
  pending_count: number;
  pending_contact_ids: string[];
  pending_deal_ids: string[];
  pending_items: NurturePendingItem[];
};

export type NurtureGenerateResponse = {
  status: string;
  approval_id: string | null;
  reason: string | null;
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? undefined);
  headers.set("Content-Type", "application/json");

  const token = window.localStorage.getItem("auth_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    headers,
    ...init,
  });

  if (!response.ok) {
    const detail = await readErrorMessage(response);
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function fetchForm<T>(url: string, formData: FormData, init?: Omit<RequestInit, "body">): Promise<T> {
  const headers = new Headers(init?.headers ?? undefined);
  const token = window.localStorage.getItem("auth_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...init,
    method: init?.method ?? "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const detail = await readErrorMessage(response);
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? `Request failed with status ${response.status}.`;
  } catch {
    return `Request failed with status ${response.status}.`;
  }
}

export function fetchTeams() {
  return fetchJson<Team[]>(`${API_BASE_URL}/teams`, { method: "GET" });
}

export async function fetchMe(): Promise<Me> {
  const res = await fetchJson<{ authenticated: boolean; user: Me | null }>(`${AI_BASE_URL}/me`, { method: "GET" });
  if (!res.authenticated || !res.user) {
    throw new Error("Not authenticated");
  }
  return res.user;
}

export function fetchContacts() {
  return fetchJson<Contact[]>(`${API_BASE_URL}/contacts`, { method: "GET" });
}

export function createContact(payload: ContactCreateInput) {
  return fetchJson<Contact>(`${API_BASE_URL}/contacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateContact(contactId: string, payload: ContactUpdateInput) {
  return fetchJson<Contact>(`${API_BASE_URL}/contacts/${contactId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteContact(contactId: string) {
  return fetchJson<void>(`${API_BASE_URL}/contacts/${contactId}`, {
    method: "DELETE",
  });
}

export function fetchAccounts() {
  return fetchJson<Account[]>(`${API_BASE_URL}/accounts`, { method: "GET" });
}

export function fetchAccountDetail(accountId: string) {
  return fetchJson<AccountDetail>(`${API_BASE_URL}/accounts/${accountId}`, { method: "GET" });
}

export function fetchProducts() {
  return fetchJson<Product[]>(`${API_BASE_URL}/products`, { method: "GET" });
}

export function createProduct(payload: ProductCreateInput) {
  return fetchJson<Product>(`${API_BASE_URL}/products`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProduct(productId: string, payload: ProductUpdateInput) {
  return fetchJson<Product>(`${API_BASE_URL}/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProduct(productId: string) {
  return fetchJson<void>(`${API_BASE_URL}/products/${productId}`, {
    method: "DELETE",
  });
}

export function fetchDeals() {
  return fetchJson<Deal[]>(`${API_BASE_URL}/deals`, { method: "GET" });
}

export function createDeal(payload: DealCreateInput) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateDeal(dealId: string, payload: DealUpdateInput) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals/${dealId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateDealStage(dealId: string, stageId: string) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals/${dealId}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage_id: stageId }),
  });
}

export function addDealLineItem(dealId: string, payload: DealLineItemCreateInput) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals/${dealId}/line-items`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchDealStakeholders(dealId: string) {
  return fetchJson<DealStakeholder[]>(`${API_BASE_URL}/deals/${dealId}/stakeholders`, {
    method: "GET",
  });
}

export function addDealStakeholder(dealId: string, payload: DealStakeholderCreateInput) {
  return fetchJson<DealStakeholder>(`${API_BASE_URL}/deals/${dealId}/stakeholders`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateDealStakeholder(
  dealId: string,
  stakeholderId: string,
  payload: DealStakeholderUpdateInput,
) {
  return fetchJson<DealStakeholder>(`${API_BASE_URL}/deals/${dealId}/stakeholders/${stakeholderId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteDealStakeholder(dealId: string, stakeholderId: string) {
  return fetchJson<void>(`${API_BASE_URL}/deals/${dealId}/stakeholders/${stakeholderId}`, {
    method: "DELETE",
  });
}

export function updateDealLineItem(dealId: string, lineItemId: string, payload: DealLineItemUpdateInput) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals/${dealId}/line-items/${lineItemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteDealLineItem(dealId: string, lineItemId: string) {
  return fetchJson<Deal>(`${API_BASE_URL}/deals/${dealId}/line-items/${lineItemId}`, {
    method: "DELETE",
  });
}

export function generateDealProposal(dealId: string) {
  return fetchJson<ProposalDraft>(`${API_BASE_URL}/ai/proposal/generate/${dealId}`, {
    method: "POST",
  });
}

export function fetchDealTimeline(dealId: string) {
  return fetchJson<DealTimelineItem[]>(`${API_BASE_URL}/deals/${dealId}/timeline`, {
    method: "GET",
  });
}

export function bulkDeleteContacts(ids: string[]) {
  return fetchJson<BulkOperationResult>(`${API_BASE_URL}/contacts/bulk-delete`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export function bulkDeleteProducts(ids: string[]) {
  return fetchJson<BulkOperationResult>(`${API_BASE_URL}/products/bulk-delete`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export function bulkUpdateDealsStage(ids: string[], stageId: string) {
  return fetchJson<BulkOperationResult>(`${API_BASE_URL}/deals/bulk-stage`, {
    method: "POST",
    body: JSON.stringify({ ids, stage_id: stageId }),
  });
}

export function importContactsCsv(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchForm<ImportResult>(`${API_BASE_URL}/import/contacts`, formData);
}

export function importAccountsCsv(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchForm<ImportResult>(`${API_BASE_URL}/import/accounts`, formData);
}

export function importProductsCsv(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchForm<ImportResult>(`${API_BASE_URL}/import/products`, formData);
}

export async function downloadCsv(path: string, filename: string) {
  const headers = new Headers();
  const token = window.localStorage.getItem("auth_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    const detail = await readErrorMessage(response);
    throw new Error(detail);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export function fetchStages() {
  return fetchJson<Stage[]>(`${API_BASE_URL}/stages`, { method: "GET" });
}

export function fetchLeadSummary(contactId: string, dealId?: string | null) {
  return fetchJson<LeadSummary>(`${AI_BASE_URL}/ai/lead-summary`, {
    method: "POST",
    body: JSON.stringify({
      contact_id: contactId,
      deal_id: dealId ?? undefined,
    }),
  });
}

export function fetchDraftEmail(contactId: string, dealId?: string | null) {
  return fetchJson<EmailDraft>(`${AI_BASE_URL}/ai/draft-email`, {
    method: "POST",
    body: JSON.stringify({
      contact_id: contactId,
      deal_id: dealId ?? undefined,
    }),
  });
}

export function updateApprovalDraft(approvalId: string, subject: string, body: string) {
  return fetchJson<EmailDraft>(`${AI_BASE_URL}/ai/approvals/${approvalId}/draft`, {
    method: "PATCH",
    body: JSON.stringify({ subject, body }),
  });
}

export function fetchContactMemory(contactId: string) {
  return fetchJson<ContactMemory>(`${AI_BASE_URL}/ai/memory/${contactId}`, {
    method: "GET",
  });
}

export function fetchApprovals() {
  return fetchJson<Approval[]>(`${AI_BASE_URL}/ai/approvals`, {
    method: "GET",
  });
}

export function fetchApprovalHistory() {
  return fetchJson<Approval[]>(`${AI_BASE_URL}/ai/approvals/history`, {
    method: "GET",
  });
}

export function approveApproval(approvalId: string, notes?: string) {
  return fetchJson<{ id: string; status: "approved"; decided_at: string | null; decision_notes: string | null }>(
    `${AI_BASE_URL}/ai/approvals/${approvalId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(notes ? { notes } : {}),
    },
  );
}

export function rejectApproval(approvalId: string, notes?: string) {
  return fetchJson<{ id: string; status: "rejected"; decided_at: string | null; decision_notes: string | null }>(
    `${AI_BASE_URL}/ai/approvals/${approvalId}/reject`,
    {
      method: "POST",
      body: JSON.stringify(notes ? { notes } : {}),
    },
  );
}

export function retryApprovalSend(approvalId: string) {
  return fetchJson<{
    id: string;
    status: "approved" | "rejected";
    execution_status: string | null;
    execution_detail: string | null;
  }>(`${AI_BASE_URL}/ai/approvals/${approvalId}/retry-send`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function cancelApprovalSend(approvalId: string) {
  return fetchJson<{
    id: string;
    status: "approved" | "rejected";
    execution_status: string | null;
    execution_detail: string | null;
  }>(`${AI_BASE_URL}/ai/approvals/${approvalId}/cancel-send`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function fetchAuditLogs() {
  return fetchJson<AuditLog[]>(`${ADMIN_BASE_URL}/audit-logs`, {
    method: "GET",
  });
}

export function fetchFollowupAgentLogs() {
  return fetchJson<AuditLog[]>(`${ADMIN_BASE_URL}/agents/followup/logs`, {
    method: "GET",
  });
}

export function fetchFollowupGraphRuns() {
  return fetchJson<GraphRun[]>(`${ADMIN_BASE_URL}/graphs/followup/runs`, {
    method: "GET",
  });
}

export function fetchFollowupGraphRun(runId: string) {
  return fetchJson<GraphRun>(`${ADMIN_BASE_URL}/graphs/followup/runs/${runId}`, {
    method: "GET",
  });
}

export function fetchSwarmStatus() {
  return fetchJson<SwarmStatusResponse>(`${API_BASE_URL}/swarm/status`, {
    method: "GET",
  });
}

export function fetchSwarmEvents() {
  return fetchJson<SwarmEvent[]>(`${API_BASE_URL}/swarm/events`, {
    method: "GET",
  });
}

export function fetchSwarmJobs() {
  return fetchJson<SwarmJobsResponse>(`${API_BASE_URL}/swarm/jobs`, {
    method: "GET",
  });
}

export function runSwarmAgent(agentName: string) {
  return fetchJson<SwarmAgentRunResponse>(`${API_BASE_URL}/swarm/agents/${encodeURIComponent(agentName)}/run`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function fetchForecast() {
  return fetchJson<ForecastResponse>(`${AI_BASE_URL}/ai/forecast`, {
    method: "GET",
  });
}

function buildReportQuery(filter: ReportFilter) {
  const params = new URLSearchParams({ period: filter.period });
  if (filter.period === "custom") {
    if (filter.startDate) params.set("start_date", filter.startDate);
    if (filter.endDate) params.set("end_date", filter.endDate);
  }
  return params.toString();
}

export function fetchReportsSummary(filter: ReportFilter = { period: "this_month" }) {
  return fetchJson<ReportsSummary>(`${API_BASE_URL}/reports/summary?${buildReportQuery(filter)}`, {
    method: "GET",
  });
}

export function fetchReportsPipeline(filter: ReportFilter = { period: "this_month" }) {
  return fetchJson<ReportsPipeline>(`${API_BASE_URL}/reports/pipeline?${buildReportQuery(filter)}`, {
    method: "GET",
  });
}

export function fetchReportsPerformance(filter: ReportFilter = { period: "this_month" }) {
  const params = buildReportQuery(filter);
  return fetchJson<ReportsPerformance>(`${API_BASE_URL}/reports/performance?${params.toString()}`, {
    method: "GET",
  });
}

export function fetchNurtureStatus() {
  return fetchJson<NurtureStatus>(`${AI_BASE_URL}/ai/nurture/status`, {
    method: "GET",
  });
}

export function runNurturerScan() {
  return fetchJson<NurtureGenerateResponse>(`${AI_BASE_URL}/ai/nurture/run`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function generateNurtureNow(payload: { contact_id?: string | null; deal_id?: string | null }) {
  return fetchJson<NurtureGenerateResponse>(`${AI_BASE_URL}/ai/nurture/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getWebSocketUrl(token?: string | null) {
  const baseUrl = new URL(AI_BASE_URL);
  const protocol = baseUrl.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(`${protocol}//${baseUrl.host}/ws`);

  if (token) {
    url.searchParams.set("token", token);
  }

  return url.toString();
}
export type CopilotResponse = {
  intent: string;
  answer: string;
  data: any;
  suggested_actions: string[];
};

export function fetchCopilotChat(message: string) {
  return fetchJson<CopilotResponse>(`${AI_BASE_URL}/ai/copilot/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function fetchMeetings(statusFilter?: string, typeFilter?: string) {
  const params = new URLSearchParams();
  if (statusFilter) params.append("status_filter", statusFilter);
  if (typeFilter) params.append("type_filter", typeFilter);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Meeting[]>(`${API_BASE_URL}/meetings${query}`, { method: "GET" });
}

export function fetchUpcomingMeetings() {
  return fetchJson<Meeting[]>(`${API_BASE_URL}/meetings/upcoming`, { method: "GET" });
}

export function createMeeting(payload: MeetingCreateInput) {
  return fetchJson<Meeting>(`${API_BASE_URL}/meetings`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function suggestMeetingSlots(payload: {
  contact_id?: string | null;
  deal_id?: string | null;
  duration_minutes: number;
  timezone: string;
}) {
  return fetchJson<SchedulerSuggestResponse>(`${AI_BASE_URL}/ai/scheduler/suggest`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function bookSuggestedMeeting(payload: {
  contact_id?: string | null;
  deal_id?: string | null;
  starts_at: string;
  duration_minutes: number;
  timezone: string;
}) {
  return fetchJson<Meeting>(`${AI_BASE_URL}/ai/scheduler/book`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMeeting(meetingId: string, payload: MeetingUpdateInput) {
  return fetchJson<Meeting>(`${API_BASE_URL}/meetings/${meetingId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function completeMeeting(meetingId: string) {
  return fetchJson<Meeting>(`${API_BASE_URL}/meetings/${meetingId}/complete`, {
    method: "PATCH",
  });
}

export function cancelMeeting(meetingId: string) {
  return fetchJson<Meeting>(`${API_BASE_URL}/meetings/${meetingId}/cancel`, {
    method: "PATCH",
  });
}

export function deleteMeeting(meetingId: string) {
  return fetchJson<void>(`${API_BASE_URL}/meetings/${meetingId}`, {
    method: "DELETE",
  });
}

export function getMeetingIcsUrl(meetingId: string) {
  return `${API_BASE_URL}/meetings/${meetingId}/ics`;
}

export function fetchTasks(statusFilter?: string, priorityFilter?: string, assignedTo?: string) {
  const params = new URLSearchParams();
  if (statusFilter) params.append("status_filter", statusFilter);
  if (priorityFilter) params.append("priority_filter", priorityFilter);
  if (assignedTo) params.append("assigned_user_id", assignedTo);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Task[]>(`${API_BASE_URL}/tasks${query}`, { method: "GET" });
}

export function fetchMyTasks() {
  return fetchJson<Task[]>(`${API_BASE_URL}/tasks/my`, { method: "GET" });
}

export function createTask(payload: TaskCreateInput) {
  return fetchJson<Task>(`${API_BASE_URL}/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTask(taskId: string, payload: TaskUpdateInput) {
  return fetchJson<Task>(`${API_BASE_URL}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function completeTask(taskId: string) {
  return fetchJson<Task>(`${API_BASE_URL}/tasks/${taskId}/done`, {
    method: "POST",
  });
}

export function deleteTask(taskId: string) {
  return fetchJson<void>(`${API_BASE_URL}/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export function fetchNotes(entityType?: string, entityId?: string) {
  const params = new URLSearchParams();
  if (entityType) params.append("entity_type", entityType);
  if (entityId) params.append("entity_id", entityId);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Note[]>(`${API_BASE_URL}/notes${query}`, { method: "GET" });
}

export function createNote(payload: NoteCreateInput) {
  return fetchJson<Note>(`${API_BASE_URL}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateNote(noteId: string, payload: NoteUpdateInput) {
  return fetchJson<Note>(`${API_BASE_URL}/notes/${noteId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteNote(noteId: string) {
  return fetchJson<void>(`${API_BASE_URL}/notes/${noteId}`, {
    method: "DELETE",
  });
}

export function fetchActivityFeed(limit: number = 50) {
  return fetchJson<ActivityFeedItem[]>(`${API_BASE_URL}/activity-feed?limit=${limit}`, {
    method: "GET",
  });
}

export function fetchAutomations() {
  return fetchJson<AutomationRule[]>(`${API_BASE_URL}/automations`, {
    method: "GET",
  });
}

export function createAutomation(payload: AutomationRuleCreateInput) {
  return fetchJson<AutomationRule>(`${API_BASE_URL}/automations`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAutomation(id: string, payload: AutomationRuleUpdateInput) {
  return fetchJson<AutomationRule>(`${API_BASE_URL}/automations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function toggleAutomation(id: string) {
  return fetchJson<AutomationRule>(`${API_BASE_URL}/automations/${id}/toggle`, {
    method: "POST",
  });
}

export function deleteAutomation(id: string) {
  return fetchJson<void>(`${API_BASE_URL}/automations/${id}`, {
    method: "DELETE",
  });
}

export type ResearchInsight = {
  status: string;
  research_summary?: string;
  industry?: string;
  company_size_guess?: string;
  outreach_angle?: string;
  confidence_score?: number;
  reason?: string;
};

export function fetchContactResearch(contactId: string) {
  return fetchJson<ResearchInsight>(`${AI_BASE_URL}/ai/research/contact/${contactId}`, {
    method: "POST",
  });
}

export function fetchAccountResearch(accountId: string) {
  return fetchJson<ResearchInsight>(`${AI_BASE_URL}/ai/research/account/${accountId}`, {
    method: "POST",
  });
}

export type EmailMessage = {
  id: string;
  team_id: string;
  contact_id: string | null;
  deal_id: string | null;
  approval_id: string | null;
  direction: string;
  recipient_email: string;
  subject: string;
  body: string;
  provider_message_id: string | null;
  status: string;
  error_detail: string | null;
  created_at: string;
  updated_at: string;
};

export type SMSMessage = {
  id: string;
  team_id: string;
  contact_id: string | null;
  direction: "inbound" | "outbound" | string;
  thread_id: string;
  from_number: string;
  to_number: string;
  body: string;
  status: "Queued" | "Sent" | "Failed" | "Received" | string;
  provider_sid: string | null;
  error_detail: string | null;
  sent_at: string | null;
  received_at: string | null;
  is_read: boolean;
  read_at: string | null;
  agent_suggestion: string | null;
  created_at: string;
  contact?: Contact | null;
};

export function fetchEmails() {
  return fetchJson<EmailMessage[]>(`${API_BASE_URL}/emails`);
}

export function fetchContactEmails(contactId: string) {
  return fetchJson<EmailMessage[]>(`${API_BASE_URL}/emails/contact/${contactId}`);
}

export function fetchDealEmails(dealId: string) {
  return fetchJson<EmailMessage[]>(`${API_BASE_URL}/emails/deal/${dealId}`);
}

export function fetchSmsHistory(direction?: "inbound" | "outbound") {
  const params = new URLSearchParams();
  if (direction) params.set("direction", direction);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<SMSMessage[]>(`${API_BASE_URL}/sms/history${query}`);
}

export function sendSms(payload: { to_number: string; body: string; contact_id?: string | null }) {
  return fetchJson<SMSMessage>(`${API_BASE_URL}/sms/send`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function markSmsRead(smsId: string) {
  return fetchJson<SMSMessage>(`${API_BASE_URL}/sms/${smsId}/mark-read`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function assignSmsContact(smsId: string, contactId: string) {
  return fetchJson<SMSMessage>(`${API_BASE_URL}/sms/${smsId}/assign-contact`, {
    method: "POST",
    body: JSON.stringify({ contact_id: contactId }),
  });
}

export function createSmsTask(smsId: string, title?: string) {
  return fetchJson<{ status: string; task_id: string }>(`${API_BASE_URL}/sms/${smsId}/create-task`, {
    method: "POST",
    body: JSON.stringify(title ? { title } : {}),
  });
}

// ── Notifications ────────────────────────────────────────────────────────────

export type CRMNotification = {
  id: string;
  team_id: string;
  user_id: string | null;
  type: string;
  title: string;
  message: string;
  entity_type: string | null;
  entity_id: string | null;
  is_read: boolean;
  created_at: string;
};

export function fetchNotifications(unreadOnly = false) {
  return fetchJson<CRMNotification[]>(
    `${API_BASE_URL}/notifications?unread_only=${unreadOnly}`
  );
}

export function fetchUnreadCount() {
  return fetchJson<{ unread_count: number }>(`${API_BASE_URL}/notifications/unread-count`);
}

export function markNotificationRead(id: string) {
  return fetchJson<CRMNotification>(`${API_BASE_URL}/notifications/${id}/read`, {
    method: "POST",
  });
}

export function markAllNotificationsRead() {
  return fetchJson<{ updated: number }>(`${API_BASE_URL}/notifications/read-all`, {
    method: "POST",
  });
}

export function deleteNotification(id: string) {
  return fetch(`${API_BASE_URL}/notifications/${id}`, { method: "DELETE" });
}

// ── Import / Export ──────────────────────────────────────────────────────────

export type CsvPreview = {
  headers: string[];
  preview: Record<string, string>[];
};

/** Upload CSV and get headers + first 5 rows back for column mapping. */
export async function previewCsv(file: File): Promise<CsvPreview> {
  const formData = new FormData();
  formData.append("file", file);
  return fetchForm<CsvPreview>(`${API_BASE_URL}/import/contacts/preview`, formData);
}

/** Import contacts with custom column mapping. */
export async function importContactsCsvMapped(
  file: File,
  columnMap: Record<string, string>
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("column_map", JSON.stringify(columnMap));
  return fetchForm<ImportResult>(`${API_BASE_URL}/import/contacts/csv`, formData);
}

/** Download contacts CSV — returns a Blob for browser save. */
export async function downloadContactsCsv(): Promise<Blob> {
  const headers = new Headers();
  const token = window.localStorage.getItem("auth_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}/export/contacts.csv`, { headers });
  if (!response.ok) throw new Error("Export failed.");
  return response.blob();
}

/** Download deals CSV — returns a Blob for browser save. */
export async function downloadDealsCsv(): Promise<Blob> {
  const headers = new Headers();
  const token = window.localStorage.getItem("auth_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}/export/deals.csv`, { headers });
  if (!response.ok) throw new Error("Export failed.");
  return response.blob();
}

/** Trigger a browser file download from a Blob. */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

import type { Dispatch, FormEvent, SetStateAction } from "react";
import type {
  Account,
  AccountDetail,
  Approval,
  AuditLog,
  Contact,
  DealLineItem,
  DealStakeholder,
  DealTimelineItem,
  Deal,
  ForecastResponse,
  GraphRun,
  SwarmEvent,
  SwarmJobsResponse,
  SwarmStatusResponse,
  Me,
  NurtureStatus,
  Product,
  ReportsSummary,
  ReportsPipeline,
  ReportsPerformance,
  ReportPeriod,
  SMSMessage,
  Stage,
  Team,
  Meeting,
  Task,
  ActivityFeedItem,
  AutomationRule,
  ResearchInsight,
  EmailMessage,
  CRMNotification,
} from "../lib/api";

export type Page =
  | "dashboard"
  | "reports"
  | "accounts"
  | "contacts"
  | "products"
  | "deals"
  | "pipeline"
  | "calendar"
  | "import-export"
  | "approvals"
  | "approval-history"
  | "graph-runs"
  | "tasks"
  | "activity-feed"
  | "messages"
  | "emails"
  | "notifications";

export type DataState = {
  me: Me | null;
  teams: Team[];
  contacts: Contact[];
  accounts: Account[];
  products: Product[];
  deals: Deal[];
  stages: Stage[];
  approvals: Approval[];
  approvalHistory: Approval[];
  auditLogs: AuditLog[];
  followupLogs: AuditLog[];
  workflowRuns: GraphRun[];
  meetings: Meeting[];
  upcomingMeetings: Meeting[];
  tasks: Task[];
  myTasks: Task[];
  activityFeed: ActivityFeedItem[];
  automations: AutomationRule[];
  smsMessages: SMSMessage[];
  emails: EmailMessage[];
  notifications: CRMNotification[];
};

export type ContactFormState = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  consent_sms: boolean;
  consent_email: boolean;
  job_title: string;
  description: string;
  account_id: string;
  preferred_timezone: string;
  working_days: string;
  working_hours_start: string;
  working_hours_end: string;
  preferred_meeting_windows: string;
  blocked_days: string;
};

export type DealFormState = {
  name: string;
  amount: string;
  currency: string;
  probability: string;
  expected_close_date: string;
  stage_id: string;
  contact_id: string;
  account_id: string;
};

export type AutomationRuleFormState = {
  name: string;
  description: string;
  trigger_type: string;
  condition_type: string;
  condition_value: string;
  action_type: string;
  action_payload: string;
};

export type ProductFormState = {
  name: string;
  sku: string;
  description: string;
  price: string;
  currency: string;
};

export type LineItemFormState = {
  product_id: string;
  quantity: string;
  unit_price: string;
};

export type StakeholderFormState = {
  contact_id: string;
  role: DealStakeholder["role"];
};

export type MeetingFormState = {
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
  meeting_type: string;
  location: string;
  reminder_minutes: string;
  contact_id: string;
  deal_id: string;
  account_id: string;
};

export type TaskFormState = {
  title: string;
  description: string;
  due_at: string;
  priority: Task["priority"];
  status: Task["status"];
  contact_id: string;
  deal_id: string;
  account_id: string;
  assigned_user_id: string;
};

export type ImportEntity = "contacts" | "accounts" | "products";

export const NAV_ITEMS: Array<{ id: Page; label: string }> = [
  { id: "dashboard", label: "⚡ Dashboard" },
  { id: "contacts", label: "👥 Contacts" },
  { id: "deals", label: "💼 Deals" },
  { id: "pipeline", label: "📈 Pipeline" },
  { id: "graph-runs", label: "🤖 Swarm console" },
  { id: "calendar", label: "📅 Calendar" },
  { id: "approvals", label: "✅ Approvals" },
  { id: "approval-history", label: "📜 Approval History" },
  { id: "import-export", label: "📤 Import / Export" },
  { id: "emails", label: "📧 Emails" },
  { id: "messages", label: "💬 Messages" },
  { id: "reports", label: "📊 Reports" },
  { id: "accounts", label: "🏢 Accounts" },
  { id: "products", label: "📦 Products" },
  { id: "tasks", label: "📋 Tasks" },
  { id: "activity-feed", label: "⚡ Activity Feed" },
  { id: "notifications", label: "🔔 Notifications" },
];

export const INITIAL_DATA: DataState = {
  me: null,
  teams: [],
  contacts: [],
  accounts: [],
  products: [],
  deals: [],
  stages: [],
  approvals: [],
  approvalHistory: [],
  auditLogs: [],
  followupLogs: [],
  workflowRuns: [],
  meetings: [],
  upcomingMeetings: [],
  tasks: [],
  myTasks: [],
  activityFeed: [],
  automations: [],
  smsMessages: [],
  emails: [],
  notifications: [],
};
export const INITIAL_MEETING_FORM: MeetingFormState = {
  title: "",
  description: "",
  starts_at: "",
  ends_at: "",
  timezone: "UTC",
  meeting_type: "internal",
  location: "",
  reminder_minutes: "15",
  contact_id: "",
  deal_id: "",
  account_id: "",
};

export const INITIAL_AUTOMATION_FORM: AutomationRuleFormState = {
  name: "",
  description: "",
  trigger_type: "contact.created",
  condition_type: "always",
  condition_value: "",
  action_type: "notify_user",
  action_payload: JSON.stringify({ title: "Action Required", message: "A rule was triggered." }, null, 2),
};

export const INITIAL_TASK_FORM: TaskFormState = {
  title: "",
  description: "",
  due_at: "",
  priority: "med",
  status: "open",
  contact_id: "",
  deal_id: "",
  account_id: "",
  assigned_user_id: "",
};

export const INITIAL_CONTACT_FORM: ContactFormState = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  consent_sms: false,
  consent_email: true,
  job_title: "",
  description: "",
  account_id: "",
  preferred_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  working_days: "Mon-Fri",
  working_hours_start: "09:00",
  working_hours_end: "17:00",
  preferred_meeting_windows: "",
  blocked_days: "",
};

export const INITIAL_DEAL_FORM: DealFormState = {
  name: "",
  amount: "",
  currency: "USD",
  probability: "",
  expected_close_date: "",
  stage_id: "",
  contact_id: "",
  account_id: "",
};

export const INITIAL_PRODUCT_FORM: ProductFormState = {
  name: "",
  sku: "",
  description: "",
  price: "",
  currency: "USD",
};

export const INITIAL_LINE_ITEM_FORM: LineItemFormState = {
  product_id: "",
  quantity: "1",
  unit_price: "",
};

export const INITIAL_STAKEHOLDER_FORM: StakeholderFormState = {
  contact_id: "",
  role: "decision_maker",
};

export const STAKEHOLDER_ROLE_OPTIONS: DealStakeholder["role"][] = [
  "decision_maker",
  "champion",
  "influencer",
  "blocker",
  "end_user",
];

export const PIPELINE_STAGE_ORDER = ["Lead", "Qualified", "Proposal", "Negotiation", "Won", "Lost"];

function normalizeStageNameLocal(stage: string | null | undefined): string {
  return (stage ?? "").trim().toLowerCase();
}

export const PIPELINE_STAGE_KEYS = new Set(PIPELINE_STAGE_ORDER.map(normalizeStageNameLocal));

export const FRONTEND_SESSION_KEY = "acufycrm_frontend_session";
export const AUTH0_PLACEHOLDER_DOMAINS = new Set(["", "demo-domain.auth0.com"]);
export const AUTH0_PLACEHOLDER_CLIENT_IDS = new Set(["", "demo-client-id"]);
export const DEFAULT_AVATAR =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
      <rect width="96" height="96" rx="48" fill="#D7E6F4"/>
      <circle cx="48" cy="37" r="18" fill="#8DA9C4"/>
      <path d="M21 80c4-16 16-24 27-24s23 8 27 24" fill="#8DA9C4"/>
    </svg>`,
  );

export type PageProps = {
  data: DataState;
  loading: boolean;
  selectedGraphRun: GraphRun | null;
  selectedGraphRunId: string | null;
  selectedGraphRunLoading: boolean;
  swarmStatus: SwarmStatusResponse | null;
  swarmEvents: SwarmEvent[];
  swarmJobs: SwarmJobsResponse | null;
  swarmLoading: boolean;
  runningSwarmAgents: Record<string, boolean>;
  onRunSwarmAgent: (agentName: string) => Promise<void>;
  onSelectGraphRun: Dispatch<SetStateAction<string | null>>;
  accountDetail: AccountDetail | null;
  accountDetailLoading: boolean;
  selectedAccountId: string | null;
  onSelectAccount: Dispatch<SetStateAction<string | null>>;
  forecast: ForecastResponse | null;
  forecastLoading: boolean;
  reportsSummary: ReportsSummary | null;
  reportsPipeline: ReportsPipeline | null;
  reportsPerformance: ReportsPerformance | null;
  reportsLoading: boolean;
  reportsPeriod: ReportPeriod;
  reportsCustomRange: { startDate: string; endDate: string };
  contactForm: ContactFormState;
  dealForm: DealFormState;
  productForm: ProductFormState;
  lineItemForm: LineItemFormState;
  contactSubmitting: boolean;
  dealSubmitting: boolean;
  productSubmitting: boolean;
  lineItemSubmitting: boolean;
  bulkSubmitting: "contacts" | "products" | "deals" | null;
  importSubmitting: ImportEntity | null;
  onContactFormChange: Dispatch<SetStateAction<ContactFormState>>;
  onDealFormChange: Dispatch<SetStateAction<DealFormState>>;
  onProductFormChange: Dispatch<SetStateAction<ProductFormState>>;
  onLineItemFormChange: Dispatch<SetStateAction<LineItemFormState>>;
  onCreateContact: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCreateDeal: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCreateOrUpdateProduct: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDeleteContact: (contactId: string) => Promise<void>;
  onDeleteProduct: (productId: string) => Promise<void>;
  onEditProduct: (product: Product) => void;
  onMoveDealStage: (dealId: string, stageId: string) => Promise<void>;
  onBulkDeleteContacts: () => Promise<void>;
  onBulkDeleteProducts: () => Promise<void>;
  onBulkMoveDeals: () => Promise<void>;
  onNavigate: Dispatch<SetStateAction<Page>>;
  onOpenDealFromPipeline: (dealId: string) => void;
  onImportCsv: (entity: ImportEntity, file: File | null) => Promise<void>;
  onExportCsv: (path: string, filename: string) => Promise<void>;
  onSelectDeal: Dispatch<SetStateAction<string | null>>;
  onAddLineItem: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddStakeholder: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateLineItem: (lineItem: DealLineItem) => Promise<void>;
  onUpdateStakeholder: (stakeholder: DealStakeholder, role: DealStakeholder["role"]) => Promise<void>;
  onDeleteLineItem: (lineItemId: string) => Promise<void>;
  onDeleteStakeholder: (stakeholderId: string) => Promise<void>;
  onGenerateProposal: () => Promise<void>;
  onLoadLeadSummary: (contact: Contact) => Promise<void>;
  onLoadEmailDraft: (contact: Contact) => Promise<void>;
  onRunAllContactAgents: (contact: Contact) => Promise<void>;
  onGenerateNurtureNow: (target: { contactId?: string | null; dealId?: string | null }) => Promise<void>;
  onRefreshForecast: () => Promise<void>;
  onRefreshReports: (period?: ReportPeriod) => Promise<void>;
  onReloadData: () => Promise<void>;
  onReportsPeriodChange: Dispatch<SetStateAction<ReportPeriod>>;
  onReportsCustomRangeChange: Dispatch<SetStateAction<{ startDate: string; endDate: string }>>;
  onApprove: (approvalId: string) => Promise<void>;
  onApproveAndSendSms: (approval: Approval) => Promise<void>;
  onReject: (approvalId: string) => Promise<void>;
  onRetryApprovalSend: (approvalId: string) => Promise<void>;
  onCancelApprovalSend: (approvalId: string) => Promise<void>;
  summaryLoadingId: string | null;
  draftLoadingId: string | null;
  runningContactAgentId: string | null;
  approvalSubmittingId: string | null;
  linkedDealsByContact: Map<string, Deal>;
  onViewApprovalDraft: Dispatch<SetStateAction<Approval | null>>;
  selectedDeal: Deal | null;
  stakeholderForm: StakeholderFormState;
  onStakeholderFormChange: Dispatch<SetStateAction<StakeholderFormState>>;
  editingProductId: string | null;
  lineItemUpdatingId: string | null;
  stakeholderUpdatingId: string | null;
  selectedContactIds: string[];
  onSelectedContactIdsChange: Dispatch<SetStateAction<string[]>>;
  selectedProductIds: string[];
  onSelectedProductIdsChange: Dispatch<SetStateAction<string[]>>;
  selectedDealIds: string[];
  onSelectedDealIdsChange: Dispatch<SetStateAction<string[]>>;
  bulkStageId: string;
  onBulkStageIdChange: Dispatch<SetStateAction<string>>;
  dealTimeline: DealTimelineItem[];
  dealTimelineLoading: boolean;
  lineItemDrafts: Record<string, { quantity: string; unit_price: string }>;
  onLineItemDraftChange: Dispatch<
    SetStateAction<Record<string, { quantity: string; unit_price: string }>>
  >;
  stakeholderSubmitting: boolean;
  meetingForm: MeetingFormState;
  onMeetingFormChange: Dispatch<SetStateAction<MeetingFormState>>;
  onCreateMeeting: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCompleteMeeting: (meetingId: string) => Promise<void>;
  onCancelMeeting: (meetingId: string) => Promise<void>;
  onDeleteMeeting: (meetingId: string) => Promise<void>;
  onEditMeeting: (meeting: Meeting) => void;
  meetingSubmitting: boolean;
  selectedMeetingId: string | null;
  onSelectMeeting: Dispatch<SetStateAction<string | null>>;
  meetingComposerOpen: boolean;
  onMeetingComposerOpenChange: Dispatch<SetStateAction<boolean>>;
  calendarMonth: Date;
  onCalendarMonthChange: Dispatch<SetStateAction<Date>>;
  meetingFilters: { status: string; type: string; date: string };
  onMeetingFiltersChange: Dispatch<SetStateAction<{ status: string; type: string; date: string }>>;
  onOpenMeetingComposerForDate: (
    date: Date,
    preset?: { contactId?: string | null; dealId?: string | null; accountId?: string | null },
  ) => void;
  onOpenScheduler: (target: {
    contactId?: string | null;
    dealId?: string | null;
    accountId?: string | null;
    label: string;
  }) => void;
  taskForm: TaskFormState;
  onTaskFormChange: Dispatch<SetStateAction<TaskFormState>>;
  onCreateTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCompleteTask: (taskId: string) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  taskSubmitting: boolean;
  selectedTaskId: string | null;
  onSelectTask: Dispatch<SetStateAction<string | null>>;
  taskFilters: { status: string; priority: string };
  onTaskFiltersChange: Dispatch<SetStateAction<{ status: string; priority: string }>>;
  automationForm: AutomationRuleFormState;
  onAutomationFormChange: Dispatch<SetStateAction<AutomationRuleFormState>>;
  onCreateAutomation: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onToggleAutomation: (ruleId: string) => Promise<void>;
  onEditAutomation: (rule: AutomationRule) => void;
  onCancelAutomationEdit: () => void;
  onDeleteAutomation: (ruleId: string) => Promise<void>;
  editingAutomationId: string | null;
  automationSubmitting: boolean;
  onCreateNote: (entityType: string, entityId: string, body: string) => Promise<any>;
  onDeleteNote: (noteId: string) => Promise<void>;
  contactResearch: ResearchInsight | null;
  contactResearchLoading: string | null;
  onContactResearch: (contactId: string) => Promise<void>;
  accountResearch: ResearchInsight | null;
  accountResearchLoading: string | null;
  onAccountResearch: (accountId: string) => Promise<void>;
  nurtureStatus: NurtureStatus;
  onMarkNotificationRead: (id: string) => Promise<void>;
  onMarkAllNotificationsRead: () => Promise<void>;
};

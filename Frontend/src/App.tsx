import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { useAuth0 } from "@auth0/auth0-react";
import "./App.css";
import {
  type AccountDetail,
  type Approval,
  type Contact,
  type ContactCreateInput,
  type BulkOperationResult,
  type DealLineItem,
  type DealLineItemCreateInput,
  type DealStakeholder,
  type DealStakeholderCreateInput,
  type DealTimelineItem,
  type Deal,
  type DealCreateInput,
  type EmailDraft,
  type ForecastResponse,
  type GraphRun,
  type SwarmEvent,
  type SwarmJobsResponse,
  type SwarmStatusResponse,
  type LeadSummary,
  type Me,
  type NurtureStatus,
  type Product,
  type ProductCreateInput,
  type ProposalDraft,
  type SchedulerSuggestedSlot,
  type ReportsSummary,
  type ReportsPipeline,
  type ReportsPerformance,
  type ReportFilter,
  type ReportPeriod,
  type SchedulerAvailabilitySummary,
  type Meeting,
  type MeetingCreateInput,
  type TaskCreateInput,
  addDealLineItem,
  addDealStakeholder,
  approveApproval,
  bulkDeleteContacts,
  bulkDeleteProducts,
  bulkUpdateDealsStage,
  createContact,
  createDeal,
  createProduct,
  deleteDealLineItem,
  deleteDealStakeholder,
  deleteContact,
  deleteProduct,
  fetchAccountDetail,
  fetchAccounts,
  fetchApprovals,
  fetchApprovalHistory,
  fetchAuditLogs,
  fetchContacts,
  fetchDeals,
  fetchDealTimeline,
  fetchDraftEmail,
  fetchFollowupAgentLogs,
  fetchFollowupGraphRuns,
  fetchFollowupGraphRun,
  fetchForecast,
  fetchReportsSummary,
  fetchReportsPipeline,
  fetchReportsPerformance,
  fetchSwarmEvents,
  fetchSwarmJobs,
  fetchSwarmStatus,
  fetchLeadSummary,
  fetchMe,
  fetchNurtureStatus,
  fetchProducts,
  fetchStages,
  fetchTeams,
  generateNurtureNow,
  generateDealProposal,
  getWebSocketUrl,
  importAccountsCsv,
  importContactsCsv,
  importProductsCsv,
  rejectApproval,
  retryApprovalSend,
  runNurturerScan,
  runSwarmAgent,
  updateDealLineItem,
  updateDealStakeholder,
  updateDealStage,
  updateProduct,
  updateApprovalDraft,
  cancelApprovalSend,
  downloadCsv,
  fetchCopilotChat,
  fetchMeetings,
  fetchUpcomingMeetings,
  suggestMeetingSlots,
  bookSuggestedMeeting,
  createMeeting,
  updateMeeting,
  completeMeeting,
  cancelMeeting,
  deleteMeeting,
  fetchTasks,
  fetchMyTasks,
  createTask,
  updateTask,
  completeTask,
  deleteTask,
  createNote,
  deleteNote,
  fetchActivityFeed,
  type AutomationRule,
  type AutomationRuleCreateInput,
  type AutomationRuleUpdateInput,
  fetchAutomations,
  createAutomation,
  updateAutomation,
  toggleAutomation,
  deleteAutomation,
  type ResearchInsight,
  fetchContactResearch,
  fetchAccountResearch,
  fetchEmails,
  fetchSmsHistory,
  sendSms,
  fetchNotifications,

  markNotificationRead,
  markAllNotificationsRead,
  type ImportResult,
} from "./lib/api";

import {
  getPageTitle,
  formatDateForInput,
} from "./lib/formatters";
import {
  type Page,
  type DataState,
  type ContactFormState,
  type DealFormState,
  type AutomationRuleFormState,
  type ProductFormState,
  type LineItemFormState,
  type StakeholderFormState,
  type MeetingFormState,
  type TaskFormState,
  type ImportEntity,
  type PageProps,
  NAV_ITEMS,
  INITIAL_DATA,
  INITIAL_MEETING_FORM,
  INITIAL_AUTOMATION_FORM,
  INITIAL_TASK_FORM,
  INITIAL_CONTACT_FORM,
  INITIAL_DEAL_FORM,
  INITIAL_PRODUCT_FORM,
  INITIAL_LINE_ITEM_FORM,
  INITIAL_STAKEHOLDER_FORM,
  FRONTEND_SESSION_KEY,
  AUTH0_PLACEHOLDER_DOMAINS,
  AUTH0_PLACEHOLDER_CLIENT_IDS,
  DEFAULT_AVATAR,
} from "./types/appState";
import { PublicAuthPage } from "./components/PublicAuthPage";
import { ErrorState } from "./components/ErrorState";
import { LoadingScreen } from "./components/LoadingScreen";
import { MeetingComposerModal } from "./components/MeetingComposerModal";
import { SchedulerModal } from "./components/SchedulerModal";
import { LeadSummaryModal } from "./components/LeadSummaryModal";
import { EmailDraftModal } from "./components/EmailDraftModal";
import { ApprovalDraftModal } from "./components/ApprovalDraftModal";
import { ImportResultModal } from "./components/ImportResultModal";
import { ProposalDraftModal } from "./components/ProposalDraftModal";
import { DashboardPage } from "./pages/DashboardPage";
import { ReportsPage } from "./pages/ReportsPage";
import { TasksPage } from "./pages/TasksPage";
import { ActivityFeedPage } from "./pages/ActivityFeedPage";
import { CalendarPage } from "./pages/CalendarPage";
import { EmailsPage } from "./pages/EmailsPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { MessagesPage } from "./pages/MessagesPage";
import { ImportExportPage } from "./pages/ImportExportPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { ApprovalHistoryPage } from "./pages/ApprovalHistoryPage";
import { GraphRunsPage } from "./pages/GraphRunsPage";
import { AccountsPage } from "./pages/AccountsPage";
import { ContactsPage } from "./pages/ContactsPage";
import { ProductsPage } from "./pages/ProductsPage";
import { DealsPage } from "./pages/DealsPage";
import { PipelinePage } from "./pages/PipelinePage";

function App() {
  const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN ?? "";
  const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID ?? "";
  const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE ?? "";
  const isAuth0Configured =
    !AUTH0_PLACEHOLDER_DOMAINS.has(auth0Domain) && !AUTH0_PLACEHOLDER_CLIENT_IDS.has(auth0ClientId);
  const {
    isLoading: auth0Loading,
    isAuthenticated,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
    user,
  } = useAuth0();
  const [activePage, setActivePage] = useState<Page>("dashboard");
  const [data, setData] = useState<DataState>(INITIAL_DATA);
  const [authState, setAuthState] = useState<"checking" | "authenticated" | "logged_out">("checking");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [demoAvailable, setDemoAvailable] = useState(false);
  const [contactForm, setContactForm] = useState<ContactFormState>(INITIAL_CONTACT_FORM);
  const [dealForm, setDealForm] = useState<DealFormState>(INITIAL_DEAL_FORM);
  const [productForm, setProductForm] = useState<ProductFormState>(INITIAL_PRODUCT_FORM);
  const [meetingForm, setMeetingForm] = useState<MeetingFormState>(INITIAL_MEETING_FORM);
  const [taskForm, setTaskForm] = useState<TaskFormState>(INITIAL_TASK_FORM);
  const [contactSubmitting, setContactSubmitting] = useState(false);
  const [dealSubmitting, setDealSubmitting] = useState(false);
  const [productSubmitting, setProductSubmitting] = useState(false);
  const [meetingSubmitting, setMeetingSubmitting] = useState(false);
  const [taskSubmitting, setTaskSubmitting] = useState(false);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [meetingComposerOpen, setMeetingComposerOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => new Date());
  const [schedulerModalOpen, setSchedulerModalOpen] = useState(false);
  const [schedulerTarget, setSchedulerTarget] = useState<{
    contactId: string | null;
    dealId: string | null;
    accountId: string | null;
    label: string;
  } | null>(null);
  const [schedulerDuration, setSchedulerDuration] = useState("30");
  const [schedulerSuggestions, setSchedulerSuggestions] = useState<SchedulerSuggestedSlot[]>([]);
  const [schedulerLoading, setSchedulerLoading] = useState(false);
  const [schedulerBookingStart, setSchedulerBookingStart] = useState<string | null>(null);
  const [schedulerSelectedStart, setSchedulerSelectedStart] = useState<string | null>(null);
  const [schedulerMessage, setSchedulerMessage] = useState<string | null>(null);
  const [schedulerYourAvailability, setSchedulerYourAvailability] = useState<SchedulerAvailabilitySummary | null>(null);
  const [schedulerCustomerAvailability, setSchedulerCustomerAvailability] =
    useState<SchedulerAvailabilitySummary | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [meetingFilters, setMeetingFilters] = useState({ status: "", type: "", date: "" });
  const [taskFilters, setTaskFilters] = useState({ status: "", priority: "" });
  const [automationForm, setAutomationForm] = useState<AutomationRuleFormState>(INITIAL_AUTOMATION_FORM);
  const [editingAutomationId, setEditingAutomationId] = useState<string | null>(null);
  const [automationSubmitting, setAutomationSubmitting] = useState(false);
  const [pageMessage, setPageMessage] = useState<string | null>(null);
  const [summaryLoadingId, setSummaryLoadingId] = useState<string | null>(null);
  const [summaryContact, setSummaryContact] = useState<Contact | null>(null);
  const [leadSummary, setLeadSummary] = useState<LeadSummary | null>(null);
  const [draftLoadingId, setDraftLoadingId] = useState<string | null>(null);
  const [draftContact, setDraftContact] = useState<Contact | null>(null);
  const [emailDraft, setEmailDraft] = useState<EmailDraft | null>(null);
  const [approvalSubmittingId, setApprovalSubmittingId] = useState<string | null>(null);
  const [approvalDraft, setApprovalDraft] = useState<Approval | null>(null);
  const [approvalDraftSaving, setApprovalDraftSaving] = useState(false);
  const [runningContactAgentId, setRunningContactAgentId] = useState<string | null>(null);
  const [editingProductId, setEditingProductId] = useState<string | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [accountDetail, setAccountDetail] = useState<AccountDetail | null>(null);
  const [accountDetailLoading, setAccountDetailLoading] = useState(false);
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);
  const [lineItemForm, setLineItemForm] = useState<LineItemFormState>(INITIAL_LINE_ITEM_FORM);
  const [stakeholderForm, setStakeholderForm] = useState<StakeholderFormState>(INITIAL_STAKEHOLDER_FORM);
  const [lineItemSubmitting, setLineItemSubmitting] = useState(false);
  const [stakeholderSubmitting, setStakeholderSubmitting] = useState(false);
  const [lineItemUpdatingId, setLineItemUpdatingId] = useState<string | null>(null);
  const [stakeholderUpdatingId, setStakeholderUpdatingId] = useState<string | null>(null);
  const [lineItemDrafts, setLineItemDrafts] = useState<Record<string, { quantity: string; unit_price: string }>>({});
  const [proposalLoading, setProposalLoading] = useState(false);
  const [proposalDraft, setProposalDraft] = useState<ProposalDraft | null>(null);
  const [proposalDeal, setProposalDeal] = useState<Deal | null>(null);
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([]);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [selectedDealIds, setSelectedDealIds] = useState<string[]>([]);
  const [dealTimeline, setDealTimeline] = useState<DealTimelineItem[]>([]);
  const [dealTimelineLoading, setDealTimelineLoading] = useState(false);
  const [bulkStageId, setBulkStageId] = useState("");
  const [bulkSubmitting, setBulkSubmitting] = useState<"contacts" | "products" | "deals" | null>(null);
  const [importSubmitting, setImportSubmitting] = useState<ImportEntity | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [reportsSummary, setReportsSummary] = useState<ReportsSummary | null>(null);
  const [reportsPipeline, setReportsPipeline] = useState<ReportsPipeline | null>(null);
  const [reportsPerformance, setReportsPerformance] = useState<ReportsPerformance | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsPeriod, setReportsPeriod] = useState<ReportPeriod>("this_month");
  const [reportsCustomRange, setReportsCustomRange] = useState<{ startDate: string; endDate: string }>({
    startDate: "",
    endDate: "",
  });
  const [nurtureStatus, setNurtureStatus] = useState<NurtureStatus>({
    pending_count: 0,
    pending_contact_ids: [],
    pending_deal_ids: [],
    pending_items: [],
  });
  const [swarmStatus, setSwarmStatus] = useState<SwarmStatusResponse | null>(null);
  const [swarmEvents, setSwarmEvents] = useState<SwarmEvent[]>([]);
  const [swarmJobs, setSwarmJobs] = useState<SwarmJobsResponse | null>(null);
  const [swarmLoading, setSwarmLoading] = useState(false);
  const [runningSwarmAgents, setRunningSwarmAgents] = useState<Record<string, boolean>>({});
  const [selectedGraphRunId, setSelectedGraphRunId] = useState<string | null>(null);
  const [selectedGraphRun, setSelectedGraphRun] = useState<GraphRun | null>(null);
  const [selectedGraphRunLoading, setSelectedGraphRunLoading] = useState(false);
  const [liveStatus, setLiveStatus] = useState<"live" | "reconnecting">("reconnecting");
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotInput, setCopilotInput] = useState("");
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotHistory, setCopilotHistory] = useState<Array<{ role: "user" | "ai"; content: string; suggestions?: string[] }>>([]);
  const [contactResearch, setContactResearch] = useState<ResearchInsight | null>(null);
  const [contactResearchLoading, setContactResearchLoading] = useState<string | null>(null);
  const [accountResearch, setAccountResearch] = useState<ResearchInsight | null>(null);
  const [accountResearchLoading, setAccountResearchLoading] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const nurturerAutoRanRef = useRef(false);

  function persistFrontendSession(state: "authenticated" | "logged_out") {
    if (state === "authenticated") {
      window.localStorage.setItem(FRONTEND_SESSION_KEY, state);
      return;
    }

    window.localStorage.removeItem(FRONTEND_SESSION_KEY);
  }

  function clearRealtimeResources() {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setLiveStatus("reconnecting");
    setToastMessage(null);
  }

  function showAppToast(message: string) {
    setToastMessage(message);
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => {
      setToastMessage(null);
      toastTimerRef.current = null;
    }, 4000);
  }

  async function loadData(currentMe?: Me) {
    const me = currentMe ?? data.me;
    if (!me) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const isAdmin = me.role === "admin";
      const [teams, contacts, accounts, products, deals, stages, approvals, approvalHistory, nurture, auditLogs, followupLogs, workflowRuns, meetings, upcomingMeetings, tasks, myTasks, activityFeed, automations, smsMessages, emails, notifications] = await Promise.all([
        fetchTeams(),
        fetchContacts(),
        fetchAccounts(),
        fetchProducts(),
        fetchDeals(),
        fetchStages(),
        fetchApprovals(),
        fetchApprovalHistory(),
        fetchNurtureStatus(),
        isAdmin ? fetchAuditLogs() : Promise.resolve([]),
        isAdmin ? fetchFollowupAgentLogs() : Promise.resolve([]),
        isAdmin ? fetchFollowupGraphRuns() : Promise.resolve([]),
        fetchMeetings(),
        fetchUpcomingMeetings(),
        fetchTasks(),
        fetchMyTasks(),
        fetchActivityFeed(),
        fetchAutomations(),
        fetchSmsHistory(),
        fetchEmails(),
        fetchNotifications(),
      ]);

      setData({
        me,
        teams,
        contacts,
        accounts,
        products,
        deals,
        stages,
        approvals,
        approvalHistory,
        auditLogs,
        followupLogs,
        workflowRuns,
        meetings,
        upcomingMeetings,
        tasks,
        myTasks,
        activityFeed,
        automations,
        smsMessages,
        emails,
        notifications,
      });
      setNurtureStatus(nurture);
      setDealForm((current) => ({
        ...current,
        stage_id: current.stage_id || stages.find((stage) => stage.name === "Lead")?.id || stages[0]?.id || "",
      }));
      setLineItemForm((current) => ({
        ...current,
        product_id: current.product_id || products[0]?.id || "",
      }));
      setStakeholderForm((current) => ({
        ...current,
        contact_id: current.contact_id || contacts[0]?.id || "",
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load CRM data.");
    } finally {
      setLoading(false);
    }
  }

  async function loadForecastInsights() {
    if (authState !== "authenticated" || !data.me || data.me.role === "rep") {
      return;
    }

    setForecastLoading(true);
    setError(null);
    try {
      const result = await fetchForecast();
      setForecast(result);
      setForecastLoading(false);
    } catch (forecastError) {
      setError(forecastError instanceof Error ? forecastError.message : "Failed to load manager insights.");
      // Backoff for 30 seconds on failure to prevent API spam loop
      setTimeout(() => {
        setForecastLoading(false);
      }, 30000);
    }
  }

  async function handleRunSwarmAgent(agentName: string) {
    setRunningSwarmAgents((current) => ({ ...current, [agentName]: true }));
    setError(null);
    try {
      const result = await runSwarmAgent(agentName);
      showAppToast(result.status === "failed" ? `${agentName} failed` : `${agentName} completed`);
      setSwarmStatus(await fetchSwarmStatus());
      setSwarmEvents(await fetchSwarmEvents());
      setSwarmJobs(await fetchSwarmJobs());
      await loadData();
    } catch (runError) {
      showAppToast(runError instanceof Error ? runError.message : `${agentName} failed`);
      setError(runError instanceof Error ? runError.message : `${agentName} failed.`);
    } finally {
      setRunningSwarmAgents((current) => ({ ...current, [agentName]: false }));
    }
  }

  function getReportFilter(period: ReportPeriod = reportsPeriod): ReportFilter {
    return {
      period,
      startDate: period === "custom" ? reportsCustomRange.startDate : undefined,
      endDate: period === "custom" ? reportsCustomRange.endDate : undefined,
    };
  }

  async function loadReports(period: ReportPeriod = reportsPeriod) {
    if (authState !== "authenticated" || !data.me || data.me.role === "rep") {
      return;
    }

    setReportsLoading(true);
    setError(null);
    try {
      const filter = getReportFilter(period);
      const [summary, pipeline, performance] = await Promise.all([
        fetchReportsSummary(filter),
        fetchReportsPipeline(filter),
        fetchReportsPerformance(filter),
      ]);
      setReportsSummary(summary);
      setReportsPipeline(pipeline);
      setReportsPerformance(performance);
    } catch (reportsError) {
      setError(reportsError instanceof Error ? reportsError.message : "Failed to load reports.");
    } finally {
      setReportsLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function initializeSession() {
      if (auth0Loading) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        if (isAuthenticated) {
          const token = await getAccessTokenSilently({
            authorizationParams: {
              audience: auth0Audience || "https://timesheet-api.example.com",
            },
          });
          window.localStorage.setItem("auth_token", token);
          setAuthState("authenticated");
          persistFrontendSession("authenticated");
          setAuthMessage(null);
        } else {
          window.localStorage.removeItem("auth_token");
        }

        const me = await fetchMe();
        if (cancelled) {
          return;
        }
        setDemoAvailable(me.auth_disabled);
        setData((current) => ({ ...current, me }));
        setAuthState("authenticated");
        persistFrontendSession("authenticated");
        setAuthMessage(null);
        await loadData(me);
      } catch (sessionError) {
        if (cancelled) {
          return;
        }
        if (!isAuthenticated) {
          window.localStorage.removeItem("auth_token");
          setAuthState("logged_out");
          setData(INITIAL_DATA);
        } else {
          console.error("Backend data fetch failed, but user remains authenticated via Auth0:", sessionError);
          const optimisticMe: Me = {
            user_id: user?.sub || "pending",
            email: user?.email || "",
            team_id: "00000000-0000-0000-0000-000000000000",
            team_name: "My Workspace",
            role: "admin",
            full_name: user?.name || null,
            auth_disabled: false,
          };
          setData((current) => ({ ...current, me: optimisticMe }));
          setAuthState("authenticated");
          persistFrontendSession("authenticated");
        }
        setLoading(false);
        setForecast(null);
        setNurtureStatus({
          pending_count: 0,
          pending_contact_ids: [],
          pending_deal_ids: [],
          pending_items: [],
        });
        nurturerAutoRanRef.current = false;
        if (isAuthenticated) {
          setAuthMessage(sessionError instanceof Error ? sessionError.message : "Unable to load workspace data.");
        }
      }
    }

    void initializeSession();
    return () => {
      cancelled = true;
    };
  }, [auth0Audience, auth0Loading, getAccessTokenSilently, isAuthenticated]);

  useEffect(() => {
    if (authState !== "authenticated" || !data.me) {
      clearRealtimeResources();
      return;
    }
    const authContext = data.me;

    let disposed = false;
    let reconnectAttempts = 0;

    function clearReconnectTimer() {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }

    function scheduleReconnect() {
      if (disposed || reconnectTimerRef.current !== null) {
        return;
      }

      setLiveStatus("reconnecting");
      const backoffTimes = [5000, 10000, 20000];
      const delay = reconnectAttempts < backoffTimes.length 
        ? backoffTimes[reconnectAttempts] 
        : 30000;
      
      reconnectAttempts++;

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        if (authState === "authenticated") {
          connect();
        }
      }, delay);
    }

    function showToast(message: string) {
      setToastMessage(message);
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
      }
      toastTimerRef.current = window.setTimeout(() => {
        setToastMessage(null);
        toastTimerRef.current = null;
      }, 4000);
    }

    function connect() {
      if (disposed) {
        return;
      }

      try {
        const token = authContext.auth_disabled ? null : window.localStorage.getItem("auth_token");
        const socket = new WebSocket(getWebSocketUrl(token));
        socketRef.current = socket;

        socket.onopen = () => {
          if (disposed) {
            socket.close();
            return;
          }
          reconnectAttempts = 0;
          clearReconnectTimer();
          setLiveStatus("live");
        };

        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as {
              type?: string;
              name?: string;
              payload?: Record<string, unknown>;
            };

            if (message.type !== "event" || !message.name) {
              return;
            }

            if (message.name === "approval.created") {
              showToast("New AI approval ready");
            }

            if (
              message.name === "approval.created" ||
              message.name === "approval.updated" ||
              message.name === "agent_run.created" ||
              message.name === "agent_run.completed" ||
              message.name === "deal.stage_changed" ||
              message.name === "sms.received" ||
              message.name === "sms.updated" ||
              message.name === "meeting.created" ||
              message.name === "meeting.updated" ||
              message.name === "meeting.completed" ||
              message.name === "meeting.cancelled" ||
              message.name === "meeting.deleted"
            ) {
              void loadData();
            }
          } catch {
            // Ignore malformed messages and keep the socket alive.
          }
        };

        socket.onclose = () => {
          if (socketRef.current === socket) {
            socketRef.current = null;
          }
          if (!disposed) {
            scheduleReconnect();
          }
        };

        socket.onerror = () => {
          socket.close();
        };
      } catch {
        scheduleReconnect();
      }
    }

    connect();

    return () => {
      disposed = true;
      clearReconnectTimer();
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
        toastTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [data.me?.team_id, data.me?.auth_disabled]);

  useEffect(() => {
    if (authState === "authenticated" && activePage === "dashboard" && forecast === null && !forecastLoading) {
      void loadForecastInsights();
    }
  }, [activePage, authState, forecast, forecastLoading, data.me?.role]);

  useEffect(() => {
    if (
      authState === "authenticated" &&
      activePage === "reports" &&
      data.me?.role !== "rep" &&
      reportsSummary === null &&
      !reportsLoading
    ) {
      void loadReports(reportsPeriod);
    }
  }, [activePage, authState, data.me?.role, reportsSummary, reportsLoading, reportsPeriod, reportsCustomRange.startDate, reportsCustomRange.endDate]);

  useEffect(() => {
    if (authState === "authenticated" && activePage === "reports" && data.me?.role !== "rep") {
      void loadReports(reportsPeriod);
    }
  }, [reportsPeriod, reportsCustomRange.startDate, reportsCustomRange.endDate]);

  useEffect(() => {
    // Only run the nurturer scan once we are authenticated, on the dashboard, 
    // and we have successfully loaded our profile data (me) to provide context.
    if (authState !== "authenticated" || activePage !== "dashboard" || !data.me || nurturerAutoRanRef.current) {
      return;
    }

    nurturerAutoRanRef.current = true;
    void (async () => {
      try {
        await runNurturerScan();
        await loadData();
      } catch {
        // Keep the dashboard usable even if nurture scan fails.
      }
    })();
  }, [activePage, authState, data.me]);

  useEffect(() => {
    if (authState !== "authenticated" || activePage !== "graph-runs" || data.me?.role !== "admin") {
      return;
    }

    let cancelled = false;
    let timerId: number | null = null;

    async function refreshRuns() {
      if (!cancelled) {
        setSwarmLoading(true);
      }
      try {
        const [runs, statusSnapshot, eventsSnapshot, jobsSnapshot] = await Promise.all([
          fetchFollowupGraphRuns(),
          fetchSwarmStatus(),
          fetchSwarmEvents(),
          fetchSwarmJobs(),
        ]);
        if (!cancelled) {
          setData((current) => ({ ...current, workflowRuns: runs }));
          setSwarmStatus(statusSnapshot);
          setSwarmEvents(eventsSnapshot);
          setSwarmJobs(jobsSnapshot);
        }
      } catch (refreshError) {
        if (!cancelled) {
          setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh swarm console.");
        }
      } finally {
        if (!cancelled) {
          setSwarmLoading(false);
          timerId = window.setTimeout(() => {
            void refreshRuns();
          }, 5000);
        }
      }
    }

    void refreshRuns();

    return () => {
      cancelled = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
    };
  }, [activePage, authState, data.me?.role]);

  useEffect(() => {
    if (!selectedGraphRunId || authState !== "authenticated" || data.me?.role !== "admin") {
      setSelectedGraphRun(null);
      setSelectedGraphRunLoading(false);
      return;
    }

    const currentRunId = selectedGraphRunId;
    let cancelled = false;
    setSelectedGraphRunLoading(true);

    async function loadGraphRunDetail() {
      try {
        const run = await fetchFollowupGraphRun(currentRunId);
        if (!cancelled) {
          setSelectedGraphRun(run);
        }
      } catch (detailError) {
        if (!cancelled) {
          setError(detailError instanceof Error ? detailError.message : "Failed to load run detail.");
          setSelectedGraphRun(null);
        }
      } finally {
        if (!cancelled) {
          setSelectedGraphRunLoading(false);
        }
      }
    }

    void loadGraphRunDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedGraphRunId, authState, data.me?.role, data.workflowRuns]);

  const availableNavItems = useMemo(() => {
    // If authenticated via Auth0 but backend data hasn't loaded yet, default to admin to show all features
    const role = data.me?.role || (isAuthenticated ? "admin" : null);
    
    if (!role) {
      return [] as Array<{ id: Page; label: string }>;
    }
    if (role === "admin") {
      return NAV_ITEMS;
    }
    if (role === "manager") {
      return NAV_ITEMS;
    }
    return NAV_ITEMS.filter(
      (item) =>
        item.id !== "graph-runs" &&
        item.id !== "approval-history" &&
        item.id !== "reports",
    );
  }, [data.me?.role, isAuthenticated]);

  useEffect(() => {
    if (authState !== "authenticated" || availableNavItems.length === 0) {
      return;
    }
    if (!availableNavItems.some((item) => item.id === activePage)) {
      setActivePage(availableNavItems[0].id);
    }
  }, [activePage, authState, availableNavItems]);

  async function handleCreateContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageMessage(null);

    if (authState !== "authenticated") {
      setError("Please log in before creating contacts.");
      return;
    }

    setContactSubmitting(true);
    try {
      const payload: ContactCreateInput = {
        first_name: contactForm.first_name.trim(),
        last_name: contactForm.last_name.trim(),
        email: contactForm.email.trim(),
        phone: contactForm.phone.trim() || null,
        consent_sms: contactForm.consent_sms,
        consent_email: contactForm.consent_email,
        job_title: contactForm.job_title.trim() || undefined,
        description: contactForm.description.trim() || undefined,
        account_id: contactForm.account_id || undefined,
        preferred_timezone: contactForm.preferred_timezone.trim() || null,
        working_days: contactForm.working_days.trim() || null,
        working_hours_start: contactForm.working_hours_start.trim() || null,
        working_hours_end: contactForm.working_hours_end.trim() || null,
        preferred_meeting_windows: contactForm.preferred_meeting_windows.trim() || null,
        blocked_days: contactForm.blocked_days.trim() || null,
      };

      await createContact(payload);
      setContactForm(INITIAL_CONTACT_FORM);
      setPageMessage("Contact created. Draft email queued for approval.");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create contact.");
    } finally {
      setContactSubmitting(false);
    }
  }

  async function handleDeleteContact(contactId: string) {
    setPageMessage(null);
    try {
      await deleteContact(contactId);
      setPageMessage("Contact deleted.");
      await loadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete contact.");
    }
  }

  async function handleCreateDeal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageMessage(null);

    const ownerUserId = data.deals[0]?.owner?.id ?? null;
    if (authState !== "authenticated") {
      setError("Please log in before creating deals.");
      return;
    }

    setDealSubmitting(true);
    try {
      const payload: DealCreateInput = {
        name: dealForm.name.trim(),
        amount: dealForm.amount ? Number(dealForm.amount) : null,
        currency: dealForm.currency.trim().toUpperCase() || "USD",
        probability: dealForm.probability ? Number(dealForm.probability) : null,
        expected_close_date: dealForm.expected_close_date || null,
        owner_user_id: ownerUserId,
        stage_id: dealForm.stage_id,
        contact_id: dealForm.contact_id || null,
        account_id: dealForm.account_id || null,
      };

      await createDeal(payload);
      setDealForm({
        ...INITIAL_DEAL_FORM,
        stage_id: data.stages.find((stage) => stage.name === "Lead")?.id || data.stages[0]?.id || "",
      });
      setPageMessage("Deal created.");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create deal.");
    } finally {
      setDealSubmitting(false);
    }
  }

  async function handleCreateOrUpdateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageMessage(null);
    setProductSubmitting(true);

    try {
      const payload: ProductCreateInput = {
        name: productForm.name.trim(),
        sku: productForm.sku.trim(),
        description: productForm.description.trim() || null,
        price: Number(productForm.price),
        currency: productForm.currency.trim().toUpperCase() || "USD",
        custom_fields: {},
      };

      if (editingProductId) {
        await updateProduct(editingProductId, payload);
        setPageMessage("Product updated.");
      } else {
        await createProduct(payload);
        setPageMessage("Product created.");
      }

      setEditingProductId(null);
      setProductForm(INITIAL_PRODUCT_FORM);
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save product.");
    } finally {
      setProductSubmitting(false);
    }
  }

  function handleEditProduct(product: Product) {
    setEditingProductId(product.id);
    setProductForm({
      name: product.name,
      sku: product.sku,
      description: product.description ?? "",
      price: String(product.price),
      currency: product.currency,
    });
    setActivePage("products");
  }

  async function handleDeleteProduct(productId: string) {
    setPageMessage(null);
    try {
      await deleteProduct(productId);
      if (editingProductId === productId) {
        setEditingProductId(null);
        setProductForm(INITIAL_PRODUCT_FORM);
      }
      setPageMessage("Product deleted.");
      await loadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete product.");
    }
  }

  async function handleMoveDealStage(dealId: string, stageId: string) {
    setPageMessage(null);
    try {
      await updateDealStage(dealId, stageId);
      setPageMessage("Deal stage updated.");
      await loadData();
    } catch (moveError) {
      setError(moveError instanceof Error ? moveError.message : "Failed to update deal stage.");
      throw moveError;
    }
  }

  function handleOpenDealFromPipeline(dealId: string) {
    setSelectedDealId(dealId);
    setActivePage("deals");
  }

  async function handleAddLineItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDeal) {
      setError("Choose a deal before adding line items.");
      return;
    }

    setLineItemSubmitting(true);
    setPageMessage(null);
    try {
      const payload: DealLineItemCreateInput = {
        product_id: lineItemForm.product_id,
        quantity: Number(lineItemForm.quantity),
        unit_price: lineItemForm.unit_price ? Number(lineItemForm.unit_price) : undefined,
      };
      await addDealLineItem(selectedDeal.id, payload);
      setLineItemForm((current) => ({ ...INITIAL_LINE_ITEM_FORM, product_id: current.product_id || data.products[0]?.id || "" }));
      setPageMessage("Line item added.");
      await loadData();
    } catch (lineItemError) {
      setError(lineItemError instanceof Error ? lineItemError.message : "Failed to add line item.");
    } finally {
      setLineItemSubmitting(false);
    }
  }

  async function handleUpdateLineItem(lineItem: DealLineItem) {
    if (!selectedDeal) {
      return;
    }

    const draft = lineItemDrafts[lineItem.id];
    if (!draft) {
      return;
    }

    setLineItemUpdatingId(lineItem.id);
    setPageMessage(null);
    try {
      await updateDealLineItem(selectedDeal.id, lineItem.id, {
        quantity: Number(draft.quantity),
        unit_price: Number(draft.unit_price),
      });
      setPageMessage("Line item updated.");
      await loadData();
    } catch (lineItemError) {
      setError(lineItemError instanceof Error ? lineItemError.message : "Failed to update line item.");
    } finally {
      setLineItemUpdatingId(null);
    }
  }

  async function handleDeleteLineItem(lineItemId: string) {
    if (!selectedDeal) {
      return;
    }

    setLineItemUpdatingId(lineItemId);
    setPageMessage(null);
    try {
      await deleteDealLineItem(selectedDeal.id, lineItemId);
      setPageMessage("Line item removed.");
      await loadData();
    } catch (lineItemError) {
      setError(lineItemError instanceof Error ? lineItemError.message : "Failed to remove line item.");
    } finally {
      setLineItemUpdatingId(null);
    }
  }

  async function handleAddStakeholder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDeal) {
      setError("Choose a deal before adding stakeholders.");
      return;
    }

    setStakeholderSubmitting(true);
    setPageMessage(null);
    try {
      const payload: DealStakeholderCreateInput = {
        contact_id: stakeholderForm.contact_id,
        role: stakeholderForm.role,
      };
      await addDealStakeholder(selectedDeal.id, payload);
      setStakeholderForm((current) => ({
        ...current,
        contact_id: "",
      }));
      setPageMessage("Stakeholder added.");
      await loadData();
    } catch (stakeholderError) {
      setError(stakeholderError instanceof Error ? stakeholderError.message : "Failed to add stakeholder.");
    } finally {
      setStakeholderSubmitting(false);
    }
  }

  async function handleUpdateStakeholder(stakeholder: DealStakeholder, role: DealStakeholder["role"]) {
    if (!selectedDeal) {
      return;
    }

    setStakeholderUpdatingId(stakeholder.id);
    setPageMessage(null);
    try {
      await updateDealStakeholder(selectedDeal.id, stakeholder.id, { role });
      setPageMessage("Stakeholder role updated.");
      await loadData();
    } catch (stakeholderError) {
      setError(stakeholderError instanceof Error ? stakeholderError.message : "Failed to update stakeholder.");
    } finally {
      setStakeholderUpdatingId(null);
    }
  }

  async function handleDeleteStakeholder(stakeholderId: string) {
    if (!selectedDeal) {
      return;
    }

    setStakeholderUpdatingId(stakeholderId);
    setPageMessage(null);
    try {
      await deleteDealStakeholder(selectedDeal.id, stakeholderId);
      setPageMessage("Stakeholder removed.");
      await loadData();
    } catch (stakeholderError) {
      setError(stakeholderError instanceof Error ? stakeholderError.message : "Failed to remove stakeholder.");
    } finally {
      setStakeholderUpdatingId(null);
    }
  }

  async function handleGenerateProposal() {
    if (!selectedDeal) {
      setError("Choose a deal before generating a proposal.");
      return;
    }

    setProposalLoading(true);
    setProposalDraft(null);
    setProposalDeal(selectedDeal);
    setPageMessage(null);
    try {
      const draft = await generateDealProposal(selectedDeal.id);
      setProposalDraft(draft);
      setPageMessage("Proposal draft generated.");
      await loadData();
    } catch (proposalError) {
      setError(proposalError instanceof Error ? proposalError.message : "Failed to generate proposal.");
      setProposalDeal(null);
    } finally {
      setProposalLoading(false);
    }
  }

  async function handleBulkDeleteContacts() {
    if (selectedContactIds.length === 0) {
      return;
    }

    setBulkSubmitting("contacts");
    setPageMessage(null);
    try {
      const result: BulkOperationResult = await bulkDeleteContacts(selectedContactIds);
      setSelectedContactIds([]);
      setPageMessage(`Deleted ${result.processed} contacts.`);
      await loadData();
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : "Failed to bulk delete contacts.");
    } finally {
      setBulkSubmitting(null);
    }
  }

  async function handleBulkDeleteProducts() {
    if (selectedProductIds.length === 0) {
      return;
    }

    setBulkSubmitting("products");
    setPageMessage(null);
    try {
      const result: BulkOperationResult = await bulkDeleteProducts(selectedProductIds);
      setSelectedProductIds([]);
      setPageMessage(`Deleted ${result.processed} products.`);
      await loadData();
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : "Failed to bulk delete products.");
    } finally {
      setBulkSubmitting(null);
    }
  }

  async function handleBulkMoveDeals() {
    if (selectedDealIds.length === 0 || !bulkStageId) {
      return;
    }

    setBulkSubmitting("deals");
    setPageMessage(null);
    try {
      const result: BulkOperationResult = await bulkUpdateDealsStage(selectedDealIds, bulkStageId);
      setSelectedDealIds([]);
      setPageMessage(`Updated ${result.processed} deals.`);
      await loadData();
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : "Failed to bulk update deals.");
    } finally {
      setBulkSubmitting(null);
    }
  }

  async function handleImport(entity: ImportEntity, file: File | null) {
    if (!file) {
      setError("Choose a CSV file before importing.");
      return;
    }

    setImportSubmitting(entity);
    setPageMessage(null);
    try {
      const result =
        entity === "contacts"
          ? await importContactsCsv(file)
          : entity === "accounts"
            ? await importAccountsCsv(file)
            : await importProductsCsv(file);
      setImportResult(result);
      setPageMessage(`${entity} import complete.`);
      await loadData();
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Failed to import CSV.");
    } finally {
      setImportSubmitting(null);
    }
  }

  async function handleExport(path: string, filename: string) {
    setPageMessage(null);
    try {
      await downloadCsv(path, filename);
      setPageMessage(`${filename} downloaded.`);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Failed to export CSV.");
    }
  }

  async function handleLoadLeadSummary(contact: Contact) {
    setPageMessage(null);
    setSummaryLoadingId(contact.id);
    setSummaryContact(contact);
    setLeadSummary(null);

    try {
      const linkedDeal = data.deals.find((deal) => deal.contact_id === contact.id) ?? null;
      const summary = await fetchLeadSummary(contact.id, linkedDeal?.id ?? null);
      setLeadSummary(summary);
    } catch (summaryError) {
      const msg = summaryError instanceof Error ? summaryError.message : "Failed to load AI summary.";
      const cleanMsg = msg.includes("AI returned") ? "AI was unable to generate a valid summary. Please try again." : msg;
      setError(cleanMsg);
      setSummaryContact(null);
    } finally {
      setSummaryLoadingId(null);
    }
  }

  async function handleLoadEmailDraft(contact: Contact) {
    setPageMessage(null);
    setDraftLoadingId(contact.id);
    setDraftContact(contact);
    setEmailDraft(null);

    try {
      const linkedDeal = data.deals.find((deal) => deal.contact_id === contact.id) ?? null;
      const draft = await fetchDraftEmail(contact.id, linkedDeal?.id ?? null);
      setEmailDraft(draft);
      const approvals = await fetchApprovals();
      setData((current) => ({ ...current, approvals }));
      const matchingApproval = approvals.find(
        (approval) => approval.contact_id === contact.id && approval.status === "pending",
      );
      if (matchingApproval) {
        setApprovalDraft(matchingApproval);
        setDraftContact(null);
        setEmailDraft(null);
      } else {
        setPageMessage("Draft created and added to approvals.");
      }
    } catch (draftError) {
      const msg = draftError instanceof Error ? draftError.message : "Failed to load email draft.";
      const cleanMsg = msg.includes("AI returned") ? "AI was unable to generate a valid draft. Please try again." : msg;
      setError(cleanMsg);
      setDraftContact(null);
    } finally {
      setDraftLoadingId(null);
    }
  }

  async function handleGenerateNurtureNow(target: { contactId?: string | null; dealId?: string | null }) {
    setPageMessage(null);
    try {
      const result = await generateNurtureNow({
        contact_id: target.contactId ?? null,
        deal_id: target.dealId ?? null,
      });
      if (result.status === "created") {
        setPageMessage("Nurture follow-up added to approvals.");
      } else if (result.reason === "recent_nurture_exists") {
        setPageMessage("A nurture suggestion already exists for this record.");
      } else {
        setPageMessage("No nurture suggestion was created.");
      }
      await loadData();
    } catch (nurtureError) {
      setError(nurtureError instanceof Error ? nurtureError.message : "Failed to generate nurture follow-up.");
    }
  }

  async function handleApprove(approvalId: string) {
    setPageMessage(null);
    setApprovalSubmittingId(approvalId);
    try {
      await approveApproval(approvalId);
      setPageMessage("Approval marked approved.");
      if (approvalDraft?.id === approvalId) {
        setApprovalDraft(null);
      }
      await loadData();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Failed to approve draft.");
    } finally {
      setApprovalSubmittingId(null);
    }
  }

  async function handleApproveAndSendSms(approval: Approval) {
    setPageMessage(null);
    setApprovalSubmittingId(approval.id);

    try {
      const contact = data.contacts.find((item) => item.id === approval.contact_id) ?? null;
      if (!contact?.phone) {
        throw new Error("This contact does not have a phone number for SMS delivery.");
      }
      if (!approval.sms_body) {
        throw new Error("No SMS version is available for this draft yet.");
      }

      await approveApproval(approval.id);
      const smsResult = await sendSms({
        to_number: contact.phone,
        body: approval.sms_body,
        contact_id: approval.contact_id,
      });

      if (smsResult.status === "Failed") {
        throw new Error(smsResult.error_detail || "SMS delivery failed.");
      }

      if (approvalDraft?.id === approval.id) {
        setApprovalDraft(null);
      }
      setPageMessage("Approval completed and SMS sent.");
      await loadData();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Failed to approve draft and send SMS.");
    } finally {
      setApprovalSubmittingId(null);
    }
  }

  async function handleReject(approvalId: string) {
    setPageMessage(null);
    setApprovalSubmittingId(approvalId);
    try {
      await rejectApproval(approvalId);
      setPageMessage("Approval marked rejected.");
      if (approvalDraft?.id === approvalId) {
        setApprovalDraft(null);
      }
      await loadData();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Failed to reject draft.");
    } finally {
      setApprovalSubmittingId(null);
    }
  }

  async function handleRetryApprovalSend(approvalId: string) {
    setPageMessage(null);
    setApprovalSubmittingId(approvalId);
    try {
      await retryApprovalSend(approvalId);
      setPageMessage("Email retry queued.");
      await loadData();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Failed to retry email send.");
    } finally {
      setApprovalSubmittingId(null);
    }
  }

  async function handleRunAllContactAgents(contact: Contact) {
    setRunningContactAgentId(contact.id);
    setPageMessage(null);

    try {
      const linkedDeal = data.deals.find((deal) => deal.contact_id === contact.id) ?? null;
      const summary = await fetchLeadSummary(contact.id, linkedDeal?.id ?? null);
      setLeadSummary(summary);

      await fetchDraftEmail(contact.id, linkedDeal?.id ?? null);
      const approvals = await fetchApprovals();
      setData((current) => ({ ...current, approvals }));

      handleOpenScheduler({
        contactId: contact.id,
        dealId: linkedDeal?.id ?? null,
        accountId: contact.account_id,
        label: `${contact.first_name} ${contact.last_name}`,
      });

      const response = await suggestMeetingSlots({
        contact_id: contact.id,
        deal_id: linkedDeal?.id ?? null,
        duration_minutes: 30,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      setSchedulerSuggestions(response.slots);
      setSchedulerSelectedStart(response.slots[0]?.starts_at ?? null);
      setSchedulerMessage(response.message);
      setSchedulerYourAvailability(response.your_availability);
      setSchedulerCustomerAvailability(response.customer_availability);
      setPageMessage("LeadQualifierAgent, NurturerAgent, and SchedulerAgent completed. Approval item created and scheduler opened.");
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Failed to run all contact agents.");
    } finally {
      setRunningContactAgentId(null);
    }
  }

  async function handleCancelApprovalSend(approvalId: string) {
    setPageMessage(null);
    setApprovalSubmittingId(approvalId);
    try {
      await cancelApprovalSend(approvalId);
      setPageMessage("Queued email cancelled.");
      await loadData();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Failed to cancel email send.");
    } finally {
      setApprovalSubmittingId(null);
    }
  }

  async function handleCreateMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageMessage(null);
    if (!data.me?.team_id) return;

    setMeetingSubmitting(true);
    try {
      const payload: MeetingCreateInput = {
        title: meetingForm.title.trim(),
        description: meetingForm.description.trim() || null,
        starts_at: meetingForm.starts_at,
        ends_at: meetingForm.ends_at,
        timezone: meetingForm.timezone,
        meeting_type: meetingForm.meeting_type,
        location: meetingForm.location.trim() || null,
        reminder_minutes: meetingForm.reminder_minutes ? Number(meetingForm.reminder_minutes) : null,
        contact_id: meetingForm.contact_id || null,
        deal_id: meetingForm.deal_id || null,
        account_id: meetingForm.account_id || null,
      };

      if (selectedMeetingId) {
        await updateMeeting(selectedMeetingId, payload);
        setPageMessage("Meeting updated.");
      } else {
        await createMeeting(payload);
        setPageMessage("Meeting scheduled.");
      }

      setMeetingForm(INITIAL_MEETING_FORM);
      setSelectedMeetingId(null);
      setMeetingComposerOpen(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save meeting.");
    } finally {
      setMeetingSubmitting(false);
    }
  }

  async function handleCompleteMeeting(meetingId: string) {
    setPageMessage(null);
    try {
      await completeMeeting(meetingId);
      setPageMessage("Meeting marked completed.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete meeting.");
    }
  }

  async function handleCancelMeeting(meetingId: string) {
    setPageMessage(null);
    try {
      await cancelMeeting(meetingId);
      setPageMessage("Meeting cancelled.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel meeting.");
    }
  }

  async function handleDeleteMeeting(meetingId: string) {
    setPageMessage(null);
    try {
      await deleteMeeting(meetingId);
      setPageMessage("Meeting deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete meeting.");
    }
  }

  function openMeetingComposerForDate(
    date: Date,
    preset?: { contactId?: string | null; dealId?: string | null; accountId?: string | null },
  ) {
    const start = new Date(date);
    start.setHours(10, 0, 0, 0);
    const end = new Date(start);
    end.setMinutes(end.getMinutes() + 30);
    setSelectedMeetingId(null);
    setMeetingForm({
      ...INITIAL_MEETING_FORM,
      starts_at: formatDateForInput(start),
      ends_at: formatDateForInput(end),
      contact_id: preset?.contactId ?? "",
      deal_id: preset?.dealId ?? "",
      account_id: preset?.accountId ?? "",
    });
    setMeetingComposerOpen(true);
  }

  function handleEditMeeting(meeting: Meeting) {
    setSelectedMeetingId(meeting.id);
    setMeetingForm({
      title: meeting.title,
      description: meeting.description ?? "",
      starts_at: meeting.starts_at.slice(0, 16),
      ends_at: meeting.ends_at.slice(0, 16),
      timezone: meeting.timezone,
      meeting_type: meeting.meeting_type,
      location: meeting.location ?? "",
      reminder_minutes: String(meeting.reminder_minutes ?? 15),
      contact_id: meeting.contact_id ?? "",
      deal_id: meeting.deal_id ?? "",
      account_id: meeting.account_id ?? "",
    });
    setMeetingComposerOpen(true);
  }

  function handleOpenScheduler(target: {
    contactId?: string | null;
    dealId?: string | null;
    accountId?: string | null;
    label: string;
  }) {
    setSchedulerTarget({
      contactId: target.contactId ?? null,
      dealId: target.dealId ?? null,
      accountId: target.accountId ?? null,
      label: target.label,
    });
    setSchedulerDuration("30");
    setSchedulerSuggestions([]);
    setSchedulerBookingStart(null);
    setSchedulerSelectedStart(null);
    setSchedulerMessage(null);
    setSchedulerYourAvailability(null);
    setSchedulerCustomerAvailability(null);
    setSchedulerModalOpen(true);
  }

  async function handleSuggestSchedulerSlots() {
    if (!schedulerTarget) return;
    setSchedulerLoading(true);
    setPageMessage(null);
    try {
      const response = await suggestMeetingSlots({
        contact_id: schedulerTarget.contactId,
        deal_id: schedulerTarget.dealId,
        duration_minutes: Number(schedulerDuration),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      setSchedulerSuggestions(response.slots);
      setSchedulerSelectedStart(response.slots[0]?.starts_at ?? null);
      setSchedulerMessage(response.message);
      setSchedulerYourAvailability(response.your_availability);
      setSchedulerCustomerAvailability(response.customer_availability);
      setPageMessage(response.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to suggest meeting slots.");
    } finally {
      setSchedulerLoading(false);
    }
  }

  useEffect(() => {
    if (!schedulerModalOpen || !schedulerTarget) {
      return;
    }
    void handleSuggestSchedulerSlots();
  }, [schedulerModalOpen, schedulerTarget, schedulerDuration]);

  async function handleBookSuggestedSlot(slot: SchedulerSuggestedSlot) {
    if (!schedulerTarget) return;
    setSchedulerBookingStart(slot.starts_at);
    setPageMessage(null);
    try {
      await bookSuggestedMeeting({
        contact_id: schedulerTarget.contactId,
        deal_id: schedulerTarget.dealId,
        starts_at: slot.starts_at,
        duration_minutes: slot.duration_minutes,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      setPageMessage("Meeting booked from SchedulerAgent.");
      setSchedulerModalOpen(false);
      setSchedulerSuggestions([]);
      setSchedulerTarget(null);
      setSchedulerSelectedStart(null);
      setSchedulerMessage(null);
      setSchedulerYourAvailability(null);
      setSchedulerCustomerAvailability(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to book suggested meeting.");
    } finally {
      setSchedulerBookingStart(null);
    }
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPageMessage(null);
    if (!data.me?.team_id) return;

    setTaskSubmitting(true);
    try {
      const payload: TaskCreateInput = {
        title: taskForm.title.trim(),
        description: taskForm.description.trim() || null,
        due_at: taskForm.due_at || null,
        priority: taskForm.priority,
        status: taskForm.status,
        contact_id: taskForm.contact_id || null,
        deal_id: taskForm.deal_id || null,
        account_id: taskForm.account_id || null,
        assigned_user_id: taskForm.assigned_user_id || data.me.user_id,
      };

      if (selectedTaskId) {
        await updateTask(selectedTaskId, payload);
        setPageMessage("Task updated.");
      } else {
        await createTask(payload);
        setPageMessage("Task created.");
      }

      setTaskForm(INITIAL_TASK_FORM);
      setSelectedTaskId(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save task.");
    } finally {
      setTaskSubmitting(false);
    }
  }

  async function handleCompleteTask(taskId: string) {
    setPageMessage(null);
    try {
      await completeTask(taskId);
      setPageMessage("Task marked done.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete task.");
    }
  }

  async function handleDeleteTask(taskId: string) {
    setPageMessage(null);
    try {
      await deleteTask(taskId);
      setPageMessage("Task deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete task.");
    }
  }

  async function handleCreateNote(entityType: string, entityId: string, body: string) {
    try {
      const newNote = await createNote({ body, entity_type: entityType, entity_id: entityId });
      await loadData();
      return newNote;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create note.");
      throw err;
    }
  }

  async function handleDeleteNote(noteId: string) {
    if (!window.confirm("Are you sure you want to delete this note?")) return;
    try {
      await deleteNote(noteId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete note.");
    }
  }

  async function handleCreateAutomation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAutomationSubmitting(true);
    try {
      let actionPayloadJson: Record<string, string> = {};
      try {
        actionPayloadJson = JSON.parse(automationForm.action_payload) as Record<string, string>;
      } catch (e) {
        throw new Error("Action payload must be valid JSON.");
      }

      const payload: AutomationRuleCreateInput | AutomationRuleUpdateInput = {
        name: automationForm.name,
        description: automationForm.description || undefined,
        trigger_type: automationForm.trigger_type,
        conditions_json: {
          type: automationForm.condition_type,
          value: automationForm.condition_value || undefined,
        },
        action_type: automationForm.action_type,
        action_payload_json: actionPayloadJson,
        ...(editingAutomationId ? {} : { is_enabled: true }),
      };

      if (editingAutomationId) {
        await updateAutomation(editingAutomationId, payload);
        setPageMessage("Automation rule updated.");
      } else {
        await createAutomation(payload as AutomationRuleCreateInput);
        setPageMessage("Automation rule created.");
      }
      setEditingAutomationId(null);
      setAutomationForm(INITIAL_AUTOMATION_FORM);
      await loadData();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to create rule.");
    } finally {
      setAutomationSubmitting(false);
    }
  }

  async function handleToggleAutomation(ruleId: string) {
    try {
      await toggleAutomation(ruleId);
      await loadData();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to toggle rule.");
    }
  }

  function handleEditAutomation(rule: AutomationRule) {
    setEditingAutomationId(rule.id);
    setAutomationForm({
      name: rule.name,
      description: rule.description ?? "",
      trigger_type: rule.trigger_type,
      condition_type: rule.conditions_json?.type ?? "always",
      condition_value: String(rule.conditions_json?.value ?? ""),
      action_type: rule.action_type,
      action_payload: JSON.stringify(rule.action_payload_json ?? {}, null, 2),
    });
    setActivePage("graph-runs");
  }

  function handleCancelAutomationEdit() {
    setEditingAutomationId(null);
    setAutomationForm(INITIAL_AUTOMATION_FORM);
  }

  async function handleDeleteAutomation(ruleId: string) {
    if (!window.confirm("Delete this automation rule?")) return;
    try {
      await deleteAutomation(ruleId);
      await loadData();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to delete rule.");
    }
  }

  async function handleContactResearch(contactId: string) {
    setContactResearchLoading(contactId);
    setContactResearch(null);
    try {
      const result = await fetchContactResearch(contactId);
      setContactResearch(result);
      if (result.status === "completed") {
        await loadData();
      }
    } catch {
      setContactResearch({ status: "error", reason: "Failed to fetch research" });
    } finally {
      setContactResearchLoading(null);
    }
  }

  async function handleAccountResearch(accountId: string) {
    setAccountResearchLoading(accountId);
    setAccountResearch(null);
    try {
      const result = await fetchAccountResearch(accountId);
      setAccountResearch(result);
      if (result.status === "completed") {
        await loadData();
      }
    } catch {
      setAccountResearch({ status: "error", reason: "Failed to fetch research" });
    } finally {
      setAccountResearchLoading(null);
    }
  }

  const linkedDealsByContact = useMemo(() => {
    const map = new Map<string, Deal>();
    for (const deal of data.deals) {
      if (deal.contact_id && !map.has(deal.contact_id)) {
        map.set(deal.contact_id, deal);
      }
    }
    return map;
  }, [data.deals]);

  const selectedDeal = useMemo(
    () => data.deals.find((deal) => deal.id === selectedDealId) ?? null,
    [data.deals, selectedDealId],
  );

  useEffect(() => {
    if (!selectedAccountId) {
      setAccountDetail(null);
      setAccountDetailLoading(false);
      return;
    }

    const currentAccountId = selectedAccountId;
    let cancelled = false;
    setAccountDetailLoading(true);

    async function loadAccountDetail() {
      try {
        const detail = await fetchAccountDetail(currentAccountId);
        if (!cancelled) {
          setAccountDetail(detail);
        }
      } catch (accountError) {
        if (!cancelled) {
          setError(accountError instanceof Error ? accountError.message : "Failed to load account detail.");
          setAccountDetail(null);
        }
      } finally {
        if (!cancelled) {
          setAccountDetailLoading(false);
        }
      }
    }

    void loadAccountDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedAccountId, data.accounts]);

  useEffect(() => {
    if (!selectedDeal) {
      setLineItemDrafts({});
      return;
    }

    setLineItemDrafts(
      Object.fromEntries(
        selectedDeal.line_items.map((item) => [
          item.id,
          {
            quantity: String(item.quantity),
            unit_price: String(item.unit_price),
          },
        ]),
      ),
    );
  }, [selectedDeal]);

  useEffect(() => {
    if (!selectedDeal) {
      return;
    }
    const currencyMatchedProducts = data.products.filter((product) => product.currency === selectedDeal.currency);
    setLineItemForm((current) => ({
      ...current,
      product_id: currencyMatchedProducts.some((product) => product.id === current.product_id)
        ? current.product_id
        : currencyMatchedProducts[0]?.id ?? "",
    }));
  }, [data.products, selectedDeal]);

  useEffect(() => {
    if (!selectedDeal) {
      setStakeholderForm(INITIAL_STAKEHOLDER_FORM);
      return;
    }

    const availableContacts = data.contacts.filter(
      (contact) => !selectedDeal.stakeholders.some((stakeholder) => stakeholder.contact_id === contact.id),
    );
    setStakeholderForm((current) => ({
      role: current.role,
      contact_id: availableContacts.some((contact) => contact.id === current.contact_id)
        ? current.contact_id
        : availableContacts[0]?.id ?? "",
    }));
  }, [data.contacts, selectedDeal]);

  useEffect(() => {
    if (!selectedDealId) {
      setDealTimeline([]);
      setDealTimelineLoading(false);
      return;
    }
    const currentDealId = selectedDealId;

    let cancelled = false;

    async function loadTimeline() {
      setDealTimelineLoading(true);
      try {
        const items = await fetchDealTimeline(currentDealId);
        if (!cancelled) {
          setDealTimeline(items);
        }
      } catch (timelineError) {
        if (!cancelled) {
          setError(timelineError instanceof Error ? timelineError.message : "Failed to load deal timeline.");
        }
      } finally {
        if (!cancelled) {
          setDealTimelineLoading(false);
        }
      }
    }

    void loadTimeline();
    return () => {
      cancelled = true;
    };
  }, [selectedDealId, data.deals]);

  useEffect(() => {
    setSelectedContactIds((current) => current.filter((id) => data.contacts.some((contact) => contact.id === id)));
    setSelectedProductIds((current) => current.filter((id) => data.products.some((product) => product.id === id)));
    setSelectedDealIds((current) => current.filter((id) => data.deals.some((deal) => deal.id === id)));
  }, [data.contacts, data.products, data.deals]);

  function handleLogin() {
    setAuthMessage(null);
    if (!isAuth0Configured) {
      setAuthMessage("Auth0 is not configured for the frontend yet. Add VITE_AUTH0_DOMAIN, VITE_AUTH0_CLIENT_ID, and VITE_AUTH0_AUDIENCE in frontend/.env, or use Enter Demo Workspace.");
      return;
    }
    void loginWithRedirect();
  }

  function handleSignup() {
    setAuthMessage(null);
    if (!isAuth0Configured) {
      setAuthMessage("Auth0 sign-up is not configured for the frontend yet. Add the VITE_AUTH0_* variables in frontend/.env, or use Enter Demo Workspace.");
      return;
    }
    void loginWithRedirect({
      authorizationParams: {
        screen_hint: "signup",
      },
    });
  }

  async function handleEnterDemoWorkspace() {
    setAuthMessage(null);
    setLoading(true);
    setError(null);

    try {
      const me = await fetchMe();
      setDemoAvailable(me.auth_disabled);
      setData((current) => ({ ...current, me }));
      setAuthState("authenticated");
      persistFrontendSession("authenticated");
      await loadData(me);
    } catch (sessionError) {
      setAuthState("logged_out");
      setLoading(false);
      setNurtureStatus({
        pending_count: 0,
        pending_contact_ids: [],
        pending_deal_ids: [],
        pending_items: [],
      });
      nurturerAutoRanRef.current = false;
      setAuthMessage(sessionError instanceof Error ? sessionError.message : "Unable to enter demo workspace.");
    }
  }

  function handleLogout() {
    clearRealtimeResources();
    persistFrontendSession("logged_out");
    window.localStorage.removeItem("auth_token");
    setActivePage("dashboard");
    setPageMessage(null);
    setError(null);
    setEditingProductId(null);
    setProductForm(INITIAL_PRODUCT_FORM);
    setSelectedDealId(null);
    setLineItemForm(INITIAL_LINE_ITEM_FORM);
    setLineItemDrafts({});
    setProposalDraft(null);
    setProposalDeal(null);
    setSelectedContactIds([]);
    setSelectedProductIds([]);
    setSelectedDealIds([]);
    setBulkStageId("");
    setImportResult(null);
    setSummaryContact(null);
    setLeadSummary(null);
    setDraftContact(null);
    setEmailDraft(null);
    setApprovalDraft(null);
    setRunningContactAgentId(null);
    setForecast(null);
    setReportsSummary(null);
    setReportsPipeline(null);
    setReportsPerformance(null);
    setNurtureStatus({
      pending_count: 0,
      pending_contact_ids: [],
      pending_deal_ids: [],
      pending_items: [],
    });
    nurturerAutoRanRef.current = false;
    setData(INITIAL_DATA);
    setAuthState("logged_out");
    setLoading(false);
    setCopilotOpen(false);
    setCopilotInput("");
    setCopilotHistory([]);
    if (!data.me?.auth_disabled) {
      auth0Logout({
        logoutParams: {
          returnTo: window.location.origin,
        },
      });
    }
  }

  async function handleMarkNotificationRead(id: string) {
    try {
      const updated = await markNotificationRead(id);
      setData(current => ({
        ...current,
        notifications: current.notifications.map(n => n.id === id ? updated : n)
      }));
    } catch (err) {
      setToastMessage("Failed to mark read");
    }
  }

  async function handleMarkAllNotificationsRead() {
    try {
      await markAllNotificationsRead();
      setData(current => ({
        ...current,
        notifications: current.notifications.map(n => ({ ...n, is_read: true }))
      }));
    } catch (err) {
      setToastMessage("Failed to mark all read");
    }
  }

  if (auth0Loading || (loading && authState !== "logged_out")) {
    return <LoadingScreen message="Initializing session..." />;
  }

  if (authState !== "authenticated") {
    return (
      <PublicAuthPage
        checking={authState === "checking" || auth0Loading}
        demoAvailable={demoAvailable}
        message={authMessage}
        auth0Configured={isAuth0Configured}
        onEnterDemoWorkspace={() => void handleEnterDemoWorkspace()}
        onLogin={handleLogin}
        onSignup={handleSignup}
      />
    );
  }

  async function handleCopilotSend(overrideMessage?: string) {
    const message = (overrideMessage ?? copilotInput).trim();
    if (!message) return;

    setCopilotInput("");
    setCopilotLoading(true);
    setCopilotHistory(prev => [...prev, { role: "user", content: message }]);

    try {
      const response = await fetchCopilotChat(message);
      setCopilotHistory(prev => [...prev, { role: "ai", content: response.answer, suggestions: response.suggested_actions }]);
    } catch (err) {
      setCopilotHistory(prev => [...prev, { role: "ai", content: "Sorry, I hit a snag processing that." }]);
    } finally {
      setCopilotLoading(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <p className="sidebar-eyebrow">Acufy CRM</p>
          <h1 className="sidebar-title">Acufy CRM</h1>
          <div className="sidebar-session">
            <img src={DEFAULT_AVATAR} alt="Profile" className="sidebar-avatar" />
            <strong>{data.me?.full_name ?? user?.name ?? data.me?.email ?? "Loading user..."}</strong>
            <span>{user?.email ?? data.me?.email ?? "-"}</span>
            <span>{data.me?.team_name ?? "Loading team..."}</span>
            <small>{data.me?.role ?? "-"}</small>
          </div>
        </div>

        <nav className="nav">
          {availableNavItems.map((item) => (
            <button
              key={item.id}
              className={item.id === activePage ? "nav-item active" : "nav-item"}
              onClick={() => setActivePage(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="text-button logout-button" onClick={handleLogout} type="button">
            Logout
          </button>
        </div>
      </aside>

      <main className="content">
        <header className="content-header">
          <div>
            <p className="content-eyebrow">Production API</p>
            <h2>{getPageTitle(activePage)}</h2>
            {data.me ? (
              <p className="subtle-text">
                {data.me.team_name} | {user?.email ?? data.me.email}
                {data.me.auth_disabled ? " | Demo Mode" : ""}
              </p>
            ) : null}
          </div>
          <div className="status-stack" style={{ flexDirection: "row", alignItems: "center", gap: "12px" }}>
            <button
              className="icon-button"
              onClick={() => setActivePage("notifications")}
              title="Notifications"
              style={{ position: "relative", fontSize: "1.2rem", background: "none", border: "none", cursor: "pointer" }}
            >
              🔔
              {data.notifications.filter(n => !n.is_read).length > 0 && (
                <span style={{
                  position: "absolute", top: "-4px", right: "-4px",
                  background: "#ef4444", color: "white", fontSize: "10px",
                  fontWeight: "bold", padding: "2px 6px", borderRadius: "10px",
                }}>
                  {data.notifications.filter(n => !n.is_read).length}
                </span>
              )}
            </button>
            <div className="status-pill">{loading ? "Loading data..." : "Connected to backend"}</div>
            <div className={`live-pill ${liveStatus}`}>{liveStatus === "live" ? "Live" : "Reconnecting"}</div>
            {pageMessage ? <div className="success-pill">{pageMessage}</div> : null}
          </div>
        </header>

        {error ? <ErrorState message={error} onDismiss={() => setError(null)} /> : null}

        {renderPage(activePage, {
          data,
          loading,
          forecast,
          forecastLoading,
          reportsSummary,
          reportsPipeline,
          reportsPerformance,
          reportsLoading,
          reportsPeriod,
          reportsCustomRange,
          contactForm,
          dealForm,
          productForm,
          lineItemForm,
          contactSubmitting,
          dealSubmitting,
          productSubmitting,
          lineItemSubmitting,
          bulkSubmitting,
          importSubmitting,
          onContactFormChange: setContactForm,
          onDealFormChange: setDealForm,
          onProductFormChange: setProductForm,
          onLineItemFormChange: setLineItemForm,
          onCreateContact: handleCreateContact,
          onCreateDeal: handleCreateDeal,
          onCreateOrUpdateProduct: handleCreateOrUpdateProduct,
          onDeleteContact: handleDeleteContact,
          onDeleteProduct: handleDeleteProduct,
          onEditProduct: handleEditProduct,
          onMoveDealStage: handleMoveDealStage,
          onBulkDeleteContacts: handleBulkDeleteContacts,
          onBulkDeleteProducts: handleBulkDeleteProducts,
          onBulkMoveDeals: handleBulkMoveDeals,
          onNavigate: setActivePage,
          onOpenDealFromPipeline: handleOpenDealFromPipeline,
          onImportCsv: handleImport,
          onExportCsv: handleExport,
          onSelectDeal: setSelectedDealId,
          onAddLineItem: handleAddLineItem,
          onAddStakeholder: handleAddStakeholder,
          onUpdateLineItem: handleUpdateLineItem,
          onUpdateStakeholder: handleUpdateStakeholder,
          onDeleteLineItem: handleDeleteLineItem,
          onDeleteStakeholder: handleDeleteStakeholder,
          onGenerateProposal: handleGenerateProposal,
          onLoadLeadSummary: handleLoadLeadSummary,
          onLoadEmailDraft: handleLoadEmailDraft,
          onRunAllContactAgents: handleRunAllContactAgents,
          onGenerateNurtureNow: handleGenerateNurtureNow,
          onApprove: handleApprove,
          onApproveAndSendSms: handleApproveAndSendSms,
          onReject: handleReject,
          onRetryApprovalSend: handleRetryApprovalSend,
          onCancelApprovalSend: handleCancelApprovalSend,
          onRefreshForecast: loadForecastInsights,
          onRefreshReports: loadReports,
          onReportsPeriodChange: setReportsPeriod,
          onReportsCustomRangeChange: setReportsCustomRange,
          selectedGraphRun,
          selectedGraphRunId,
          selectedGraphRunLoading,
          swarmStatus,
          swarmEvents,
          swarmJobs,
          swarmLoading,
          runningSwarmAgents,
          onRunSwarmAgent: handleRunSwarmAgent,
          onSelectGraphRun: setSelectedGraphRunId,
          accountDetail,
          accountDetailLoading,
          selectedAccountId,
          onSelectAccount: setSelectedAccountId,
          summaryLoadingId,
          draftLoadingId,
          runningContactAgentId,
          approvalSubmittingId,
          linkedDealsByContact,
          onViewApprovalDraft: setApprovalDraft,
          selectedDeal,
          stakeholderForm,
          onStakeholderFormChange: setStakeholderForm,
          editingProductId,
          lineItemUpdatingId,
          stakeholderUpdatingId,
          selectedContactIds,
          onSelectedContactIdsChange: setSelectedContactIds,
          selectedProductIds,
          onSelectedProductIdsChange: setSelectedProductIds,
          selectedDealIds,
          onSelectedDealIdsChange: setSelectedDealIds,
          bulkStageId,
          onBulkStageIdChange: setBulkStageId,
          dealTimeline,
          dealTimelineLoading,
          lineItemDrafts,
          onLineItemDraftChange: setLineItemDrafts,
          stakeholderSubmitting,
          meetingForm,
          onMeetingFormChange: setMeetingForm,
          onCreateMeeting: handleCreateMeeting,
          onCompleteMeeting: handleCompleteMeeting,
          onCancelMeeting: handleCancelMeeting,
          onDeleteMeeting: handleDeleteMeeting,
          onEditMeeting: handleEditMeeting,
          meetingSubmitting,
          selectedMeetingId,
          onSelectMeeting: setSelectedMeetingId,
          meetingComposerOpen,
          onMeetingComposerOpenChange: setMeetingComposerOpen,
          calendarMonth,
          onCalendarMonthChange: setCalendarMonth,
          meetingFilters,
          onMeetingFiltersChange: setMeetingFilters,
          onOpenMeetingComposerForDate: openMeetingComposerForDate,
          onOpenScheduler: handleOpenScheduler,
          taskForm,
          onTaskFormChange: setTaskForm,
          onCreateTask: handleCreateTask,
          onCompleteTask: handleCompleteTask,
          onDeleteTask: handleDeleteTask,
          taskSubmitting,
          selectedTaskId,
          onSelectTask: setSelectedTaskId,
          taskFilters,
          onTaskFiltersChange: setTaskFilters,
          onCreateNote: handleCreateNote,
          onDeleteNote: handleDeleteNote,
          automationForm,
          onAutomationFormChange: setAutomationForm,
          onCreateAutomation: handleCreateAutomation,
          onToggleAutomation: handleToggleAutomation,
          onEditAutomation: handleEditAutomation,
          onCancelAutomationEdit: handleCancelAutomationEdit,
          onDeleteAutomation: handleDeleteAutomation,
          editingAutomationId,
          automationSubmitting,
          contactResearch,
          contactResearchLoading,
          onContactResearch: handleContactResearch,
          accountResearch,
          accountResearchLoading,
          onAccountResearch: handleAccountResearch,
          nurtureStatus,
          onMarkNotificationRead: handleMarkNotificationRead,
          onMarkAllNotificationsRead: handleMarkAllNotificationsRead,
          onReloadData: () => loadData(),
        })}

        <MeetingComposerModal
          data={data}
          meetingForm={meetingForm}
          meetingSubmitting={meetingSubmitting}
          open={meetingComposerOpen}
          selectedMeetingId={selectedMeetingId}
          onClose={() => {
            setMeetingComposerOpen(false);
            setSelectedMeetingId(null);
            setMeetingForm(INITIAL_MEETING_FORM);
          }}
          onCreateMeeting={handleCreateMeeting}
          onMeetingFormChange={setMeetingForm}
        />

        <SchedulerModal
          bookingStart={schedulerBookingStart}
          customerAvailability={schedulerCustomerAvailability}
          durationMinutes={schedulerDuration}
          loading={schedulerLoading}
          message={schedulerMessage}
          open={schedulerModalOpen}
          selectedStart={schedulerSelectedStart}
          suggestions={schedulerSuggestions}
          targetLabel={schedulerTarget?.label ?? ""}
          yourAvailability={schedulerYourAvailability}
          onBookSlot={handleBookSuggestedSlot}
          onClose={() => {
            setSchedulerModalOpen(false);
            setSchedulerSuggestions([]);
            setSchedulerTarget(null);
            setSchedulerSelectedStart(null);
            setSchedulerMessage(null);
            setSchedulerYourAvailability(null);
            setSchedulerCustomerAvailability(null);
          }}
          onDurationChange={setSchedulerDuration}
          onSelectSlot={setSchedulerSelectedStart}
          onSuggestSlots={() => void handleSuggestSchedulerSlots()}
        />

        {/* Copilot Floating Widget */}
        <div className={`copilot-container ${copilotOpen ? "open" : ""}`}>
          {copilotOpen && (
            <div className="copilot-window panel-card">
              <div className="copilot-header">
                <h3>Acufy Copilot</h3>
                <button onClick={() => setCopilotOpen(false)} className="text-button">❌ Close</button>
              </div>
              <div className="copilot-messages">
                {copilotHistory.length === 0 && <p className="subtle-text">Ask me about your pipeline, stalled deals, or pending approvals.</p>}
                {copilotHistory.map((m, i) => (
                  <div key={i} className={`copilot-msg ${m.role}`}>
                    <div className="msg-bubble">{m.content}</div>
                    {m.suggestions && (
                      <div className="suggestion-row">
                        {m.suggestions.map(s => (
                          <button key={s} onClick={() => handleCopilotSend(s)} className="suggestion-pill">{s}</button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {copilotLoading && <div className="copilot-msg ai"><div className="msg-bubble">...</div></div>}
              </div>
              <div className="copilot-input-row">
                <input
                  value={copilotInput}
                  onChange={(e) => setCopilotInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCopilotSend()}
                  placeholder="Ask anything..."
                />
                <button onClick={() => handleCopilotSend()} disabled={copilotLoading} className="primary-button" type="button">Send</button>
              </div>
            </div>
          )}
          <button className="copilot-trigger" onClick={() => setCopilotOpen(!copilotOpen)} type="button">
            {copilotOpen ? "×" : "AI"}
          </button>
        </div>

        {summaryContact ? (
          <LeadSummaryModal
            contact={summaryContact}
            summary={leadSummary}
            loading={summaryLoadingId === summaryContact.id}
            onClose={() => {
              setSummaryContact(null);
              setLeadSummary(null);
              setSummaryLoadingId(null);
            }}
          />
        ) : null}

        {draftContact ? (
          <EmailDraftModal
            contact={draftContact}
            draft={emailDraft}
            loading={draftLoadingId === draftContact.id}
            onClose={() => {
              setDraftContact(null);
              setEmailDraft(null);
              setDraftLoadingId(null);
            }}
          />
        ) : null}

        {approvalDraft ? (
          <ApprovalDraftModal
            approval={approvalDraft}
            saving={approvalDraftSaving}
            onSave={async (subject, body) => {
              setApprovalDraftSaving(true);
              try {
                const updated = await updateApprovalDraft(approvalDraft.id, subject, body);
                setApprovalDraft((current) =>
                  current
                    ? {
                      ...current,
                      subject: updated.subject,
                      body: updated.body,
                    }
                    : current,
                );
                setPageMessage("Draft updated.");
                await loadData();
              } catch (draftError) {
                setError(draftError instanceof Error ? draftError.message : "Failed to update approval draft.");
              } finally {
                setApprovalDraftSaving(false);
              }
            }}
            onClose={() => setApprovalDraft(null)}
          />
        ) : null}

        {proposalDeal ? (
          <ProposalDraftModal
            deal={proposalDeal}
            draft={proposalDraft}
            loading={proposalLoading}
            onClose={() => {
              setProposalDeal(null);
              setProposalDraft(null);
              setProposalLoading(false);
            }}
          />
        ) : null}

        {importResult ? (
          <ImportResultModal
            result={importResult}
            onClose={() => setImportResult(null)}
          />
        ) : null}

        {toastMessage ? (
          <div className="toast-banner" role="status" aria-live="polite">
            {toastMessage}
          </div>
        ) : null}
      </main>
    </div>
  );
}



function renderPage(page: Page, props: PageProps) {
  switch (page) {
    case "dashboard":
      return (
        <DashboardPage
          data={props.data}
          loading={props.loading}
          forecast={props.forecast}
          forecastLoading={props.forecastLoading}
          nurtureStatus={props.nurtureStatus}
          onRefreshForecast={props.onRefreshForecast}
          viewerRole={props.data.me?.role ?? "rep"}
        />
      );
    case "reports":
      return (
        <ReportsPage
          summary={props.reportsSummary}
          pipeline={props.reportsPipeline}
          performance={props.reportsPerformance}
          loading={props.reportsLoading}
          period={props.reportsPeriod}
          customRange={props.reportsCustomRange}
          onRefresh={props.onRefreshReports}
          onPeriodChange={props.onReportsPeriodChange}
          onCustomRangeChange={props.onReportsCustomRangeChange}
        />
      );
    case "accounts":
      return <AccountsPage {...props} />;
    case "contacts":
      return <ContactsPage {...props} />;
    case "products":
      return <ProductsPage {...props} />;
    case "deals":
      return <DealsPage {...props} />;
    case "messages":
      return <MessagesPage {...props} />;
    case "emails":
      return <EmailsPage {...props} />;
    case "notifications":
      return <NotificationsPage {...props} />;
    case "pipeline":
      return (
        <PipelinePage
          deals={props.data.deals}
          stages={props.data.stages}
          loading={props.loading}
          onMoveDealStage={props.onMoveDealStage}
          onOpenDeal={props.onOpenDealFromPipeline}
          onCreateDealClick={() => props.onNavigate("deals")}
        />
      );
    case "import-export":
      return <ImportExportPage {...props} />;
    case "approvals":
      return <ApprovalsPage {...props} />;
    case "approval-history":
      return (
        <ApprovalHistoryPage
          data={props.data}
          loading={props.loading}
          approvalSubmittingId={props.approvalSubmittingId}
          onRetryApprovalSend={props.onRetryApprovalSend}
          onCancelApprovalSend={props.onCancelApprovalSend}
        />
      );
    case "graph-runs":
      return (
        <GraphRunsPage
          runs={props.data.workflowRuns}
          loading={props.loading || props.swarmLoading}
          swarmStatus={props.swarmStatus}
          swarmEvents={props.swarmEvents}
          swarmJobs={props.swarmJobs}
          runningSwarmAgents={props.runningSwarmAgents}
          onRunSwarmAgent={props.onRunSwarmAgent}
          selectedRun={props.selectedGraphRun}
          selectedRunId={props.selectedGraphRunId}
          selectedRunLoading={props.selectedGraphRunLoading}
          onSelectRun={props.onSelectGraphRun}
          data={props.data}
        />
      );
    case "calendar":
      return <CalendarPage {...props} />;
    case "tasks":
      return <TasksPage {...props} />;
    case "activity-feed":
      return <ActivityFeedPage {...props} />;
  }
}



export default App;


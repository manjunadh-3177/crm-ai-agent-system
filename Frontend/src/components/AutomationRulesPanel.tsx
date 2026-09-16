import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";

import type { AutomationRule } from "../lib/api";
import { formatRunStats, getConditionPlaceholder, getTriggerBadgeColor } from "../lib/formatters";
import type { AutomationRuleFormState, DataState } from "../types/appState";

// ── Automation V2 constants ────────────────────────────────────────────────

export const AUTOMATION_TRIGGERS = [
  { value: "contact.created", label: "Contact Created" },
  { value: "deal.created", label: "Deal Created" },
  { value: "deal.stage_changed", label: "Deal Stage Changed" },
  { value: "lead.qualified_hot", label: "Lead Qualified Hot" },
  { value: "meeting.completed", label: "Meeting Completed" },
  { value: "task.overdue", label: "Task Overdue" },
];

export const AUTOMATION_CONDITIONS = [
  { value: "always", label: "Always" },
  { value: "stage_equals", label: "Stage Equals" },
  { value: "lead_tier_equals", label: "Lead Tier Equals" },
  { value: "deal_health_equals", label: "Deal Health Equals" },
];

export const AUTOMATION_ACTIONS = [
  { value: "notify_user", label: "Notify User" },
  { value: "create_task", label: "Create Task" },
  { value: "assign_owner", label: "Assign Owner" },
  { value: "create_meeting", label: "Create Meeting" },
  { value: "change_status", label: "Change Status" },
  { value: "draft_email", label: "Draft Email" },
];

const ACTION_PAYLOAD_HINTS: Record<string, string> = {
  notify_user: JSON.stringify({ title: "Action Required", message: "A rule was triggered." }, null, 2),
  create_task: JSON.stringify({ title: "Follow up with client", priority: "high", description: "Auto-generated task." }, null, 2),
  assign_owner: JSON.stringify({ assigned_user_id: "user-uuid-here" }, null, 2),
  create_meeting: JSON.stringify({ title: "Follow-up call", meeting_type: "call", days_from_now: 1, duration_minutes: 30 }, null, 2),
  change_status: JSON.stringify({ status: "done" }, null, 2),
  draft_email: JSON.stringify({ subject: "Following up", body: "Just checking in..." }, null, 2),
};

const AUTOMATION_TEMPLATES: Array<{ title: string; description: string; form: AutomationRuleFormState }> = [
  {
    title: "New Contact -> Draft Email",
    description: "Prepare a welcome draft whenever a contact is added.",
    form: {
      name: "New Contact -> Draft Email",
      description: "Prepare a welcome email draft for each new contact.",
      trigger_type: "contact.created",
      condition_type: "always",
      condition_value: "",
      action_type: "draft_email",
      action_payload: JSON.stringify({ subject: "Great to connect", body: "Thanks for connecting. I wanted to introduce myself and see if a quick next step would be helpful." }, null, 2),
    },
  },
  {
    title: "Hot Lead -> Notify Me",
    description: "Send an alert when LeadQualifierAgent marks a lead hot.",
    form: {
      name: "Hot Lead -> Notify Me",
      description: "Notify the team when a hot lead is qualified.",
      trigger_type: "lead.qualified_hot",
      condition_type: "lead_tier_equals",
      condition_value: "Hot",
      action_type: "notify_user",
      action_payload: JSON.stringify({ title: "Hot lead", message: "A hot lead is ready for follow-up." }, null, 2),
    },
  },
  {
    title: "Won Deal -> Create Follow-up Task",
    description: "Create a handoff task when a deal moves to Won.",
    form: {
      name: "Won Deal -> Create Follow-up Task",
      description: "Create a customer follow-up task when a deal is won.",
      trigger_type: "deal.stage_changed",
      condition_type: "stage_equals",
      condition_value: "Won",
      action_type: "create_task",
      action_payload: JSON.stringify({ title: "Follow up after won deal", priority: "med", description: "Confirm next steps and onboarding details." }, null, 2),
    },
  },
  {
    title: "Stale Deal -> Alert Me",
    description: "Notify the team when a deal is marked stalled.",
    form: {
      name: "Stale Deal -> Alert Me",
      description: "Alert when a deal health signal is stalled.",
      trigger_type: "deal.stage_changed",
      condition_type: "deal_health_equals",
      condition_value: "stalled",
      action_type: "notify_user",
      action_payload: JSON.stringify({ title: "Stale deal", message: "A deal needs attention." }, null, 2),
    },
  },
  {
    title: "Meeting Done -> Send Follow-up",
    description: "Draft a follow-up email after a completed meeting.",
    form: {
      name: "Meeting Done -> Send Follow-up",
      description: "Prepare a follow-up draft after a meeting is completed.",
      trigger_type: "meeting.completed",
      condition_type: "always",
      condition_value: "",
      action_type: "draft_email",
      action_payload: JSON.stringify({ subject: "Thanks for the meeting", body: "Thanks for taking the time today. I wanted to recap the next step and keep momentum going." }, null, 2),
    },
  },
];


export function AutomationRulesPanel({
  data,
  loading,
  automationForm,
  onAutomationFormChange,
  onCreateAutomation,
  onToggleAutomation,
  onEditAutomation,
  onCancelAutomationEdit,
  onDeleteAutomation,
  editingAutomationId,
  automationSubmitting,
}: {
  data: DataState;
  loading: boolean;
  automationForm: AutomationRuleFormState;
  onAutomationFormChange: Dispatch<SetStateAction<AutomationRuleFormState>>;
  onCreateAutomation: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onToggleAutomation: (ruleId: string) => Promise<void>;
  onEditAutomation: (rule: AutomationRule) => void;
  onCancelAutomationEdit: () => void;
  onDeleteAutomation: (ruleId: string) => Promise<void>;
  editingAutomationId: string | null;
  automationSubmitting: boolean;
}) {
  const enabledCount = data.automations.filter((r) => r.is_enabled).length;
  const totalRuns = data.automations.reduce((s, r) => s + (r.run_count || 0), 0);
  const [customRuleOpen, setCustomRuleOpen] = useState(false);

  return (
    <section className="stack">
      {/* Stats row */}
      <div className="automation-stats-row">
        <div className="automation-stat-card">
          <div className="automation-stat-value">{data.automations.length}</div>
          <div className="automation-stat-label">Total Rules</div>
        </div>
        <div className="automation-stat-card">
          <div className="automation-stat-value" style={{ color: "#10b981" }}>{enabledCount}</div>
          <div className="automation-stat-label">Enabled</div>
        </div>
        <div className="automation-stat-card">
          <div className="automation-stat-value" style={{ color: "#3b82f6" }}>{totalRuns}</div>
          <div className="automation-stat-label">Total Executions</div>
        </div>
      </div>

      <div className="automation-template-grid">
        {AUTOMATION_TEMPLATES.map((template) => (
          <button
            key={template.title}
            className="automation-template-card"
            type="button"
            onClick={() => {
              onAutomationFormChange(template.form);
              setCustomRuleOpen(true);
            }}
          >
            <strong>{template.title}</strong>
            <span>{template.description}</span>
          </button>
        ))}
      </div>

      <details
        className="ops-section custom-rule-section"
        open={customRuleOpen || Boolean(editingAutomationId)}
        onToggle={(event) => setCustomRuleOpen(event.currentTarget.open)}
      >
        <summary>Custom Rule</summary>
        <div className="ops-section-body">
      <form className="panel-card form-card" onSubmit={onCreateAutomation} id="automation-create-form">
        <div className="form-header">
          <div>
            <h3>{editingAutomationId ? "Edit Automation Rule" : "Create Automation Rule"}</h3>
            <p className="subtle-text">Define a trigger → condition → action workflow.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Rule Name *
            <input
              required
              placeholder="e.g. Notify on hot lead"
              value={automationForm.name}
              onChange={(e) => onAutomationFormChange({ ...automationForm, name: e.target.value })}
            />
          </label>
          <label>
            Description
            <input
              placeholder="Optional — what does this rule do?"
              value={automationForm.description}
              onChange={(e) => onAutomationFormChange({ ...automationForm, description: e.target.value })}
            />
          </label>
        </div>

        {/* Trigger → Condition → Action pipeline */}
        <div className="automation-pipeline">
          {/* Trigger */}
          <div className="automation-pipeline-step">
            <div className="pipeline-step-label">
              <span className="pipeline-step-icon">⚡</span> TRIGGER
            </div>
            <select
              required
              value={automationForm.trigger_type}
              onChange={(e) => onAutomationFormChange({ ...automationForm, trigger_type: e.target.value })}
            >
              {AUTOMATION_TRIGGERS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div className="pipeline-arrow">→</div>

          {/* Condition */}
          <div className="automation-pipeline-step">
            <div className="pipeline-step-label">
              <span className="pipeline-step-icon">🔍</span> CONDITION
            </div>
            <select
              required
              value={automationForm.condition_type}
              onChange={(e) => onAutomationFormChange({ ...automationForm, condition_type: e.target.value, condition_value: "" })}
            >
              {AUTOMATION_CONDITIONS.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            {automationForm.condition_type !== "always" && (
              <input
                required
                style={{ marginTop: "8px" }}
                placeholder={getConditionPlaceholder(automationForm.condition_type)}
                value={automationForm.condition_value}
                onChange={(e) => onAutomationFormChange({ ...automationForm, condition_value: e.target.value })}
              />
            )}
          </div>

          <div className="pipeline-arrow">→</div>

          {/* Action */}
          <div className="automation-pipeline-step">
            <div className="pipeline-step-label">
              <span className="pipeline-step-icon">🎯</span> ACTION
            </div>
            <select
              required
              value={automationForm.action_type}
              onChange={(e) => {
                const next = e.target.value;
                onAutomationFormChange({
                  ...automationForm,
                  action_type: next,
                  action_payload: ACTION_PAYLOAD_HINTS[next] ?? "{}",
                });
              }}
            >
              {AUTOMATION_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Action payload */}
        <div style={{ marginTop: "16px" }}>
          <label>
            <span style={{ fontWeight: 600 }}>Action Payload (JSON)</span>
            <span className="subtle-text" style={{ marginLeft: "8px", fontSize: "12px" }}>
              Fields passed to the action — edit as needed.
            </span>
            <textarea
              required
              rows={5}
              value={automationForm.action_payload}
              onChange={(e) => onAutomationFormChange({ ...automationForm, action_payload: e.target.value })}
              style={{ fontFamily: "monospace", fontSize: "13px", marginTop: "6px" }}
              spellCheck={false}
            />
          </label>
        </div>

        <div className="form-actions">
          <button
            className="primary-button"
            disabled={automationSubmitting || !automationForm.name}
            type="submit"
          >
            {automationSubmitting ? "Saving..." : editingAutomationId ? "Save Rule" : "Create Rule"}
          </button>
          {editingAutomationId ? (
            <button className="text-button" onClick={onCancelAutomationEdit} type="button">
              Cancel Edit
            </button>
          ) : null}
        </div>
      </form>
        </div>
      </details>

      <div className="panel-card">
        <div className="form-header">
          <h3>Active Rules</h3>
          <span className="subtle-text">{data.automations.length} rule{data.automations.length !== 1 ? "s" : ""} configured</span>
        </div>

        {loading ? (
          <p className="modal-copy">Loading rules...</p>
        ) : data.automations.length === 0 ? (
          <p className="modal-copy">No automation rules yet. Create one above to get started.</p>
        ) : (
          <div className="automation-rules-list">
            {data.automations.map((rule) => (
              <div key={rule.id} className={`automation-rule-card ${!rule.is_enabled ? "disabled" : ""}`}>
                <div className="automation-rule-header">
                  <div className="automation-rule-title-row">
                    <strong>{rule.name}</strong>
                    <span
                      className={`status-pill ${rule.is_enabled ? "open" : "cancelled"}`}
                      style={{ fontSize: "11px", padding: "2px 8px" }}
                    >
                      {rule.is_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  {rule.description && (
                    <p className="subtle-text" style={{ margin: "2px 0 0", fontSize: "13px" }}>{rule.description}</p>
                  )}
                </div>

                {/* Pipeline badges */}
                <div className="automation-rule-pipeline">
                  <span
                    className="automation-badge"
                    style={{ background: getTriggerBadgeColor(rule.trigger_type) + "22", color: getTriggerBadgeColor(rule.trigger_type), borderColor: getTriggerBadgeColor(rule.trigger_type) + "44" }}
                  >
                    ⚡ {AUTOMATION_TRIGGERS.find((t) => t.value === rule.trigger_type)?.label ?? rule.trigger_type}
                  </span>
                  <span className="automation-pipe-sep">→</span>
                  <span className="automation-badge" style={{ background: "#f1f5f922", color: "#64748b", borderColor: "#e2e8f0" }}>
                    🔍 {rule.conditions_json?.type ?? "always"}
                    {rule.conditions_json?.value ? ` = ${rule.conditions_json.value}` : ""}
                  </span>
                  <span className="automation-pipe-sep">→</span>
                  <span className="automation-badge" style={{ background: "#10b98111", color: "#10b981", borderColor: "#10b98133" }}>
                    🎯 {AUTOMATION_ACTIONS.find((a) => a.value === rule.action_type)?.label ?? rule.action_type}
                  </span>
                </div>

                {/* Stats + controls */}
                <div className="automation-rule-footer">
                  <small className="subtle-text">
                    {formatRunStats(rule)}
                  </small>
                    <button
                      className="text-button"
                      onClick={() => onEditAutomation(rule)}
                      type="button"
                    >
                      Edit
                    </button>
                  <div className="action-row compact-actions">
                    <button
                      className="text-button"
                      onClick={() => void onToggleAutomation(rule.id)}
                    >
                      {rule.is_enabled ? "⏸ Disable" : "▶ Enable"}
                    </button>
                    <button
                      className="text-button danger-text"
                      onClick={() => void onDeleteAutomation(rule.id)}
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

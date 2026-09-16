import type { Note, Task } from "../lib/api";
import type { PageProps } from "../types/appState";
import { INITIAL_TASK_FORM } from "../types/appState";
import { NoteSection } from "../components/NoteList";

export function TasksPage(props: PageProps) {
  const {
    data,
    loading,
    taskForm,
    taskSubmitting,
    onCreateTask,
    onTaskFormChange,
    onCompleteTask,
    onDeleteTask,
    selectedTaskId,
    onSelectTask,
    taskFilters,
    onTaskFiltersChange,
  } = props;

  const filteredTasks = data.tasks.filter((t) => {
    if (taskFilters.status && t.status !== taskFilters.status) return false;
    if (taskFilters.priority && t.priority !== taskFilters.priority) return false;
    return true;
  });

  function handleEdit(t: Task) {
    onSelectTask(t.id);
    onTaskFormChange({
      title: t.title,
      description: t.description ?? "",
      due_at: t.due_at ? t.due_at.slice(0, 16) : "",
      priority: t.priority,
      status: t.status,
      contact_id: t.contact_id ?? "",
      deal_id: t.deal_id ?? "",
      account_id: t.account_id ?? "",
      assigned_user_id: t.assigned_user_id ?? "",
    });
  }

  return (
    <section className="stack">
      <div className="panel-card">
        <div className="form-header">
          <h3>{selectedTaskId ? "✏️ Edit Task" : "📌 Add New Task"}</h3>
        </div>
        <form className="crm-form" onSubmit={onCreateTask}>
          <div className="form-grid">
            <div className="form-group">
              <label>Title</label>
              <input
                required
                value={taskForm.title}
                onChange={(e) => onTaskFormChange({ ...taskForm, title: e.target.value })}
                placeholder="Follow up on proposal..."
              />
            </div>
            <div className="form-group">
              <label>Priority</label>
              <select
                value={taskForm.priority}
                onChange={(e) => onTaskFormChange({ ...taskForm, priority: e.target.value as Task["priority"] })}
              >
                <option value="low">Low</option>
                <option value="med">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <div className="form-group">
              <label>Due Date</label>
              <input
                type="datetime-local"
                value={taskForm.due_at}
                onChange={(e) => onTaskFormChange({ ...taskForm, due_at: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Assigned To (ID)</label>
              <input
                value={taskForm.assigned_user_id}
                onChange={(e) => onTaskFormChange({ ...taskForm, assigned_user_id: e.target.value })}
                placeholder={data.me?.user_id}
              />
            </div>
            <div className="form-group">
              <label>Link Contact</label>
              <select
                value={taskForm.contact_id}
                onChange={(e) => onTaskFormChange({ ...taskForm, contact_id: e.target.value })}
              >
                <option value="">None</option>
                {data.contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Link Deal</label>
              <select
                value={taskForm.deal_id}
                onChange={(e) => onTaskFormChange({ ...taskForm, deal_id: e.target.value })}
              >
                <option value="">None</option>
                {data.deals.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group full-width">
            <label>Description</label>
            <textarea
              value={taskForm.description}
              onChange={(e) => onTaskFormChange({ ...taskForm, description: e.target.value })}
              rows={3}
            />
          </div>
          <div className="form-actions">
            {selectedTaskId && (
              <button
                className="text-button"
                type="button"
                onClick={() => {
                  onSelectTask(null);
                  onTaskFormChange(INITIAL_TASK_FORM);
                }}
              >
                ❌ Cancel Edit
              </button>
            )}
            <button className="primary-button" disabled={taskSubmitting} type="submit">
              {taskSubmitting ? "💾 Saving..." : selectedTaskId ? "💾 Update Task" : "📌 Add Task"}
            </button>
          </div>
        </form>
      </div>

      <div className="panel-card">
        <div className="form-header">
          <div>
          <h3>📋 Tasks Hub</h3>
            <p className="subtle-text">All tasks across the team.</p>
          </div>
          <div className="filter-row">
            <select
              value={taskFilters.status}
              onChange={(e) => onTaskFiltersChange({ ...taskFilters, status: e.target.value })}
            >
              <option value="">All Statuses</option>
              <option value="open">Open</option>
              <option value="done">Done</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <select
              value={taskFilters.priority}
              onChange={(e) => onTaskFiltersChange({ ...taskFilters, priority: e.target.value })}
            >
              <option value="">All Priorities</option>
              <option value="low">Low</option>
              <option value="med">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>

        <div className="agent-activity-list">
          {loading ? (
            <p className="modal-copy">Loading tasks...</p>
          ) : filteredTasks.length === 0 ? (
            <p className="modal-copy">No tasks found matching filters.</p>
          ) : (
            filteredTasks.map((t) => (
              <div key={t.id} className="meeting-activity-item">
                <div className="meeting-row-header">
                  <div className="stack-tight">
                    <div className="row-align">
                      <strong>{t.title}</strong>
                      <span className={`status-pill ${t.status}`}>{t.status}</span>
                      <span className={`type-tag`}>{t.priority}</span>
                    </div>
                    {t.due_at && (
                      <span className="subtle-text">Due: {new Date(t.due_at).toLocaleString()}</span>
                    )}
                  </div>
                  <div className="filter-row compact-actions">
                    {t.status === "open" && (
                      <button className="text-button" onClick={() => void onCompleteTask(t.id)}>
                        ✅ Mark Done
                      </button>
                    )}
                    <button className="text-button" onClick={() => handleEdit(t)}>
                      ✏️ Edit
                    </button>
                    <button className="text-button danger-text" onClick={() => void onDeleteTask(t.id)}>
                      🗑️ Delete
                    </button>
                  </div>
                </div>
                {(t.contact || t.deal || t.account) && (
                  <div className="meeting-tags">
                    {t.contact && <span className="location-tag">Contact: {t.contact.first_name} {t.contact.last_name}</span>}
                    {t.deal && <span className="location-tag">Deal: {t.deal.name}</span>}
                    {t.account && <span className="location-tag">Account: {t.account.name}</span>}
                  </div>
                )}
                {t.description && <p className="meeting-desc-preview">{t.description}</p>}
                {selectedTaskId === t.id && (
                  <div style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid #eee" }}>
                    <NoteSection
                      entityType="task"
                      entityId={t.id}
                      notes={data.activityFeed.filter(item => item.type === "note").map(item => ({
                        id: item.id,
                        team_id: data.me?.team_id || "",
                        body: item.description,
                        entity_type: item.entity_type || "",
                        entity_id: item.entity_id || "",
                        created_by_user_id: item.actor_id,
                        created_at: item.time,
                        updated_at: item.time
                      })) as Note[]}
                      onCreateNote={props.onCreateNote}
                      onDeleteNote={props.onDeleteNote}
                    />
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

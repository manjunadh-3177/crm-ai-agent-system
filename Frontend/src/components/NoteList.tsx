import { useState } from "react";
import type { Note } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

export function NoteList({ notes, onDeleteNote }: { notes: Note[]; onDeleteNote: (id: string) => void }) {
  if (notes.length === 0) return <p className="subtle-text">No notes yet.</p>;

  return (
    <div className="agent-activity-list">
      {notes.map((note) => (
        <div key={note.id} className="agent-activity-item">
          <div className="meeting-row-header">
            <span className="activity-time">{formatDateTime(note.created_at)}</span>
            <button className="text-button danger" onClick={() => onDeleteNote(note.id)}>
              Delete
            </button>
          </div>
          <p className="modal-copy" style={{ whiteSpace: "pre-wrap" }}>
            {note.body}
          </p>
        </div>
      ))}
    </div>
  );
}

export function NoteSection({
  entityType,
  entityId,
  notes,
  onCreateNote,
  onDeleteNote,
}: {
  entityType: string;
  entityId: string;
  notes: Note[];
  onCreateNote: (type: string, id: string, body: string) => Promise<any>;
  onDeleteNote: (id: string) => void;
}) {
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSubmitting(true);
    try {
      await onCreateNote(entityType, entityId, body);
      setBody("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="timeline-section">
      <div className="form-header">
        <h3>Notes</h3>
      </div>
      <form onSubmit={handleSubmit} className="note-form" style={{ marginBottom: "16px" }}>
        <textarea
          className="form-input"
          placeholder="Add a note..."
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={3}
          required
        ></textarea>
        <div style={{ textAlign: "right", marginTop: "8px" }}>
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Adding..." : "Add Note"}
          </button>
        </div>
      </form>
      <NoteList notes={notes.filter((n) => n.entity_type === entityType && n.entity_id === entityId)} onDeleteNote={onDeleteNote} />
    </div>
  );
}

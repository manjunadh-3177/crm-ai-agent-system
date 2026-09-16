import type { ImportResult } from "../lib/api";

export function ImportResultModal({
  result,
  onClose,
}: {
  result: ImportResult;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <p className="content-eyebrow">📥 Import Result</p>
            <h3>{result.entity}</h3>
          </div>
          <button className="text-button" onClick={onClose} type="button">
            ❌ Close
          </button>
        </div>
        <div className="modal-body">
          <div className="detail-grid">
            <div className="agent-activity-item">
              <strong>Created</strong>
              <span>{result.created}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Skipped</strong>
              <span>{result.skipped}</span>
            </div>
            <div className="agent-activity-item">
              <strong>Failed</strong>
              <span>{result.failed}</span>
            </div>
          </div>
          <div>
            <h4>Row-Level Errors</h4>
            {result.errors.length === 0 ? (
              <p className="modal-copy">No row-level issues.</p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((error) => (
                      <tr key={`${error.row_number}-${error.message}`}>
                        <td>{error.row_number}</td>
                        <td>{error.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

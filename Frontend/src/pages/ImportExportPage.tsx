import { useState } from "react";

import type { CsvPreview, ImportResult, ImportRowError } from "../lib/api";
import {
  previewCsv,
  importContactsCsvMapped,
  downloadContactsCsv,
  downloadDealsCsv,
  triggerBlobDownload,
} from "../lib/api";
import type { PageProps } from "../types/appState";

const CRM_FIELDS = [
  { value: "",            label: "— Skip column —" },
  { value: "name",        label: "Full Name (auto-split)" },
  { value: "first_name",  label: "First Name" },
  { value: "last_name",   label: "Last Name" },
  { value: "email",       label: "Email" },
  { value: "phone",       label: "Phone" },
];

export function ImportExportPage(_props: PageProps) {
  // ── Import state ──────────────────────────────────────────────────────────
  const [importFile, setImportFile] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  // ── Export state ─────────────────────────────────────────────────────────
  const [exportingContacts, setExportingContacts] = useState(false);
  const [exportingDeals, setExportingDeals] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  // Step 1: file picked → upload for preview
  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setImportFile(file);
    setCsvPreview(null);
    setColumnMap({});
    setImportResult(null);
    setImportError(null);
    if (!file) return;

    setPreviewing(true);
    try {
      const preview = await previewCsv(file);
      setCsvPreview(preview);
      // Auto-map columns whose name contains a CRM field keyword
      const autoMap: Record<string, string> = {};
      for (const header of preview.headers) {
        const lower = header.toLowerCase().replace(/[^a-z]/g, "");
        if (lower.includes("email")) autoMap[header] = "email";
        else if (lower.includes("phone") || lower.includes("mobile")) autoMap[header] = "phone";
        else if (lower.includes("fullname") || lower.includes("name")) autoMap[header] = "name";
        else if (lower.includes("first")) autoMap[header] = "first_name";
        else if (lower.includes("last")) autoMap[header] = "last_name";
        else autoMap[header] = "";
      }
      setColumnMap(autoMap);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Failed to read CSV.");
    } finally {
      setPreviewing(false);
    }
  }

  // Step 2: Run import
  async function handleImport() {
    if (!importFile) return;
    // Build map: only entries with a value
    const activeMap: Record<string, string> = {};
    for (const [col, crm] of Object.entries(columnMap)) {
      if (crm) activeMap[crm] = col;
    }
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importContactsCsvMapped(importFile, activeMap);
      setImportResult(result);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setImporting(false);
    }
  }

  function resetImport() {
    setImportFile(null);
    setCsvPreview(null);
    setColumnMap({});
    setImportResult(null);
    setImportError(null);
  }

  // Export handlers
  async function handleExportContacts() {
    setExportingContacts(true);
    setExportMsg(null);
    try {
      const blob = await downloadContactsCsv();
      triggerBlobDownload(blob, `contacts-${new Date().toISOString().slice(0, 10)}.csv`);
      setExportMsg("Contacts exported successfully.");
    } catch (err) {
      setExportMsg(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExportingContacts(false);
    }
  }

  async function handleExportDeals() {
    setExportingDeals(true);
    setExportMsg(null);
    try {
      const blob = await downloadDealsCsv();
      triggerBlobDownload(blob, `deals-${new Date().toISOString().slice(0, 10)}.csv`);
      setExportMsg("Deals exported successfully.");
    } catch (err) {
      setExportMsg(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExportingDeals(false);
    }
  }

  const hasMappedField = Object.values(columnMap).some(Boolean);

  return (
    <section className="stack">

      {/* ── EXPORT ─────────────────────────────────────────────────────── */}
      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>⬇️ Export Data</h3>
            <p className="subtle-text">Download CRM data as UTF-8 CSV, scoped to your team.</p>
          </div>
        </div>
        {exportMsg && (
          <p className="subtle-text" style={{ marginBottom: "12px", color: exportMsg.includes("failed") ? "#f43f5e" : "#10b981" }}>
            {exportMsg}
          </p>
        )}
        <div className="csv-export-row">
          <button
            className="csv-export-btn"
            onClick={() => void handleExportContacts()}
            disabled={exportingContacts}
            type="button"
          >
            <span className="csv-export-icon">👥</span>
            <span>
              <strong>{exportingContacts ? "Exporting…" : "Export Contacts"}</strong>
              <small>All contacts with lead scores</small>
            </span>
          </button>
          <button
            className="csv-export-btn"
            onClick={() => void handleExportDeals()}
            disabled={exportingDeals}
            type="button"
          >
            <span className="csv-export-icon">💼</span>
            <span>
              <strong>{exportingDeals ? "Exporting…" : "Export Deals"}</strong>
              <small>All deals with stage & amount</small>
            </span>
          </button>
        </div>
      </div>

      {/* ── IMPORT ─────────────────────────────────────────────────────── */}
      <div className="panel-card">
        <div className="form-header">
          <div>
            <h3>📥 Import Contacts</h3>
            <p className="subtle-text">Upload any CSV and map your columns to CRM fields. Duplicate emails are skipped automatically.</p>
          </div>
        </div>

        {importError && (
          <div className="csv-error-banner">{importError}</div>
        )}

        {/* Step 1: Upload */}
        {!csvPreview && !importResult && (
          <div className="csv-upload-zone">
            <input
              id="csv-file-input"
              type="file"
              accept=".csv,text/csv"
              style={{ display: "none" }}
              onChange={(e) => void handleFileChange(e)}
            />
            <label htmlFor="csv-file-input" className="csv-upload-label">
              {previewing ? (
                <span>⏳ Reading file…</span>
              ) : (
                <>
                  <span className="csv-upload-icon">📂</span>
                  <strong>Click to choose CSV file</strong>
                  <small>UTF-8 encoded, any column names</small>
                </>
              )}
            </label>
          </div>
        )}

        {/* Step 2: Mapping + preview */}
        {csvPreview && !importResult && (
          <div className="csv-mapping-section">
            <h4 style={{ marginBottom: "12px" }}>
              Step 2 — Map your columns
              <span className="subtle-text" style={{ fontWeight: 400, marginLeft: "8px" }}>
                ({csvPreview.headers.length} columns detected)
              </span>
            </h4>

            <div className="csv-mapping-grid">
              {csvPreview.headers.map((header) => (
                <div key={header} className="csv-mapping-row">
                  <span className="csv-col-name" title={header}>{header}</span>
                  <span className="csv-arrow">→</span>
                  <select
                    value={columnMap[header] ?? ""}
                    onChange={(e) =>
                      setColumnMap((prev) => ({ ...prev, [header]: e.target.value }))
                    }
                  >
                    {CRM_FIELDS.map((f) => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            {/* Preview table */}
            {csvPreview.preview.length > 0 && (
              <div style={{ marginTop: "20px" }}>
                <h4 style={{ marginBottom: "8px" }}>Preview (first {csvPreview.preview.length} rows)</h4>
                <div className="table-wrap">
                  <table className="data-table" style={{ fontSize: "12px" }}>
                    <thead>
                      <tr>
                        {csvPreview.headers.map((h) => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {csvPreview.preview.map((row, i) => (
                        <tr key={i}>
                          {csvPreview.headers.map((h) => (
                            <td key={h}>{row[h] ?? ""}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="form-actions" style={{ marginTop: "20px" }}>
              <button
                className="primary-button"
                onClick={() => void handleImport()}
                disabled={importing || !hasMappedField}
                type="button"
              >
                {importing ? "⏳ Importing…" : "📥 Import Contacts"}
              </button>
              <button className="text-button" onClick={resetImport} type="button">
                ✕ Cancel
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Results */}
        {importResult && (
          <div className="csv-result-section">
            <div className="csv-result-stats">
              <div className="csv-result-stat" style={{ color: "#10b981" }}>
                <strong>{importResult.created}</strong>
                <small>Imported</small>
              </div>
              <div className="csv-result-stat" style={{ color: "#f59e0b" }}>
                <strong>{importResult.skipped}</strong>
                <small>Skipped (Duplicates)</small>
              </div>
              <div className="csv-result-stat" style={{ color: "#f43f5e" }}>
                <strong>{importResult.failed}</strong>
                <small>Failed</small>
              </div>
            </div>

            {importResult.errors.length > 0 && (
              <div style={{ marginTop: "16px" }}>
                <h4 style={{ marginBottom: "8px", color: "#f59e0b" }}>
                  ⚠️ Row Issues ({importResult.errors.length})
                </h4>
                <div className="table-wrap">
                  <table className="data-table" style={{ fontSize: "12px" }}>
                    <thead>
                      <tr>
                        <th>Row #</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.errors.slice(0, 20).map((e: ImportRowError) => (
                        <tr key={e.row_number}>
                          <td>{e.row_number}</td>
                          <td>{e.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="form-actions" style={{ marginTop: "16px" }}>
              <button className="primary-button" onClick={resetImport} type="button">
                Import Another File
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

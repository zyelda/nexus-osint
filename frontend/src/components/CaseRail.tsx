import { useMemo, useRef, useState } from 'react';
import type { GraphPayload, ToolSpec } from '../types';
import { DownloadIcon, FileIcon, PivotIcon, PlusIcon, RefreshIcon, TrashIcon, UploadIcon } from './Icons';

const STATUS_LABELS: Record<string, string> = {
  queued: 'menunggu',
  running: 'berjalan',
  success: 'selesai',
  partial: 'sebagian',
  not_found: 'tidak ditemukan',
  missing_key: 'butuh API key',
  error: 'gagal',
  timeout: 'timeout',
  blocked: 'diblokir',
};

const ENTITY_TYPES = [
  'person',
  'email',
  'phone',
  'username',
  'domain',
  'url',
  'ip',
  'nik',
  'npwp',
  'nim',
  'btc',
  'mac',
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface CaseRailProps {
  data: GraphPayload;
  tools: ToolSpec[];
  running: boolean;
  onRefresh: () => void;
  onAddEntity: (value: string, type: string) => Promise<void>;
  onUpload: (files: File[]) => Promise<void>;
  onRunAll: () => Promise<void>;
  onDelete: () => void;
  onExport: (format: string) => void;
}

export function CaseRail({ data, tools, running, onRefresh, onAddEntity, onUpload, onRunAll, onDelete, onExport }: CaseRailProps) {
  const [entityValue, setEntityValue] = useState('');
  const [entityType, setEntityType] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const labels = useMemo(() => new Map(tools.map((tool) => [tool.id, tool.label])), [tools]);
  const runningCount = data.runs.filter((run) => run.status === 'queued' || run.status === 'running').length;
  const sortedRuns = useMemo(
    () =>
      [...data.runs].sort((left, right) => {
        const leftTime = left.started_at ?? '';
        const rightTime = right.started_at ?? '';
        return rightTime.localeCompare(leftTime);
      }),
    [data.runs],
  );

  async function submitEntity() {
    const value = entityValue.trim();
    if (!value || adding) {
      return;
    }
    setAdding(true);
    setAddError('');
    try {
      await onAddEntity(value, entityType);
      setEntityValue('');
    } catch (error) {
      setAddError(error instanceof Error ? error.message : 'Entity tidak bisa ditambahkan.');
    } finally {
      setAdding(false);
    }
  }

  async function upload(list: FileList | null) {
    if (!list || list.length === 0 || uploading) {
      return;
    }
    const files = Array.from(list).filter((file) => file.size <= 16 * 1024 * 1024);
    if (files.length === 0) {
      setUploadError('Semua file melebihi 16 MB.');
      return;
    }
    setUploading(true);
    setUploadError('');
    try {
      await onUpload(files.slice(0, 8));
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'File gagal diunggah.');
    } finally {
      setUploading(false);
    }
  }

  return (
    <aside className="rail" aria-label="Panel kasus">
      <section className="rail-section">
        <div className="rail-head">
          <span className="file-tab">Identitas berkas</span>
          <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label="Muat ulang kasus" onClick={onRefresh}>
            <RefreshIcon size={15} />
          </button>
        </div>
        <h2 className="rail-case-title">{data.case.title}</h2>
        <dl className="meta-grid">
          <div>
            <dt>Dibuka</dt>
            <dd className="mono">{formatDate(data.case.created_at)}</dd>
          </div>
          <div>
            <dt>Diperbarui</dt>
            <dd className="mono">{formatDate(data.case.updated_at)}</dd>
          </div>
          <div>
            <dt>Entity</dt>
            <dd className="mono">{data.findings.counts.entities}</dd>
          </div>
          <div>
            <dt>Relasi</dt>
            <dd className="mono">{data.findings.counts.edges}</dd>
          </div>
          <div>
            <dt>Bukti</dt>
            <dd className="mono">{data.findings.counts.evidence}</dd>
          </div>
          <div>
            <dt>Tool</dt>
            <dd className="mono">{data.findings.counts.runs}</dd>
          </div>
        </dl>
        {data.case.purpose && <p className="meta-text">{data.case.purpose}</p>}
        {data.case.authorization_note && (
          <p className="meta-text">
            <strong>Dasar:</strong> {data.case.authorization_note}
          </p>
        )}
      </section>

      <section className="rail-section">
        <span className="file-tab">Tambah entity</span>
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submitEntity();
          }}
        >
          <label className="sr-only" htmlFor="entity-value">
            Nilai entity
          </label>
          <input
            id="entity-value"
            value={entityValue}
            onChange={(event) => setEntityValue(event.target.value)}
            placeholder="email, domain, username..."
          />
          <label className="sr-only" htmlFor="entity-type">
            Tipe entity
          </label>
          <select id="entity-type" value={entityType} onChange={(event) => setEntityType(event.target.value)}>
            <option value="">auto</option>
            {ENTITY_TYPES.map((type) => (
              <option value={type} key={type}>
                {type}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-icon" aria-label="Tambah entity" disabled={adding || !entityValue.trim()}>
            <PlusIcon size={17} />
          </button>
        </form>
        {addError && (
          <div className="notice notice-error" role="alert">
            {addError}
          </div>
        )}
      </section>

      <section className="rail-section">
        <span className="file-tab">Unggah bukti</span>
        <div
          className={`dropzone dropzone-compact${dragging ? ' active' : ''}`}
          role="button"
          tabIndex={0}
          aria-label="Unggah file bukti ke kasus"
          onClick={() => fileInput.current?.click()}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              fileInput.current?.click();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void upload(event.dataTransfer.files);
          }}
        >
          <UploadIcon size={18} />
          <div>
            <strong>{uploading ? 'Mengunggah dan membaca file...' : 'Tambah file ke kasus'}</strong>
            <span>Hasil ekstraksi langsung masuk ke graph.</span>
          </div>
          <input
            ref={fileInput}
            type="file"
            hidden
            multiple
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.docx,.xlsx,.csv,.json,.txt,.md,.log"
            onChange={(event) => {
              void upload(event.target.files);
              event.target.value = '';
            }}
          />
        </div>
        {uploadError && (
          <div className="notice notice-error" role="alert">
            {uploadError}
          </div>
        )}
        {!uploading && <p className="muted">Maks 16 MB per file, 8 file per unggahan.</p>}
      </section>

      <section className="rail-section">
        <div className="rail-head">
          <span className="file-tab">Log tool</span>
          <span className="mono run-status">{runningCount > 0 ? `${runningCount} aktif` : 'idle'}</span>
        </div>
        {sortedRuns.length === 0 ? (
          <div className="empty-block" style={{ marginTop: 10 }}>
            <strong>Belum ada run</strong>
            Tool akan muncul di sini setelah dijalankan.
          </div>
        ) : (
          <ul className="run-list">
            {sortedRuns.slice(0, 30).map((run) => (
              <li className={`run-item run-${run.status}`} key={run.id}>
                <span className="run-dot" />
                <div>
                  <span className="run-tool mono">{labels.get(run.tool_id) ?? run.tool_id}</span>
                  <span className="run-status">{STATUS_LABELS[run.status] ?? run.status}</span>
                  {run.error_message && <span className="run-error">{run.error_message}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="btn btn-block" onClick={() => void onRunAll()} disabled={running}>
          <PivotIcon size={15} />
          {running ? 'Tool sedang berjalan' : 'Jalankan pivot tersisa'}
        </button>
      </section>

      <section className="rail-section">
        <span className="file-tab">Ekspor</span>
        <div className="export-grid">
          <button type="button" className="btn btn-sm" onClick={() => onExport('json')}>
            <DownloadIcon size={14} />
            JSON
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onExport('csv')}>
            <FileIcon size={14} />
            CSV
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onExport('pdf')}>
            <FileIcon size={14} />
            PDF
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onExport('graphml')}>
            <DownloadIcon size={14} />
            GraphML
          </button>
        </div>
        <p className="muted">CSV berisi arsip zip: entity, relasi, bukti, run, dan findings.</p>
      </section>

      <section className="rail-section rail-danger">
        <button type="button" className="btn btn-danger btn-block" onClick={onDelete}>
          <TrashIcon size={15} />
          Hapus kasus
        </button>
      </section>
    </aside>
  );
}

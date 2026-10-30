import { useEffect, useRef, useState } from 'react';
import { api, backendConfigured } from '../api';
import type { CaseSummary, ParsedEntity, ToolSpec } from '../types';
import { BookIcon, CloseIcon, FileIcon, PlusIcon, SearchIcon, UploadIcon } from './Icons';

interface LandingProps {
  tools: ToolSpec[];
  cases: CaseSummary[];
  casesLoading: boolean;
  onOpenCase: (caseId: string) => void;
  onCreated: (caseId: string) => void;
  onOpenDocs: () => void;
  onToast: (message: string, tone?: 'info' | 'error') => void;
}

const MAX_FILE = 16 * 1024 * 1024;
const MAX_FILES = 8;

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function Landing({
  tools,
  cases,
  casesLoading,
  onOpenCase,
  onCreated,
  onOpenDocs,
  onToast,
}: LandingProps) {
  const [text, setText] = useState('');
  const [entities, setEntities] = useState<ParsedEntity[]>([]);
  const [parsedText, setParsedText] = useState('');
  const [parseState, setParseState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState('');
  const [purpose, setPurpose] = useState('');
  const [authorization, setAuthorization] = useState('');
  const [autorun, setAutorun] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const value = text.trim();
    if (!value) {
      setEntities([]);
      setParsedText('');
      setParseState('idle');
      return;
    }
    let cancelled = false;
    setParseState('loading');
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.parse(text);
        if (cancelled) {
          return;
        }
        setEntities(result.entities);
        setParsedText(text);
        setParseState('ready');
      } catch {
        if (!cancelled) {
          setParseState('error');
        }
      }
    }, 420);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [text]);

  function addFiles(list: FileList | null) {
    if (!list) {
      return;
    }
    const incoming = Array.from(list);
    const accepted: File[] = [];
    for (const file of incoming) {
      if (file.size > MAX_FILE) {
        onToast(`${file.name} melebihi 16 MB dan dilewati.`, 'error');
        continue;
      }
      accepted.push(file);
    }
    setFiles((current) => [...current, ...accepted].slice(0, MAX_FILES));
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, position) => position !== index));
  }

  function removeEntity(index: number) {
    setEntities((current) => current.filter((_, position) => position !== index));
  }

  async function submit() {
    if (busy) {
      return;
    }
    if (!text.trim() && files.length === 0) {
      setError('Isi minimal satu entity atau unggah satu file bukti.');
      return;
    }
    setBusy(true);
    setError('');
    const useParsed = parsedText === text && entities.length > 0;
    try {
      const created = await api.createCase({
        text: useParsed ? '' : text,
        entities: useParsed
          ? entities.map((item) => ({
              type: item.type,
              value: item.value,
              normalized: item.normalized,
              confidence: item.confidence,
              source: item.source ?? 'intake',
            }))
          : [],
        title,
        purpose,
        authorization_note: authorization,
        autorun: false,
      });
      const caseId = created.case.id;
      let uploadIssue = false;
      let runNote = autorun ? 'Kasus dibuka. Tool berjalan di latar belakang.' : 'Kasus dibuka tanpa menjalankan tool.';
      if (files.length > 0) {
        try {
          await api.uploadFiles(caseId, files);
        } catch (uploadError) {
          uploadIssue = true;
          onToast(uploadError instanceof Error ? uploadError.message : 'Sebagian file gagal diunggah.', 'error');
        }
      }
      if (autorun) {
        try {
          const runs = await api.startRuns(caseId, { skip_existing: true });
          if (runs.count === 0) {
            runNote = 'Kasus dibuat. Tidak ada tool baru yang perlu dijalankan.';
          } else if (runs.deferred > 0) {
            runNote = `${runs.count} tool berjalan, ${runs.deferred} ditunda karena batas batch. Jalankan lagi setelah selesai.`;
          }
        } catch (runError) {
          onToast(runError instanceof Error ? runError.message : 'Tool otomatis gagal dimulai.', 'error');
        }
      }
      if (!uploadIssue) {
        onToast(runNote);
      }
      onCreated(caseId);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Kasus tidak bisa dibuat.');
    } finally {
      setBusy(false);
    }
  }

  const parseLabel =
    parseState === 'loading'
      ? 'Membaca entity...'
      : parseState === 'ready'
        ? `${entities.length} entity dikenali`
        : parseState === 'error'
          ? 'Parser gagal, input dikirim apa adanya'
          : 'Tempel entity untuk melihat pecahannya';

  return (
    <main className="landing">
      {!backendConfigured && (
        <div className="notice notice-warn backend-notice" role="status">
          <strong>Backend belum terhubung.</strong> Deployment ini hanya menyajikan antarmuka. Isi
          <code> VITE_API_BASE </code>
          di environment Vercel, lalu deploy ulang.
          <button type="button" className="link-btn" onClick={onOpenDocs}>
            Buka panduan deploy
          </button>
        </div>
      )}
      <section className="masthead">
        <div>
          <p className="eyebrow">Arsip investigasi sumber publik</p>
          <h1 className="masthead-title">
            Mulai dari satu berkas,
            <br />
            lacak seluruh koneksinya.
          </h1>
          <p className="masthead-lede">
            Tempel nama, email, nomor, username, domain, atau unggah dokumen. Berkas memecah entity, menjalankan tool
            yang relevan, dan menyusun peta bukti yang bisa diaudit.
          </p>
        </div>
        <div className="masthead-note">
          <span className="file-tab">Batas penggunaan</span>
          <p>
            Gunakan hanya untuk tujuan yang sah. Tool tidak melakukan lookup pemilik nomor, NIK, atau akun di balik
            login.
          </p>
        </div>
      </section>

      <section className="intake-sheet" aria-labelledby="intake-title">
        <div className="sheet-head">
          <span className="file-tab">Formulir intake</span>
          <h2 id="intake-title">Entity target</h2>
          <p>Pisahkan dengan baris baru atau koma. Format "label: nilai" juga dikenali.</p>
        </div>

        <label className="sr-only" htmlFor="intake-text">
          Entity target
        </label>
        <textarea
          id="intake-text"
          className="intake-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder={'Nama: Budi Santoso\nemail: budi@example.com\nhp: 081234567890\nusername: budi_s\nhttps://example.com'}
          spellCheck={false}
        />

        <div className="parse-row">
          <span className="mono parse-status" aria-live="polite">
            {parseLabel}
          </span>
          {entities.length > 0 && (
            <button type="button" className="link-btn" onClick={() => setEntities([])}>
              Kosongkan chip
            </button>
          )}
        </div>

        {entities.length > 0 && (
          <div className="chips" aria-label="Entity yang dikenali">
            {entities.map((item, index) => (
              <span className="chip" key={`${item.type}:${item.normalized}:${index}`}>
                <span className="chip-type">{item.type}</span>
                <span className="chip-value" title={item.value}>
                  {item.value}
                </span>
                <span className="chip-conf">{Math.round(item.confidence * 100)}%</span>
                <button
                  type="button"
                  className="chip-remove"
                  aria-label={`Hapus ${item.value}`}
                  onClick={() => removeEntity(index)}
                >
                  <CloseIcon size={14} />
                </button>
              </span>
            ))}
          </div>
        )}

        <div
          className={`dropzone${dragging ? ' active' : ''}`}
          role="button"
          tabIndex={0}
          aria-label="Unggah file bukti"
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
            addFiles(event.dataTransfer.files);
          }}
        >
          <UploadIcon size={22} />
          <div>
            <strong>Unggah bukti</strong>
            <span>Gambar, PDF, DOCX, XLSX, CSV, JSON, TXT. Maks 16 MB per file, 8 file per intake.</span>
          </div>
          <input
            ref={fileInput}
            type="file"
            hidden
            multiple
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.docx,.xlsx,.csv,.json,.txt,.md,.log"
            onChange={(event) => {
              addFiles(event.target.files);
              event.target.value = '';
            }}
          />
        </div>

        {files.length > 0 && (
          <ul className="file-list">
            {files.map((file, index) => (
              <li key={`${file.name}:${index}`}>
                <FileIcon size={14} />
                <span title={file.name}>{file.name}</span>
                <span className="mono">{Math.round(file.size / 1024)} KB</span>
                <button type="button" aria-label={`Hapus ${file.name}`} onClick={() => removeFile(index)}>
                  <CloseIcon size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <details className="case-details">
          <summary>Detail kasus (opsional)</summary>
          <label className="field">
            <span>Judul kasus</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Kosongkan untuk memakai entity pertama"
            />
          </label>
          <label className="field">
            <span>Tujuan</span>
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              placeholder="Contoh: verifikasi identitas vendor sebelum kontrak"
            />
          </label>
          <label className="field">
            <span>Dasar kewenangan</span>
            <input
              value={authorization}
              onChange={(event) => setAuthorization(event.target.value)}
              placeholder="Contoh: penugasan tim audit internal, 12 Oktober 2026"
            />
          </label>
        </details>

        <label className="check-row">
          <input type="checkbox" checked={autorun} onChange={(event) => setAutorun(event.target.checked)} />
          Jalankan tool otomatis setelah intake
        </label>

        {error && (
          <div className="notice notice-error" role="alert">
            {error}
          </div>
        )}

        <button type="button" className="btn btn-primary btn-submit" onClick={() => void submit()} disabled={busy}>
          <SearchIcon size={17} />
          {busy ? 'Menyiapkan berkas...' : 'Buka berkas kasus'}
        </button>
        <p className="mono parse-status" style={{ marginTop: 8 }}>
          Ctrl atau Cmd + Enter untuk membuka kasus
        </p>
      </section>

      <aside className="landing-side">
        <section className="side-section">
          <span className="file-tab">Berkas terakhir</span>
          <h2>Kasus tersimpan</h2>
          {casesLoading ? (
            <div className="empty-block" aria-live="polite">
              <strong>Memuat berkas...</strong>
              Daftar kasus sedang dibaca dari database lokal.
            </div>
          ) : cases.length === 0 ? (
            <div className="empty-block">
              <strong>Belum ada kasus</strong>
              Intake pertama akan muncul di sini setelah disimpan.
            </div>
          ) : (
            <ul className="case-list">
              {cases.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => onOpenCase(item.id)}>
                    <strong>{item.title}</strong>
                    <span>
                      {formatDate(item.updated_at)} / {item.entity_count} entity
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="side-section side-note">
          <span className="file-tab">Cakupan tool</span>
          {tools.length > 0 ? (
            <p>
              {tools.length} tool terdaftar. {tools.filter((tool) => tool.requires_key).length} tool membutuhkan API key
              dan akan ditandai jika belum dikonfigurasi.
            </p>
          ) : (
            <p>Daftar tool dibaca dari backend. Setelah backend terhubung, jumlah dan status key muncul di sini.</p>
          )}
          <p>
            Semua hasil masuk ke graph yang sama, lengkap dengan sumber, bobot bukti, dan tingkat keyakinan.
          </p>
        </section>

        <section className="side-section side-note">
          <span className="file-tab">Panduan</span>
          <p>
            Penjelasan lengkap tentang alur intake, cara membaca skor keyakinan, daftar tool, API, dan deploy ada di
            halaman dokumentasi.
          </p>
          <button type="button" className="btn btn-block" onClick={onOpenDocs}>
            <BookIcon size={16} />
            Buka dokumentasi
          </button>
        </section>

        <section className="side-section side-note">
          <span className="file-tab">Alur kerja</span>
          <p>
            Intake memecah entity, tool berjalan paralel sesuai tipe, lalu panel temuan menyusun kandidat identitas dan
            pivot berikutnya. Anda tetap memutuskan langkah akhir.
          </p>
          <p className="mono" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <PlusIcon size={12} /> Tambah entity dari hasil tool, bukan hanya dari ketikan awal.
          </p>
        </section>
      </aside>
    </main>
  );
}

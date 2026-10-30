import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api, backendConfigured, getToken, setToken } from './api';
import { CaseRail } from './components/CaseRail';
import { Documentation } from './components/Documentation';
import { FindingsPanel } from './components/FindingsPanel';
import { GraphView } from './components/GraphView';
import { BookIcon, KeyIcon, MoonIcon, RefreshIcon, SunIcon } from './components/Icons';
import { Landing } from './components/Landing';
import { ToastStack, type ToastItem } from './components/ToastStack';
import { TokenDialog } from './components/TokenDialog';
import type { CaseSummary, GraphPayload, StreamEvent, ToolSpec } from './types';

type Theme = 'light' | 'dark';
type StreamState = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'offline';

function readCaseId(): string | null {
  return new URLSearchParams(window.location.search).get('case');
}

function readDocs(): boolean {
  return new URLSearchParams(window.location.search).get('doc') === '1';
}

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem('berkas.theme');
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }
  } catch {
    // storage can be unavailable
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export default function App() {
  const [caseId, setCaseId] = useState<string | null>(() => readCaseId());
  const [docsOpen, setDocsOpen] = useState(() => readDocs());
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [streamState, setStreamState] = useState<StreamState>('idle');
  const [tokenOpen, setTokenOpen] = useState(false);
  const [token, setTokenValue] = useState(() => getToken());
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [focusRequest, setFocusRequest] = useState<{ id: string; token: number } | null>(null);
  const toastCounter = useRef(0);
  const failureCount = useRef(0);

  const addToast = useCallback((message: string, tone: 'info' | 'error' = 'info') => {
    toastCounter.current += 1;
    const id = toastCounter.current;
    setToasts((current) => [...current.slice(-2), { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 4600);
  }, []);

  const loadCase = useCallback(
    async (id: string, silent = false) => {
      if (!silent) {
        setLoading(true);
      }
      try {
        const payload = await api.graph(id);
        setGraph(payload);
        setError('');
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : 'Kasus tidak bisa dimuat.';
        setError(message);
        if (caught instanceof ApiError && caught.status === 401) {
          setTokenOpen(true);
        }
        if (!silent) {
          setGraph(null);
        }
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [],
  );

  const refreshCases = useCallback(async () => {
    if (!backendConfigured) {
      setCases([]);
      setCasesLoading(false);
      return;
    }
    setCasesLoading(true);
    try {
      setCases(await api.listCases());
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setTokenOpen(true);
      }
    } finally {
      setCasesLoading(false);
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('berkas.theme', theme);
    } catch {
      // storage can be unavailable
    }
  }, [theme]);

  useEffect(() => {
    if (!backendConfigured) {
      return;
    }
    api
      .tools()
      .then(setTools)
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 401) {
          setTokenOpen(true);
        } else {
          addToast('Daftar tool tidak bisa dimuat.', 'error');
        }
      });
    api
      .health()
      .then((health) => {
        if (health.auth_required && !getToken()) {
          setTokenOpen(true);
        }
      })
      .catch(() => {
        setStreamState('offline');
      });
  }, [addToast]);

  useEffect(() => {
    if (!caseId) {
      void refreshCases();
    }
  }, [caseId, refreshCases]);

  useEffect(() => {
    if (!caseId || docsOpen) {
      if (!caseId) {
        setGraph(null);
        setStreamState('idle');
      }
      return;
    }
    void loadCase(caseId);
  }, [caseId, docsOpen, loadCase]);

  useEffect(() => {
    const onPop = () => {
      setCaseId(readCaseId());
      setDocsOpen(readDocs());
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (!caseId || docsOpen) {
      return;
    }
    setStreamState('connecting');
    const source = new EventSource(api.streamUrl(caseId));
    let refreshTimer: number | undefined;
    const scheduleRefresh = (delay = 300) => {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        void loadCase(caseId, true);
      }, delay);
    };

    source.onopen = () => setStreamState('live');
    source.onmessage = (event) => {
      let message: StreamEvent;
      try {
        message = JSON.parse(event.data) as StreamEvent;
      } catch {
        return;
      }
      if (message.type === 'hello') {
        setStreamState('live');
        if (message.findings) {
          const incoming = message.findings;
          setGraph((current) => (current ? { ...current, findings: incoming } : current));
        }
        return;
      }
      if (message.type === 'findings.updated' && message.findings) {
        const incoming = message.findings;
        setGraph((current) => (current ? { ...current, findings: incoming } : current));
        return;
      }
      if (message.type === 'run.started') {
        scheduleRefresh(120);
        return;
      }
      if (message.type === 'run.finished') {
        scheduleRefresh(220);
        if (message.status === 'error' || message.status === 'timeout') {
          failureCount.current += 1;
        }
        return;
      }
      if (message.type === 'graph.updated') {
        scheduleRefresh(220);
        return;
      }
      if (message.type === 'runs.completed') {
        setStreamState('live');
        if (message.findings) {
          const incoming = message.findings;
          setGraph((current) => (current ? { ...current, findings: incoming } : current));
        }
        scheduleRefresh(0);
        const failures = failureCount.current;
        failureCount.current = 0;
        addToast(
          failures > 0
            ? `${failures} tool gagal atau timeout. Detail ada di log tool.`
            : 'Semua tool yang antre sudah selesai.',
          failures > 0 ? 'error' : 'info',
        );
      }
    };
    source.onerror = () => {
      setStreamState('reconnecting');
    };
    return () => {
      window.clearTimeout(refreshTimer);
      source.close();
    };
  }, [caseId, docsOpen, loadCase, addToast]);

  const openCase = useCallback((id: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set('case', id);
    url.searchParams.delete('doc');
    window.history.pushState({}, '', url);
    setCaseId(id);
    setDocsOpen(false);
    setGraph(null);
    setError('');
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  const goHome = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete('case');
    url.searchParams.delete('doc');
    window.history.pushState({}, '', url);
    setCaseId(null);
    setDocsOpen(false);
    setGraph(null);
    setError('');
    setStreamState('idle');
    void refreshCases();
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [refreshCases]);

  const openDocs = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.set('doc', '1');
    window.history.pushState({}, '', url);
    setDocsOpen(true);
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  const closeDocs = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete('doc');
    window.history.pushState({}, '', url);
    setDocsOpen(false);
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  const runAll = useCallback(async () => {
    if (!caseId) {
      return;
    }
    try {
      const result = await api.startRuns(caseId, { skip_existing: true });
      if (result.count === 0) {
        addToast('Tidak ada pivot baru yang tersisa untuk entity saat ini.');
      } else {
        addToast(
          result.deferred > 0
            ? `${result.count} tool dimasukkan, ${result.deferred} ditunda karena batas batch. Jalankan lagi setelah selesai.`
            : `${result.count} tool dimasukkan ke antrean.`,
        );
        await loadCase(caseId, true);
      }
    } catch (caught) {
      addToast(caught instanceof Error ? caught.message : 'Tool tidak bisa dimulai.', 'error');
    }
  }, [caseId, loadCase, addToast]);

  const pivot = useCallback(
    async (entityId: string, toolId: string) => {
      if (!caseId) {
        return;
      }
      try {
        const result = await api.pivot(caseId, entityId, toolId);
        addToast(`${result.runs.length} pivot dimulai.`);
        await loadCase(caseId, true);
      } catch (caught) {
        addToast(caught instanceof Error ? caught.message : 'Pivot gagal dimulai.', 'error');
      }
    },
    [caseId, loadCase, addToast],
  );

  const addEntity = useCallback(
    async (value: string, type: string) => {
      if (!caseId) {
        throw new Error('Kasus belum dibuka.');
      }
      await api.addEntity(caseId, value, type || undefined);
      addToast('Entity ditambahkan ke kasus.');
      await loadCase(caseId, true);
    },
    [caseId, loadCase, addToast],
  );

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (!caseId) {
        throw new Error('Kasus belum dibuka.');
      }
      const result = await api.uploadFiles(caseId, files);
      const failed = result.files.filter((item) => item.status === 'error').length;
      if (failed > 0) {
        addToast(`${failed} file gagal dibaca. Periksa format atau ukuran file.`, 'error');
      } else {
        addToast(`${result.count} file dibaca dan masuk ke graph.`);
      }
      await loadCase(caseId, true);
    },
    [caseId, loadCase, addToast],
  );

  const removeCase = useCallback(async () => {
    if (!caseId) {
      return;
    }
    if (!window.confirm('Hapus kasus ini beserta seluruh entity, bukti, dan file unggahan?')) {
      return;
    }
    try {
      await api.deleteCase(caseId);
      addToast('Kasus dihapus.');
      goHome();
    } catch (caught) {
      addToast(caught instanceof Error ? caught.message : 'Kasus tidak bisa dihapus.', 'error');
    }
  }, [caseId, goHome, addToast]);

  const saveToken = useCallback((value: string) => {
    setToken(value);
    setTokenValue(value);
    setTokenOpen(false);
    addToast(value ? 'Token disimpan. Data dimuat ulang.' : 'Token dihapus. Data dimuat ulang.');
    window.setTimeout(() => window.location.reload(), 350);
  }, [addToast]);

  const running = graph?.runs.some((run) => run.status === 'queued' || run.status === 'running') ?? false;
  const runningCount = graph?.runs.filter((run) => run.status === 'queued' || run.status === 'running').length ?? 0;

  const streamLabel =
    streamState === 'live'
      ? 'live'
      : streamState === 'connecting'
        ? 'menghubungkan'
        : streamState === 'reconnecting'
          ? 'menyambung ulang'
          : streamState === 'offline'
            ? 'offline'
            : 'siap';

  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" onClick={goHome} aria-label="Kembali ke formulir intake">
          Berkas <span>OSINT</span>
        </button>
        {!docsOpen && graph && (
          <div className="topbar-case">
            <span className="topbar-case-label">Berkas aktif</span>
            <h1 title={graph.case.title}>{graph.case.title}</h1>
          </div>
        )}
        <div className="topbar-spacer" />
        {!docsOpen && caseId && (
          <span className={`live-status ${streamState}`} aria-live="polite">
            <span className="live-dot" />
            {streamLabel}
          </span>
        )}
        {!docsOpen && graph && <span className="mono run-status">{runningCount} berjalan</span>}
        <button
          type="button"
          className="btn btn-ghost docs-btn"
          aria-label="Buka dokumentasi"
          title="Dokumentasi"
          aria-current={docsOpen ? 'page' : undefined}
          onClick={openDocs}
        >
          <BookIcon size={18} />
          <span>Dokumentasi</span>
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label={theme === 'dark' ? 'Aktifkan tema terang' : 'Aktifkan tema gelap'}
          title={theme === 'dark' ? 'Tema terang' : 'Tema gelap'}
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark' ? <SunIcon size={18} /> : <MoonIcon size={18} />}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label="Atur token API"
          title="Token API"
          onClick={() => setTokenOpen(true)}
        >
          <KeyIcon size={18} />
        </button>
        {caseId && (
          <button type="button" className="btn" onClick={goHome}>
            Kasus baru
          </button>
        )}
      </header>

      {docsOpen ? (
        <Documentation tools={tools} onBack={closeDocs} />
      ) : caseId ? (
        loading && !graph ? (
          <main className="landing">
            <div className="empty-block" style={{ gridColumn: '1 / -1' }} aria-live="polite">
              <strong>Membuka berkas...</strong>
              Entity, bukti, dan graph sedang dimuat dari database lokal.
            </div>
          </main>
        ) : error && !graph ? (
          <main className="landing">
            <div className="empty-block" style={{ gridColumn: '1 / -1' }} role="alert">
              <strong>Kasus tidak bisa dibuka</strong>
              {error}
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button type="button" className="btn" onClick={() => void loadCase(caseId)}>
                  <RefreshIcon size={15} />
                  Coba lagi
                </button>
                <button type="button" className="btn" onClick={goHome}>
                  Kembali ke intake
                </button>
              </div>
            </div>
          </main>
        ) : graph ? (
          <div className="workspace">
            <CaseRail
              data={graph}
              tools={tools}
              running={running}
              onRefresh={() => void loadCase(caseId, true)}
              onAddEntity={addEntity}
              onUpload={uploadFiles}
              onRunAll={runAll}
              onDelete={() => void removeCase()}
              onExport={(format) => {
                window.location.href = api.exportUrl(caseId, format);
              }}
            />
            <GraphView
              data={graph}
              tools={tools}
              loading={loading}
              running={running}
              theme={theme}
              focusRequest={focusRequest}
              onPivot={(entityId, toolId) => void pivot(entityId, toolId)}
              onRefresh={() => void loadCase(caseId, true)}
            />
            <FindingsPanel
              caseId={caseId}
              findings={graph.findings}
              running={running}
              onPivot={(entityId, toolId) => void pivot(entityId, toolId)}
              onFocusEntity={(entityId) => setFocusRequest({ id: entityId, token: Date.now() })}
              onRefresh={() => void loadCase(caseId, true)}
              onToast={addToast}
            />
          </div>
        ) : null
      ) : (
        <Landing
          tools={tools}
          cases={cases}
          casesLoading={casesLoading}
          onOpenCase={openCase}
          onCreated={openCase}
          onOpenDocs={openDocs}
          onToast={addToast}
        />
      )}

      {!caseId || docsOpen ? (
        <footer className="app-footer">
          <span>Berkas, arsip investigasi sumber publik.</span>
          <span>
            Dibuat oleh{' '}
            <a href="https://github.com/zyelda" target="_blank" rel="noreferrer">
              Zulmatoriq (zyelda)
            </a>
          </span>
          {!docsOpen && (
            <button type="button" className="link-btn" onClick={openDocs}>
              Buka dokumentasi
            </button>
          )}
        </footer>
      ) : null}

      <TokenDialog
        open={tokenOpen}
        current={token}
        onClose={() => setTokenOpen(false)}
        onSave={saveToken}
      />
      <ToastStack toasts={toasts} />
    </div>
  );
}

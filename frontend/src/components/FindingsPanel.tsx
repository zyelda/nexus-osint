import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Findings, SummaryCitation, SummaryResponse } from '../types';
import { AlertIcon, CheckIcon, ExternalIcon, PivotIcon, RefreshIcon } from './Icons';

type Tab = 'summary' | 'findings' | 'clues' | 'timeline';
type Audience = 'public' | 'analyst';

function formatDateTime(value: string): string {
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

function CitationChips({ ids, citations }: { ids: string[]; citations: SummaryCitation[] }) {
  const byId = new Map(citations.map((item) => [item.id, item]));
  const items = ids.map((id) => byId.get(id)).filter((item): item is SummaryCitation => Boolean(item));
  if (items.length === 0) {
    return null;
  }
  return (
    <span className="citation-row" aria-label="Bukti pendukung">
      {items.map((item) =>
        item.source_url ? (
          <a
            key={item.id}
            className="citation-chip"
            href={item.source_url}
            target="_blank"
            rel="noreferrer noopener"
            title={item.label}
          >
            {item.category}
          </a>
        ) : (
          <span className="citation-chip" key={item.id} title={item.label}>
            {item.category}
          </span>
        ),
      )}
    </span>
  );
}

function summaryText(summary: SummaryResponse): string {
  const lines = [summary.headline, '', summary.confidence.plain, ''];
  for (const point of summary.points) {
    lines.push(`- ${point.text}`);
  }
  if (summary.narrative.length > 0) {
    lines.push('', 'Naratif');
    for (const paragraph of summary.narrative) {
      lines.push(paragraph.text, '');
    }
  }
  if (summary.limits.length > 0) {
    lines.push('Batasan');
    for (const item of summary.limits) {
      lines.push(`- ${item}`);
    }
    lines.push('');
  }
  lines.push(summary.notice);
  return lines.join('\n').trim();
}

interface FindingsPanelProps {
  caseId: string;
  findings: Findings;
  running: boolean;
  onPivot: (entityId: string, toolId: string) => void;
  onFocusEntity: (entityId: string) => void;
  onRefresh: () => void;
  onToast: (message: string, tone?: 'info' | 'error') => void;
}

export function FindingsPanel({ caseId, findings, running, onPivot, onFocusEntity, onRefresh, onToast }: FindingsPanelProps) {
  const [tab, setTab] = useState<Tab>('summary');
  const [audience, setAudience] = useState<Audience>('public');
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [summaryState, setSummaryState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [summaryError, setSummaryError] = useState('');
  const [copied, setCopied] = useState(false);
  const requestSeq = useRef(0);
  const loadedFor = useRef('');

  const confidence = findings.confidence;
  const bandClass = confidence.band.toLowerCase();

  const loadSummary = useCallback(
    async (target: Audience, refresh = false) => {
      const seq = requestSeq.current + 1;
      requestSeq.current = seq;
      setSummaryState('loading');
      setSummaryError('');
      try {
        const result = await api.summary(caseId, target, refresh);
        if (seq !== requestSeq.current) {
          return;
        }
        setSummary(result);
        setSummaryState('ready');
        if (refresh) {
          onToast('Ringkasan disusun ulang dari bukti terbaru.');
        }
      } catch (error) {
        if (seq !== requestSeq.current) {
          return;
        }
        setSummaryState('error');
        setSummaryError(error instanceof Error ? error.message : 'Ringkasan tidak bisa disusun.');
      }
    },
    [caseId, onToast],
  );

  useEffect(() => {
    if (loadedFor.current === caseId) {
      return;
    }
    loadedFor.current = caseId;
    setAudience('public');
    setSummary(null);
    void loadSummary('public');
  }, [caseId, loadSummary]);

  function selectAudience(next: Audience) {
    if (next === audience) {
      return;
    }
    setAudience(next);
    setSummary(null);
    setCopied(false);
    void loadSummary(next);
  }

  async function copySummary() {
    if (!summary) {
      return;
    }
    try {
      await navigator.clipboard.writeText(summaryText(summary));
      setCopied(true);
      onToast('Ringkasan disalin ke papan klip.');
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      onToast('Browser menolak akses papan klip. Pilih teks secara manual.', 'error');
    }
  }

  return (
    <aside className="findings" aria-label="Panel ringkasan temuan">
      <div className="findings-head">
        <span className="file-tab">Ringkasan temuan</span>
        <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label="Muat ulang temuan" onClick={onRefresh}>
          <RefreshIcon size={15} />
        </button>
      </div>

      <div className="confidence-block">
        <div className="confidence-row">
          <div className="confidence-score">
            <strong>{confidence.score}</strong>
            <span>/100</span>
          </div>
          <div className={`confidence-stamp band-${bandClass}`}>{confidence.band}</div>
        </div>
        <p className="confidence-caption">Keyakinan bukti</p>
        <div
          className="confidence-bar"
          role="progressbar"
          aria-valuenow={confidence.score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Skor keyakinan bukti"
        >
          <span style={{ width: `${confidence.score}%` }} />
        </div>
        <p className="confidence-meta">
          {confidence.evidence_count} bukti / {confidence.source_count} sumber / {confidence.conflicts} konflik
        </p>
        <p className="confidence-meta">Skor ini menilai kekuatan bukti kasus, bukan menetapkan identitas seseorang.</p>
        {confidence.why.length > 0 && (
          <ul className="why-list">
            {confidence.why.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="findings-tabs" role="tablist" aria-label="Bagian temuan">
        <button
          type="button"
          role="tab"
          id="tab-summary"
          aria-selected={tab === 'summary'}
          aria-controls="panel-summary"
          onClick={() => setTab('summary')}
        >
          Ringkasan
        </button>
        <button
          type="button"
          role="tab"
          id="tab-findings"
          aria-selected={tab === 'findings'}
          aria-controls="panel-findings"
          onClick={() => setTab('findings')}
        >
          Temuan
        </button>
        <button
          type="button"
          role="tab"
          id="tab-clues"
          aria-selected={tab === 'clues'}
          aria-controls="panel-clues"
          onClick={() => setTab('clues')}
        >
          Clue ({findings.clues.length})
        </button>
        <button
          type="button"
          role="tab"
          id="tab-timeline"
          aria-selected={tab === 'timeline'}
          aria-controls="panel-timeline"
          onClick={() => setTab('timeline')}
        >
          Linimasa
        </button>
      </div>

      {tab === 'summary' && (
        <div role="tabpanel" id="panel-summary" aria-labelledby="tab-summary">
          <div className="summary-toolbar">
            <div className="segmented" role="group" aria-label="Pilih pembaca ringkasan">
              <button
                type="button"
                aria-pressed={audience === 'public'}
                className={audience === 'public' ? 'active' : ''}
                onClick={() => selectAudience('public')}
              >
                Awam
              </button>
              <button
                type="button"
                aria-pressed={audience === 'analyst'}
                className={audience === 'analyst' ? 'active' : ''}
                onClick={() => selectAudience('analyst')}
              >
                Analis
              </button>
            </div>
            <div className="summary-toolbar-actions">
              {summary && (
                <button type="button" className="btn btn-sm" onClick={() => void copySummary()}>
                  {copied ? <CheckIcon size={14} /> : null}
                  {copied ? 'Tersalin' : 'Salin'}
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void loadSummary(audience, true)}
                disabled={summaryState === 'loading'}
              >
                {summaryState === 'loading' ? 'Menyusun...' : 'Susun ulang'}
              </button>
            </div>
          </div>

          {summaryState === 'loading' && (
            <div className="summary-state" aria-live="polite">
              <strong>Menyusun ringkasan dari bukti...</strong>
              Tiga lapisan sedang dibuat: ringkasan satu menit, naratif, dan lampiran analis.
            </div>
          )}

          {summaryState === 'error' && (
            <div className="notice notice-error" role="alert">
              <p>{summaryError}</p>
              <button type="button" className="btn btn-sm" onClick={() => void loadSummary(audience)}>
                Coba lagi
              </button>
            </div>
          )}

          {summaryState === 'ready' && summary && (
            <div className="summary-sheet">
              <section className="summary-brief">
                <p className="summary-kicker">Ringkasan satu menit</p>
                <h3>{summary.headline}</h3>
                <p className="summary-confidence">{summary.confidence.plain}</p>
                <ul className="summary-points">
                  {summary.points.map((point) => (
                    <li key={point.text}>
                      <p>{point.text}</p>
                      <CitationChips ids={point.citation_ids} citations={summary.citations} />
                    </li>
                  ))}
                </ul>
              </section>

              {summary.redaction.policy === 'partial' && (
                <div className="summary-redaction">
                  <span>
                    {summary.redaction.applied
                      ? `PII disamarkan: ${summary.redaction.fields.join(', ')}. Mode awam tidak menampilkan data penuh.`
                      : 'Mode awam memakai penyamaran sebagian PII. Tidak ada PII terdeteksi di ringkasan ini.'}
                  </span>
                  <button type="button" className="btn btn-sm" onClick={() => selectAudience('analyst')}>
                    Tampilkan PII
                  </button>
                </div>
              )}

              {summary.limits.length > 0 && (
                <section className="summary-limits">
                  <h4>Batasan yang perlu dibaca</h4>
                  <ul>
                    {summary.limits.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="summary-narrative">
                <h4>Naratif</h4>
                {summary.narrative.map((paragraph) => (
                  <div className="summary-paragraph" key={paragraph.text}>
                    <p>{paragraph.text}</p>
                    <CitationChips ids={paragraph.citation_ids} citations={summary.citations} />
                  </div>
                ))}
              </section>

              {summary.glossary.length > 0 && (
                <section className="summary-glossary">
                  <h4>Istilah</h4>
                  <dl>
                    {summary.glossary.map((item) => (
                      <div key={item.term}>
                        <dt>{item.term}</dt>
                        <dd>{item.meaning}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}

              {audience === 'analyst' ? (
                <section className="summary-analyst">
                  <h4>Lampiran analis</h4>
                  {summary.analyst.notes.length > 0 && (
                    <ul className="summary-notes">
                      {summary.analyst.notes.map((note) => (
                        <li key={note.text}>
                          <p>{note.text}</p>
                          <CitationChips ids={note.citation_ids} citations={summary.citations} />
                        </li>
                      ))}
                    </ul>
                  )}
                  {summary.analyst.next_steps.length > 0 && (
                    <>
                      <h5>Pemeriksaan berikutnya</h5>
                      <ul>
                        {summary.analyst.next_steps.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {summary.analyst.method.length > 0 && (
                    <>
                      <h5>Metode</h5>
                      <ul>
                        {summary.analyst.method.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </section>
              ) : (
                <p className="summary-mode-note">
                  Lampiran analis, daftar bukti lengkap, dan data tanpa penyamaran tersedia di mode Analis. Graph dan
                  panel clue tetap menampilkan nilai entity asli untuk keperluan audit.
                </p>
              )}

              <p className="summary-source mono">
                {summary.generated_by === 'local'
                  ? 'Disusun lokal dari bukti kasus'
                  : `Disusun ${summary.generated_by}${summary.model ? ` (${summary.model})` : ''}`}
                {summary.cached ? ' / cache' : ''} / {formatDateTime(summary.generated_at)}
              </p>
              <p className="summary-source">{summary.notice}</p>
            </div>
          )}
        </div>
      )}

      {tab === 'findings' && (
        <div role="tabpanel" id="panel-findings" aria-labelledby="tab-findings">
          <section className="finding-section">
            <h3>Identitas kandidat</h3>
            {findings.identities.length === 0 ? (
              <div className="empty-block">
                <strong>Belum ada kandidat</strong>
                Tambahkan entity atau jalankan pivot. Panel ini hanya menampilkan kandidat yang punya bukti.
              </div>
            ) : (
              findings.identities.map((identity) => (
                <button
                  type="button"
                  className="identity-card"
                  key={identity.entity_id}
                  onClick={() => onFocusEntity(identity.entity_id)}
                  title="Fokuskan entity ini di graph"
                >
                  <span className="identity-top">
                    <span className="identity-name">{identity.name}</span>
                    <span className="identity-score">
                      {identity.score}/100 {identity.band}
                    </span>
                  </span>
                  <span className="identity-meta">
                    <span>{identity.connections} relasi</span>
                    <span>{identity.evidence_count} bukti langsung</span>
                  </span>
                  {identity.aliases.length > 0 && (
                    <span className="alias-row">
                      {identity.aliases.slice(0, 6).map((alias) => (
                        <span className="alias" key={`${alias.type}:${alias.id}`}>
                          {alias.type}: {alias.value}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              ))
            )}
          </section>

          <section className="finding-section">
            <h3>Pivot berikutnya</h3>
            {findings.next_pivots.length === 0 ? (
              <p className="muted">Semua tool yang relevan sudah dijalankan untuk entity saat ini.</p>
            ) : (
              <div className="pivot-grid">
                {findings.next_pivots.slice(0, 8).map((pivot) => (
                  <button
                    type="button"
                    className="pivot-btn"
                    key={`${pivot.entity_id}:${pivot.tool_id}`}
                    disabled={running}
                    onClick={() => onPivot(pivot.entity_id, pivot.tool_id)}
                  >
                    <PivotIcon size={15} />
                    <span>
                      <strong>{pivot.label}</strong>
                      <small>
                        {pivot.entity_type}: {pivot.entity_value}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>

          {findings.warnings.length > 0 && (
            <section className="finding-section">
              <h3>Peringatan</h3>
              <div className="warning-box">
                <ul>
                  {findings.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </div>
      )}

      {tab === 'clues' && (
        <div role="tabpanel" id="panel-clues" aria-labelledby="tab-clues">
          <section className="finding-section">
            {findings.clues.length === 0 ? (
              <div className="empty-block">
                <strong>Belum ada clue</strong>
                Clue muncul setelah tool menyimpan bukti dengan bobot.
              </div>
            ) : (
              findings.clues.map((clue) => (
                <article className="clue" key={clue.id}>
                  <div className="clue-top">
                    <span className="clue-category">{clue.category}</span>
                    <span className="clue-weight">bobot {clue.weight.toFixed(1)}</span>
                  </div>
                  <p>{clue.snippet}</p>
                  {clue.source_url && (
                    <a href={clue.source_url} target="_blank" rel="noreferrer noopener">
                      Buka sumber
                      <ExternalIcon size={11} />
                    </a>
                  )}
                </article>
              ))
            )}
          </section>
        </div>
      )}

      {tab === 'timeline' && (
        <div role="tabpanel" id="panel-timeline" aria-labelledby="tab-timeline">
          <section className="finding-section">
            {findings.timeline.length === 0 ? (
              <div className="empty-block">
                <strong>Linimasa kosong</strong>
                Setiap bukti baru akan dicatat dengan waktu penyimpanan.
              </div>
            ) : (
              <ul className="timeline">
                {findings.timeline.map((item) => (
                  <li key={item.id}>
                    <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
                    <p>{item.title}</p>
                    <span className="clue-category">{item.category}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      <section className="finding-section">
        <div className="warning-box">
          <p className="mono" style={{ margin: 0, display: 'flex', gap: 7, alignItems: 'center' }}>
            <AlertIcon size={14} />
            Skor adalah alat bantu, bukan bukti identitas final.
          </p>
        </div>
      </section>
    </aside>
  );
}

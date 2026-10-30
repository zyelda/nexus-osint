import { useEffect, useState } from 'react';
import { api } from '../api';
import type { KeyHealth } from '../types';
import { CloseIcon, KeyIcon } from './Icons';

interface TokenDialogProps {
  open: boolean;
  current: string;
  onClose: () => void;
  onSave: (token: string) => void;
}

export function TokenDialog({ open, current, onClose, onSave }: TokenDialogProps) {
  const [value, setValue] = useState(current);
  const [health, setHealth] = useState<KeyHealth | null>(null);
  const [healthState, setHealthState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');

  useEffect(() => {
    if (open) {
      setValue(current);
    }
  }, [open, current]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setHealthState('loading');
    api
      .keyHealth()
      .then((result) => {
        setHealth(result);
        setHealthState('ready');
      })
      .catch(() => {
        setHealthState('error');
      });
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="token-title">
        <div className="dialog-head">
          <div>
            <span className="file-tab">Akses</span>
            <h2 id="token-title">Token API</h2>
          </div>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Tutup dialog token" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <p>
          Jika server diset dengan BERKAS_API_TOKEN, isi token yang sama di sini. Token disimpan di localStorage dan
          dikirim sebagai header X-Berkas-Token.
        </p>
        <div className="key-health" aria-live="polite">
          <span className="file-tab">Status kunci</span>
          {healthState === 'loading' && <p className="muted">Membaca status kunci...</p>}
          {healthState === 'error' && <p className="muted">Status kunci tidak bisa dibaca.</p>}
          {healthState === 'ready' && health && (
            <>
              <p className="key-health-ai">
                Provider ringkasan: <strong>{health.ai.ready ? health.ai.provider : 'lokal'}</strong>
                {health.ai.model ? ` (${health.ai.model})` : ''}
              </p>
              <ul className="key-health-list">
                {health.keys.map((item) => (
                  <li key={item.name}>
                    <span className={`key-dot ${item.configured ? 'on' : 'off'}`} aria-hidden="true" />
                    <span className="mono">{item.name}</span>
                    <span className="key-health-purpose">{item.purpose}</span>
                    <span className={item.configured ? 'key-state on' : 'key-state'}>
                      {item.configured ? 'aktif' : 'belum diset'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="key-health-meta">
                Cache tool {Math.round(health.tool_cache_ttl / 60)} menit / cache ringkasan{' '}
                {Math.round(health.summary_cache_ttl / 60)} menit / maksimal {health.max_runs_per_batch} tool per batch.
              </p>
            </>
          )}
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSave(value.trim());
          }}
        >
          <label className="field">
            <span>Token akses</span>
            <input
              type="password"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="Tempel token"
              autoFocus
              autoComplete="off"
            />
          </label>
          <div className="dialog-actions">
            {current && (
              <button type="button" className="btn" onClick={() => onSave('')}>
                Hapus token
              </button>
            )}
            <button type="button" className="btn" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn btn-primary">
              <KeyIcon size={15} />
              Simpan token
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

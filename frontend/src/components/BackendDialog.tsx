import { useEffect, useRef, useState } from 'react';
import { getApiOrigin, isStaticHost, normalizeApiOrigin } from '../api';
import { CloseIcon, PlugIcon } from './Icons';

interface BackendDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (origin: string) => void;
}

export function BackendDialog({ open, onClose, onSave }: BackendDialogProps) {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setValue(getApiOrigin());
    setError('');
    const timer = window.setTimeout(() => inputRef.current?.focus(), 40);
    return () => window.clearTimeout(timer);
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

  const submit = () => {
    try {
      onSave(normalizeApiOrigin(value));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Alamat backend tidak valid.');
    }
  };

  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="backend-title">
        <div className="dialog-head">
          <div>
            <span className="file-tab">Koneksi</span>
            <h2 id="backend-title">Alamat backend</h2>
          </div>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Tutup dialog backend" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <p>
          Frontend statis ini perlu alamat backend Flask yang publik. Masukkan origin saja, misalnya
          <code> https://api.contoh.com</code>. Nilainya disimpan di browser ini, bukan di server.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label className="field">
            <span>URL backend</span>
            <input
              ref={inputRef}
              type="text"
              value={value}
              placeholder="https://api.contoh.com"
              autoComplete="url"
              spellCheck={false}
              onChange={(event) => {
                setValue(event.target.value);
                setError('');
              }}
            />
          </label>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <p className="dialog-hint">
            {isStaticHost
              ? 'Kosongkan kolom untuk memakai nilai VITE_API_BASE dari build.'
              : 'Kosongkan kolom untuk memakai origin yang sama dengan halaman ini.'}
          </p>
          <div className="dialog-actions">
            {getApiOrigin() && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setValue('');
                  onSave('');
                }}
              >
                Hapus alamat
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn">
              <PlugIcon size={16} />
              Simpan dan sambungkan
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

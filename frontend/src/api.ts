import type {
  CaseDetail,
  CaseSummary,
  CreateCaseResponse,
  Findings,
  GraphPayload,
  KeyHealth,
  ParseResponse,
  StartRunsResponse,
  SummaryResponse,
  ToolSpec,
  ToolRun,
} from './types';

const API_ORIGIN = (import.meta.env.VITE_API_BASE ?? '').trim().replace(/\/+$/, '');
const BASE = `${API_ORIGIN}/api/v1`;
const TOKEN_KEY = 'berkas.token';
const STATIC_HOST = /\.(vercel\.app|vercel\.sh)$/i.test(window.location.hostname);

export const backendConfigured = Boolean(API_ORIGIN) || !STATIC_HOST;

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
}

export function setToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // storage can be unavailable in private mode; the app still works for open instances
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!backendConfigured) {
    throw new ApiError(
      0,
      'backend_not_configured',
      'Backend belum diset untuk deployment ini. Buka Dokumentasi untuk cara menghubungkan API.',
    );
  }
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const token = getToken();
  if (token) {
    headers.set('X-Berkas-Token', token);
  }
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'network_error', 'Tidak bisa menghubungi server Berkas.');
  }
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const record = (payload ?? {}) as { error?: string; message?: string };
    throw new ApiError(
      response.status,
      record.error ?? 'request_failed',
      record.message ?? `Permintaan gagal dengan status ${response.status}.`,
    );
  }
  return payload as T;
}

export const api = {
  health: () => request<{ status: string; tools: number; auth_required: boolean }>('/health'),

  keyHealth: () => request<KeyHealth>('/keys/health'),

  tools: () => request<{ tools: ToolSpec[] }>('/tools').then((data) => data.tools),

  parse: (text: string) => request<ParseResponse>('/intake/parse', { method: 'POST', body: JSON.stringify({ text }) }),

  listCases: () => request<{ cases: CaseSummary[] }>('/cases').then((data) => data.cases),

  createCase: (payload: {
    text: string;
    entities: Array<Record<string, unknown>>;
    title: string;
    purpose: string;
    authorization_note: string;
    autorun: boolean;
  }) =>
    request<CreateCaseResponse>('/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getCase: (caseId: string) => request<{ case: CaseDetail }>(`/cases/${caseId}`).then((data) => data.case),

  deleteCase: (caseId: string) => request<{ deleted: boolean }>(`/cases/${caseId}`, { method: 'DELETE' }),

  addEntity: (caseId: string, value: string, type?: string) =>
    request<{ entity: unknown }>(`/cases/${caseId}/entities`, {
      method: 'POST',
      body: JSON.stringify({ value, type: type || undefined }),
    }),

  startRuns: (caseId: string, options: { entity_ids?: string[]; tool_ids?: string[]; skip_existing?: boolean } = {}) =>
    request<StartRunsResponse>(`/cases/${caseId}/runs`, {
      method: 'POST',
      body: JSON.stringify(options),
    }),

  pivot: (caseId: string, entityId: string, toolId: string) =>
    request<{ jobs: unknown[]; runs: ToolRun[] }>(`/cases/${caseId}/pivot`, {
      method: 'POST',
      body: JSON.stringify({ entity_id: entityId, tool_id: toolId }),
    }),

  uploadFiles: async (caseId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append('files', file));
    return request<{ files: Array<Record<string, unknown>>; count: number }>(`/cases/${caseId}/files`, {
      method: 'POST',
      body: form,
    });
  },

  graph: (caseId: string) => request<GraphPayload>(`/cases/${caseId}/graph`),

  findings: (caseId: string) => request<{ findings: Findings }>(`/cases/${caseId}/findings`).then((data) => data.findings),

  summary: (caseId: string, audience: 'public' | 'analyst' = 'public', refresh = false) => {
    const query = new URLSearchParams({ audience });
    if (refresh) {
      query.set('refresh', '1');
    }
    return request<SummaryResponse>(`/cases/${caseId}/summary?${query.toString()}`);
  },

  streamUrl: (caseId: string) => {
    const token = getToken();
    const suffix = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${BASE}/cases/${caseId}/events${suffix}`;
  },

  exportUrl: (caseId: string, format: string) => {
    const token = getToken();
    const suffix = token ? `&token=${encodeURIComponent(token)}` : '';
    return `${BASE}/cases/${caseId}/export?format=${encodeURIComponent(format)}${suffix}`;
  },
};

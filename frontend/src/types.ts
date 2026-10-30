export interface ParsedEntity {
  type: string;
  value: string;
  normalized: string;
  confidence: number;
  source?: string;
  attributes?: Record<string, unknown>;
  start?: number;
  end?: number;
}

export interface Entity extends ParsedEntity {
  id: string;
  case_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Edge {
  id: string;
  case_id: string;
  source_id: string;
  target_id: string;
  relation: string;
  confidence: number;
  attributes: Record<string, unknown>;
  created_at: string;
}

export interface Evidence {
  id: string;
  case_id: string;
  entity_id: string | null;
  edge_id: string | null;
  tool_run_id: string | null;
  source_url: string;
  snippet: string;
  category: string;
  weight: number;
  raw: Record<string, unknown>;
  created_at: string;
}

export interface ToolRun {
  id: string;
  case_id: string;
  tool_id: string;
  input_entity_id: string | null;
  status: string;
  progress: number;
  error_code: string;
  error_message: string;
  result: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
}

export interface CaseMeta {
  id: string;
  title: string;
  purpose: string;
  authorization_note: string;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail extends CaseMeta {
  entities: Entity[];
  edges: Edge[];
  evidence: Evidence[];
  runs: ToolRun[];
}

export interface CaseSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  entity_count: number;
}

export interface FindingIdentity {
  entity_id: string;
  name: string;
  score: number;
  band: string;
  aliases: Array<{ type: string; value: string; id: string }>;
  connections: number;
  evidence_count: number;
}

export interface Clue {
  id: string;
  category: string;
  snippet: string;
  source_url: string;
  weight: number;
  entity_id: string | null;
  edge_id: string | null;
  created_at: string;
}

export interface NextPivot {
  entity_id: string;
  entity_type: string;
  entity_value: string;
  tool_id: string;
  label: string;
  reason: string;
}

export interface TimelineItem {
  id: string;
  category: string;
  title: string;
  source_url: string;
  created_at: string;
  entity_id: string | null;
}

export interface Findings {
  case_id: string;
  case_title: string;
  confidence: {
    score: number;
    band: string;
    evidence_count: number;
    source_count: number;
    conflicts: number;
    why: string[];
  };
  clues: Clue[];
  identities: FindingIdentity[];
  timeline: TimelineItem[];
  warnings: string[];
  next_pivots: NextPivot[];
  counts: { entities: number; edges: number; evidence: number; runs: number };
}

export interface GraphNodeData {
  id: string;
  label: string;
  type: string;
  confidence: number;
  status: string;
  normalized: string;
  attributes: Record<string, unknown>;
}

export interface GraphPayload {
  case: CaseMeta;
  nodes: Array<{ data: GraphNodeData }>;
  edges: Array<{ data: { id: string; source: string; target: string; relation: string; confidence: number } }>;
  findings: Findings;
  runs: ToolRun[];
}

export interface ToolSpec {
  id: string;
  label: string;
  description: string;
  inputs: string[];
  outputs: string[];
  category: string;
  requires_key: string;
  configured: boolean;
  legal_note: string;
}

export interface CreateCaseResponse {
  case: CaseDetail;
  jobs: Array<Record<string, unknown>>;
  runs: ToolRun[];
  deferred: number;
}

export interface StartRunsResponse {
  jobs: Array<Record<string, unknown>>;
  runs: ToolRun[];
  count: number;
  deferred: number;
  limit: number;
}

export interface ParseResponse {
  entities: ParsedEntity[];
  plan: Array<{ type: string; value: string; tools: Array<{ id: string; label: string }> }>;
  count: number;
}

export interface SummaryItem {
  text: string;
  citation_ids: string[];
}

export interface SummaryCitation {
  id: string;
  category: string;
  label: string;
  source_url: string;
}

export interface SummaryResponse {
  case_id: string;
  case_title: string;
  audience: 'public' | 'analyst';
  generated_by: string;
  model: string;
  generated_at: string;
  fingerprint: string;
  headline: string;
  confidence: { score: number; band: string; plain: string };
  points: SummaryItem[];
  limits: string[];
  narrative: SummaryItem[];
  glossary: Array<{ term: string; meaning: string }>;
  analyst: {
    notes: SummaryItem[];
    next_steps: string[];
    method: string[];
  };
  citations: SummaryCitation[];
  redaction: { applied: boolean; policy: 'partial' | 'none'; fields: string[] };
  notice: string;
  cached: boolean;
}

export interface KeyHealth {
  keys: Array<{ name: string; configured: boolean; purpose: string }>;
  ai: { provider: string; model: string; ready: boolean };
  public_redaction: boolean;
  tool_cache_ttl: number;
  summary_cache_ttl: number;
  max_runs_per_batch: number;
}

export interface StreamEvent {
  type: string;
  at?: string;
  findings?: Findings;
  tool_id?: string;
  run_id?: string;
  entity_id?: string;
  status?: string;
  error_message?: string;
  warnings?: string[];
  delta?: { entities: number; edges: number; evidence: number };
  count?: number;
  case_id?: string;
}

export type FileType = 'pdf' | 'docx';
export type Severity = 'high' | 'medium' | 'low' | '楂?' | '涓?' | '浣?' | string;
export type PerspectiveType = 'party_a' | 'party_b';
export type ExportFormat = 'docx' | 'markdown';
export type AnalysisLanguage = 'auto' | 'zh' | 'en';

export interface Document {
  id: string;
  filename: string;
  file_type: FileType;
  file_size: number;
  page_count: number;
  text_content?: string;
  uploaded_at: string;
  session_id: string;
  analyses?: Record<
    string,
    {
      risks: RiskCard[];
      summary: string;
      analyzed_at: string;
      duration_ms: number;
      trace_steps?: AgentTraceStep[];
      decision_records?: Record<string, unknown>[];
      evidence_summary?: {
        grounded_count: number;
        total_risks: number;
        grounding_ratio: number;
      };
    }
  >;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  file_type: FileType;
  file_size: number;
  page_count: number;
  uploaded_at: string;
  session_id: string;
}

export interface EvidenceRef {
  chunk_id: string;
  quote: string;
  score: number;
}

export interface RiskCard {
  id: string;
  clause_title: string;
  risk_category: string;
  original_text: string;
  risk_description: string;
  suggested_revision: string;
  severity: Severity;
  document_id: string;
  citations?: EvidenceRef[];
  grounding_score?: number | null;
}

export interface AnalysisRequest {
  document_id: string;
  perspective: PerspectiveType;
  options?: {
    analysis_language?: AnalysisLanguage;
    [key: string]: unknown;
  };
}

export interface AgentTraceStep {
  phase: string;
  action: string;
  reason: string;
  inputs_summary?: Record<string, unknown>;
  outputs_summary?: Record<string, unknown>;
  verdict?: string;
  policy_hint?: string;
  ts?: string;
}

export interface DoneEvent {
  summary: string;
  total_risks: number;
  duration_ms: number;
  risks?: RiskCard[];
  trace_steps?: AgentTraceStep[];
  decision_records?: Record<string, unknown>[];
  evidence_summary?: {
    grounded_count: number;
    total_risks: number;
    grounding_ratio: number;
  };
}

export interface AnalysisResult {
  document_id: string;
  perspective: PerspectiveType;
  risks: RiskCard[];
  summary: string;
  analyzed_at: string;
  duration_ms: number;
}

export interface PerspectiveInfo {
  id: PerspectiveType;
  name: string;
  description: string;
  focus_areas: string[];
}

export interface StatusEvent {
  message: string;
  progress: number;
}

export interface RefineRequest {
  instruction: string;
  original_risk_id: string;
}

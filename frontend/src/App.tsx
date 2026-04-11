import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api } from './services/api';
import type {
  AnalysisLanguage,
  AgentTraceStep,
  Document,
  DocumentMetadata,
  DoneEvent,
  PerspectiveInfo,
  PerspectiveType,
  RiskCard,
} from './types';
import AgentTracePanel from './components/AgentTracePanel';
import DocumentUpload from './components/DocumentUpload';
import ExportButton from './components/ExportButton';
import PerspectiveSwitch from './components/PerspectiveSwitch';
import RiskCardList from './components/RiskCardList';
import RiskDetailModal from './components/RiskDetailModal';

const SESSION_KEY = 'contract-review-session-id';

function getOrCreateSessionId(): string {
  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created = `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  window.localStorage.setItem(SESSION_KEY, created);
  return created;
}

function App() {
  const [document, setDocument] = useState<Document | null>(null);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [risks, setRisks] = useState<RiskCard[]>([]);
  const [partyARisks, setPartyARisks] = useState<RiskCard[]>([]);
  const [partyBRisks, setPartyBRisks] = useState<RiskCard[]>([]);
  const [perspectives, setPerspectives] = useState<PerspectiveInfo[]>([]);
  const [currentPerspective, setCurrentPerspective] = useState<PerspectiveType>('party_a');
  const [analysisLanguage, setAnalysisLanguage] = useState<AnalysisLanguage>('auto');
  const [comparisonMode, setComparisonMode] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState<{ message: string; percent: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedRisk, setSelectedRisk] = useState<RiskCard | null>(null);
  const [traceSteps, setTraceSteps] = useState<AgentTraceStep[]>([]);
  const [evidenceSummary, setEvidenceSummary] = useState<{ grounded_count: number; total_risks: number; grounding_ratio: number } | null>(null);

  const sessionIdRef = useRef('');
  const currentPerspectiveRef = useRef(currentPerspective);
  currentPerspectiveRef.current = currentPerspective;

  useEffect(() => {
    sessionIdRef.current = getOrCreateSessionId();
    void Promise.all([loadPerspectives(), loadDocuments()]);
  }, []);

  async function loadPerspectives() {
    try {
      const data = await api.getPerspectives();
      setPerspectives(data.perspectives);
    } catch {
      setError('加载视角失败');
    }
  }

  async function loadDocuments() {
    try {
      const data = await api.listDocuments();
      setDocuments(data.documents);
    } catch {
      setDocuments([]);
    }
  }

  async function hydrateDocument(documentId: string) {
    try {
      const data = await api.getDocument(documentId);
      setDocument(data.document);
      const partyA = data.document.analyses?.party_a?.risks ?? [];
      const partyB = data.document.analyses?.party_b?.risks ?? [];
      setPartyARisks(partyA);
      setPartyBRisks(partyB);
      setRisks(currentPerspectiveRef.current === 'party_a' ? partyA : partyB);
      setTraceSteps(data.document.analyses?.[currentPerspectiveRef.current]?.trace_steps ?? []);
      setEvidenceSummary(data.document.analyses?.[currentPerspectiveRef.current]?.evidence_summary ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载文档失败');
    }
  }

  const handleSSEEvent = (eventType: string, data: unknown) => {
    if (eventType === 'status' || eventType === 'progress') {
      const d = data as { message: string; progress: number };
      setProgress({ message: d.message, percent: d.progress });
      return;
    }

    if (eventType === 'agent_trace') {
      const d = data as { step?: AgentTraceStep };
      if (d.step) {
        const nextStep = d.step;
        setTraceSteps((prev) => [...prev, nextStep]);
      }
      return;
    }

    if (eventType === 'done') {
      const d = data as DoneEvent;
      setProgress(null);
      setIsAnalyzing(false);
      setTraceSteps(d.trace_steps ?? []);
      setEvidenceSummary(d.evidence_summary ?? null);
      return;
    }

    if (eventType === 'risk') {
      const riskCard = data as RiskCard;
      setRisks((prev) => [...prev, riskCard]);
      if (currentPerspectiveRef.current === 'party_a') {
        setPartyARisks((prev) => [...prev, riskCard]);
      } else {
        setPartyBRisks((prev) => [...prev, riskCard]);
      }
    }
  };

  async function handleUpload(file: File, sessionId: string) {
    setError(null);
    sessionIdRef.current = sessionId;
    window.localStorage.setItem(SESSION_KEY, sessionId);
    try {
      const data = await api.uploadDocument(file, sessionId);
      setDocument(data.document);
      setRisks([]);
      setPartyARisks([]);
      setPartyBRisks([]);
      setTraceSteps([]);
      setEvidenceSummary(null);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败');
    }
  }

  async function handleAnalyze() {
    if (!document) return;

    setError(null);
    setIsAnalyzing(true);
    setProgress({ message: '准备开始分析...', percent: 2 });
    setTraceSteps([]);
    setEvidenceSummary(null);
    setRisks([]);
    if (currentPerspective === 'party_a') {
      setPartyARisks([]);
    } else {
      setPartyBRisks([]);
    }

    try {
      await api.analyzeStream(
        {
          document_id: document.id,
          perspective: currentPerspective,
          options: { analysis_language: analysisLanguage },
        },
        handleSSEEvent
      );
      await hydrateDocument(document.id);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析失败');
      setIsAnalyzing(false);
      setProgress(null);
    }
  }

  function handlePerspectiveChange(perspective: PerspectiveType) {
    setCurrentPerspective(perspective);
    setRisks(perspective === 'party_a' ? partyARisks : partyBRisks);
    if (document?.analyses?.[perspective]) {
      setTraceSteps(document.analyses[perspective].trace_steps ?? []);
      setEvidenceSummary(document.analyses[perspective].evidence_summary ?? null);
    } else {
      setTraceSteps([]);
      setEvidenceSummary(null);
    }
  }

  async function handleDeleteCurrentDocument() {
    if (!document) return;
    await api.deleteDocument(document.id);
    setDocument(null);
    setRisks([]);
    setPartyARisks([]);
    setPartyBRisks([]);
    setTraceSteps([]);
    setEvidenceSummary(null);
    await loadDocuments();
  }

  function handleUpdateRisk(riskId: string, newSuggestion: string) {
    const update = (list: RiskCard[]) =>
      list.map((risk) => (risk.id === riskId ? { ...risk, suggested_revision: newSuggestion } : risk));
    setRisks((prev) => update(prev));
    setPartyARisks((prev) => update(prev));
    setPartyBRisks((prev) => update(prev));
    setSelectedRisk((prev) => (prev && prev.id === riskId ? { ...prev, suggested_revision: newSuggestion } : prev));
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-800">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <h1 className="text-2xl font-bold text-slate-100">合同智能审查</h1>
          <p className="mt-1 text-sm text-slate-400">Hybrid RAG + Agent runtime + grounded evidence</p>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-4 py-8 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="rounded-lg border border-red-500 bg-red-500/20 p-4 text-red-200"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <section className="rounded-lg border border-slate-700 bg-slate-800 p-6">
            <h2 className="mb-4 text-lg font-semibold">上传合同</h2>
            <DocumentUpload onUpload={handleUpload} disabled={isAnalyzing} />
          </section>

          <section className="rounded-lg border border-slate-700 bg-slate-800 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">审查视角</h2>
              {partyARisks.length > 0 && partyBRisks.length > 0 && (
                <button
                  onClick={() => setComparisonMode((value) => !value)}
                  className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-600"
                >
                  {comparisonMode ? '退出对比' : '视角对比'}
                </button>
              )}
            </div>
            <PerspectiveSwitch
              perspectives={perspectives}
              currentPerspective={currentPerspective}
              onChange={handlePerspectiveChange}
            />
          </section>

          <section className="rounded-lg border border-slate-700 bg-slate-800 p-6">
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-slate-100">Language Branch</h2>
              <p className="mt-1 text-sm text-slate-400">
                Choose the retrieval strategy branch for this analysis run.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: 'auto', label: 'Auto' },
                { value: 'zh', label: 'Chinese' },
                { value: 'en', label: 'English' },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setAnalysisLanguage(option.value as AnalysisLanguage)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    analysisLanguage === option.value
                      ? 'border-blue-500 bg-blue-500/15 text-blue-200'
                      : 'border-slate-700 bg-slate-900/50 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-700 bg-slate-800 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">最近文档</h3>
              <span className="text-xs text-slate-500">{documents.length}</span>
            </div>
            <div className="space-y-2">
              {documents.slice(0, 6).map((item) => (
                <button
                  key={item.id}
                  onClick={() => void hydrateDocument(item.id)}
                  className={`w-full rounded border p-3 text-left transition-colors ${
                    document?.id === item.id ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                  }`}
                >
                  <div className="truncate text-sm font-medium text-slate-200">{item.filename}</div>
                  <div className="mt-1 text-xs text-slate-500">{new Date(item.uploaded_at).toLocaleString()}</div>
                </button>
              ))}
              {documents.length === 0 && <p className="text-sm text-slate-400">还没有已保存文档。</p>}
            </div>
          </section>

          <section className="space-y-3">
            <button
              onClick={() => void handleAnalyze()}
              disabled={!document || isAnalyzing}
              className={`w-full rounded-lg px-4 py-3 font-semibold transition-colors ${
                !document || isAnalyzing ? 'cursor-not-allowed bg-slate-600 text-slate-400' : 'bg-blue-600 text-white hover:bg-blue-500'
              }`}
            >
              {isAnalyzing ? '分析中...' : '开始分析'}
            </button>

            {document && (
              <button
                onClick={() => void handleDeleteCurrentDocument()}
                className="w-full rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800"
              >
                删除当前文档
              </button>
            )}
          </section>

          {document && risks.length > 0 && (
            <ExportButton documentId={document.id} risks={risks} perspective={currentPerspective} />
          )}

          <AgentTracePanel steps={traceSteps} />
        </div>

        <div className="space-y-6 lg:col-span-2">
          {progress && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-lg border border-slate-700 bg-slate-800 p-4">
              <div className="flex items-center gap-3">
                <div className="spinner text-blue-500" />
                <span className="text-slate-300">{progress.message}</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-700">
                <motion.div initial={{ width: 0 }} animate={{ width: `${progress.percent}%` }} className="h-full bg-blue-500" />
              </div>
            </motion.div>
          )}

          {evidenceSummary && (
            <section className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
              <h3 className="text-sm font-semibold text-emerald-200">Evidence Summary</h3>
              <p className="mt-1 text-sm text-emerald-100/90">
                {evidenceSummary.grounded_count}/{evidenceSummary.total_risks} 条风险已绑定证据，grounding ratio =
                {' '}{evidenceSummary.grounding_ratio.toFixed(2)}
              </p>
            </section>
          )}

          <RiskCardList
            risks={risks}
            comparisonMode={comparisonMode}
            partyARisks={partyARisks}
            partyBRisks={partyBRisks}
            currentPerspective={currentPerspective}
            onPerspectiveChange={handlePerspectiveChange}
            onRiskClick={setSelectedRisk}
          />
        </div>
      </main>

      <RiskDetailModal risk={selectedRisk} onClose={() => setSelectedRisk(null)} onUpdateRisk={handleUpdateRisk} />
    </div>
  );
}

export default App;

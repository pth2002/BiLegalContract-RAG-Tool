import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { RiskCard } from '../types';
import { normalizeSeverity, severityLabel, type SeverityTone } from '../utils/severity';
import RefinementInput from './RefinementInput';
import SuggestionDiff from './SuggestionDiff'; 

interface RiskDetailModalProps {
  risk: RiskCard | null;
  onClose: () => void;
  onUpdateRisk?: (riskId: string, newSuggestion: string) => void;
}

const severityConfig: Record<SeverityTone, { color: string; bgColor: string; borderColor: string }> = {
  high: { color: 'text-red-400', bgColor: 'bg-red-500/10', borderColor: 'border-red-500/30' },
  medium: { color: 'text-yellow-400', bgColor: 'bg-yellow-500/10', borderColor: 'border-yellow-500/30' },
  low: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500/30' },
};

type ModalState = 'view' | 'refine' | 'result';

export default function RiskDetailModal({ risk, onClose, onUpdateRisk }: RiskDetailModalProps) {
  const [copied, setCopied] = useState<string | null>(null);
  const [modalState, setModalState] = useState<ModalState>('view');
  const [refinedSuggestion, setRefinedSuggestion] = useState<string | null>(null);

  useEffect(() => {
    setModalState('view');
    setRefinedSuggestion(null);
  }, [risk?.id]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (modalState === 'view') {
        onClose();
      } else {
        setModalState('view');
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [modalState, onClose]);

  if (!risk) return null;

  const config = severityConfig[normalizeSeverity(risk.severity)];

  const handleCopy = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleRefined = (_original: string, refined: string) => {
    setRefinedSuggestion(refined);
    setModalState('result');
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-700 bg-slate-800 shadow-2xl"
        >
          <div className={`sticky top-0 border-b border-slate-700 p-6 ${config.bgColor}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">⚠</span>
                <div>
                  <h2 className="text-xl font-semibold text-slate-100">{risk.clause_title}</h2>
                  <div className="mt-1 flex items-center gap-2">
                    <span className={`rounded bg-slate-800/50 px-2 py-0.5 text-xs ${config.color}`}>{severityLabel(risk.severity)}</span>
                    <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">{risk.risk_category}</span>
                    <span className="text-xs text-slate-500">{risk.id}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => {
                  setModalState('view');
                  setRefinedSuggestion(null);
                  onClose();
                }}
                className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-white"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div className="space-y-6 p-6">
            <AnimatePresence mode="wait">
              {modalState === 'view' && (
                <motion.div key="view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-medium text-slate-400">原文条款</h3>
                      <button onClick={() => handleCopy(risk.original_text, 'original')} className="text-xs text-blue-400 transition-colors hover:text-blue-300">
                        {copied === 'original' ? '已复制' : '复制'}
                      </button>
                    </div>
                    <blockquote className="rounded-lg border-l-4 border-slate-600 bg-slate-900/50 p-4">
                      <p className="whitespace-pre-wrap text-slate-300">{risk.original_text}</p>
                    </blockquote>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium text-slate-400">风险分析</h3>
                    <div className="rounded-lg bg-slate-900/50 p-4">
                      <p className="whitespace-pre-wrap text-slate-300">{risk.risk_description}</p>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-medium text-slate-400">修改建议</h3>
                      <button onClick={() => handleCopy(risk.suggested_revision, 'suggestion')} className="text-xs text-blue-400 transition-colors hover:text-blue-300">
                        {copied === 'suggestion' ? '已复制' : '复制建议'}
                      </button>
                    </div>
                    <div className={`rounded-lg border p-4 ${config.bgColor} ${config.borderColor}`}>
                      <p className="whitespace-pre-wrap text-green-300">{risk.suggested_revision}</p>
                    </div>
                  </div>

                  {risk.citations && risk.citations.length > 0 && (
                    <div>
                      <h3 className="mb-2 text-sm font-medium text-slate-400">证据引用</h3>
                      <div className="space-y-2">
                        {risk.citations.map((citation) => (
                          <div key={`${risk.id}-${citation.chunk_id}`} className="rounded border border-slate-700 bg-slate-900/60 p-3">
                            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                              <span>{citation.chunk_id}</span>
                              <span>score {citation.score.toFixed(2)}</span>
                            </div>
                            <p className="text-xs text-slate-300">{citation.quote}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-3 border-t border-slate-700 pt-4">
                    <button
                      onClick={() => handleCopy(risk.suggested_revision, 'copy')}
                      className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-500"
                    >
                      复制建议
                    </button>
                    <button
                      onClick={() => handleCopy(risk.original_text, 'copy-original')}
                      className="flex-1 rounded-lg bg-slate-700 px-4 py-2 text-slate-300 transition-colors hover:bg-slate-600"
                    >
                      复制原文
                    </button>
                    <button
                      onClick={() => setModalState('refine')}
                      className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-white transition-colors hover:bg-emerald-500"
                    >
                      优化建议
                    </button>
                  </div>
                </motion.div>
              )}

              {modalState === 'refine' && (
                <motion.div key="refine" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                  <RefinementInput risk={risk} onRefined={handleRefined} onCancel={() => setModalState('view')} />
                </motion.div>
              )}

              {modalState === 'result' && refinedSuggestion && (
                <motion.div key="result" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-slate-400">原文条款</h3>
                    <blockquote className="rounded-lg border-l-4 border-slate-600 bg-slate-900/50 p-4">
                      <p className="whitespace-pre-wrap text-slate-300">{risk.original_text}</p>
                    </blockquote>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium text-slate-400">风险分析</h3>
                    <div className="rounded-lg bg-slate-900/50 p-4">
                      <p className="whitespace-pre-wrap text-slate-300">{risk.risk_description}</p>
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium text-slate-400">修改建议优化</h3>
                    <SuggestionDiff original={risk.suggested_revision} refined={refinedSuggestion} onCopyRefined={() => {}} />
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => {
                        if (onUpdateRisk) onUpdateRisk(risk.id, refinedSuggestion);
                        setModalState('view');
                        setRefinedSuggestion(null);
                      }}
                      className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-white transition-colors hover:bg-emerald-500"
                    >
                      确认使用优化建议
                    </button>
                    <button
                      onClick={() => {
                        setModalState('view');
                        setRefinedSuggestion(null);
                      }}
                      className="flex-1 rounded-lg bg-slate-700 px-4 py-2 text-slate-300 transition-colors hover:bg-slate-600"
                    >
                      返回详情
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

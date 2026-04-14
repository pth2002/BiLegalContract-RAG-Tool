import { useState } from 'react';
import { motion } from 'framer-motion';
import type { RiskCard as RiskCardType } from '../types';
import { normalizeSeverity, severityLabel, type SeverityTone } from '../utils/severity';

interface RiskCardProps {
  risk: RiskCardType;
  index: number;
  compact?: boolean;
  onClick?: (risk: RiskCardType) => void; 
}

const severityConfig: Record<SeverityTone, { color: string; bgColor: string; icon: string }> = {
  high: { color: 'text-red-400', bgColor: 'border-red-500 bg-red-500/10', icon: '!' },
  medium: { color: 'text-yellow-400', bgColor: 'border-yellow-500 bg-yellow-500/10', icon: '~' },
  low: { color: 'text-blue-400', bgColor: 'border-blue-500 bg-blue-500/10', icon: '*' },
};

export default function RiskCard({ risk, index, compact = false, onClick }: RiskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const config = severityConfig[normalizeSeverity(risk.severity)];

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(risk.suggested_revision);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCardClick = () => {
    if (onClick) {
      onClick(risk);
    } else {
      setExpanded((value) => !value);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={handleCardClick}
      className={`mb-3 rounded-lg border p-3 ${config.bgColor} ${compact ? 'text-sm' : ''} ${
        onClick ? 'cursor-pointer transition-colors hover:border-slate-500' : ''
      }`}
    >
      <div className="flex items-start gap-2">
        <span className={compact ? 'text-lg' : 'text-xl'}>{config.icon}</span>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className={`truncate font-semibold ${config.color}`}>{risk.clause_title}</span>
            <span className={`rounded bg-slate-800/50 px-1.5 py-0.5 text-xs ${config.color}`}>
              {severityLabel(risk.severity)}
            </span>
            {!compact && (
              <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-300">{risk.risk_category}</span>
            )}
            {typeof risk.grounding_score === 'number' && (
              <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-xs text-emerald-300">
                evidence {risk.grounding_score.toFixed(2)}
              </span>
            )}
          </div>

          {!expanded && <p className="line-clamp-2 text-xs text-slate-300/80">{risk.risk_description}</p>}
        </div>
      </div>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className={`mt-3 space-y-3 border-t border-slate-700 pt-3 ${compact ? 'text-xs' : ''}`}
        >
          <div>
            <h4 className="mb-1 text-xs font-medium text-slate-400">原文</h4>
            <blockquote className="border-l border-slate-600 pl-2 text-xs text-slate-300">{risk.original_text}</blockquote>
          </div>

          <div>
            <h4 className="mb-1 text-xs font-medium text-slate-400">风险分析</h4>
            <p className="text-xs text-slate-300">{risk.risk_description}</p>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <h4 className="text-xs font-medium text-slate-400">修改建议</h4>
              <button onClick={handleCopy} className="text-xs text-blue-400 transition-colors hover:text-blue-300">
                {copied ? '已复制' : '复制'}
              </button>
            </div>
            <div className="rounded border border-green-500/30 bg-green-500/10 p-2">
              <p className="text-xs text-green-300">{risk.suggested_revision}</p>
            </div>
          </div>

          {risk.citations && risk.citations.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-medium text-slate-400">证据引用</h4>
              <div className="space-y-2">
                {risk.citations.map((citation) => (
                  <div key={`${risk.id}-${citation.chunk_id}`} className="rounded border border-slate-700 bg-slate-900/60 p-2">
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
        </motion.div>
      )}

      <div className="mt-2 flex items-center justify-between">
        <button
          onClick={(event) => {
            event.stopPropagation();
            setExpanded((value) => !value);
          }}
          className="text-xs text-slate-400 transition-colors hover:text-white"
        >
          {expanded ? '收起详情' : '查看详情'}
        </button>

        <span className="text-xs text-slate-500">{risk.id}</span>
      </div>
    </motion.div>
  );
}

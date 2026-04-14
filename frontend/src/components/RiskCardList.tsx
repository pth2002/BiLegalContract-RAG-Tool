import { AnimatePresence } from 'framer-motion';
import type { RiskCard as RiskCardType, PerspectiveType } from '../types';
import { normalizeSeverity } from '../utils/severity';
import PerspectiveCompare from './PerspectiveCompare';
import RiskCard from './RiskCard';

interface RiskCardListProps {
  risks: RiskCardType[];
  comparisonMode?: boolean;
  partyARisks?: RiskCardType[]; 
  partyBRisks?: RiskCardType[];
  currentPerspective?: PerspectiveType;
  onPerspectiveChange?: (p: PerspectiveType) => void;
  onRiskClick?: (risk: RiskCardType) => void;
}

const SEVERITY_ORDER = {
  high: 0,
  medium: 1,
  low: 2,
} as const;

function countBySeverity(risks: RiskCardType[], tone: keyof typeof SEVERITY_ORDER) {
  return risks.filter((risk) => normalizeSeverity(risk.severity) === tone).length;
}

export default function RiskCardList({
  risks,
  comparisonMode = false,
  partyARisks = [],
  partyBRisks = [],
  currentPerspective = 'party_a',
  onPerspectiveChange,
  onRiskClick,
}: RiskCardListProps) {
  const sortedRisks = [...risks].sort(
    (a, b) => SEVERITY_ORDER[normalizeSeverity(a.severity)] - SEVERITY_ORDER[normalizeSeverity(b.severity)],
  );

  const highCount = countBySeverity(risks, 'high');
  const mediumCount = countBySeverity(risks, 'medium');
  const lowCount = countBySeverity(risks, 'low');

  if (comparisonMode && partyARisks.length > 0 && partyBRisks.length > 0) {
    return (
      <PerspectiveCompare
        partyARisks={partyARisks}
        partyBRisks={partyBRisks}
        currentPerspective={currentPerspective}
        onSwitchPerspective={onPerspectiveChange || (() => {})}
        onRiskClick={onRiskClick}
      />
    );
  }

  if (risks.length === 0) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-12 text-center">
        <svg className="mx-auto mb-4 h-16 w-16 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="mb-2 text-lg font-medium text-slate-300">暂无风险结果</h3>
        <p className="text-sm text-slate-500">上传合同并开始分析后，风险点会显示在这里。</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-4">
        <h2 className="text-lg font-semibold text-slate-100">风险分析结果</h2>
        <div className="flex items-center gap-2">
          <span className="rounded border border-red-500/30 bg-red-500/20 px-2 py-1 text-xs text-red-400">高 {highCount}</span>
          <span className="rounded border border-yellow-500/30 bg-yellow-500/20 px-2 py-1 text-xs text-yellow-400">中 {mediumCount}</span>
          <span className="rounded border border-blue-500/30 bg-blue-500/20 px-2 py-1 text-xs text-blue-400">低 {lowCount}</span>
        </div>
      </div>

      <AnimatePresence mode="popLayout">
        {sortedRisks.map((risk, index) => (
          <RiskCard key={risk.id} risk={risk} index={index} onClick={onRiskClick} />
        ))}
      </AnimatePresence>
    </div>
  );
}

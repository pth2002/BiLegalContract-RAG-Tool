import { AnimatePresence } from 'framer-motion';
import type { PerspectiveType, RiskCard as RiskCardType } from '../types';
import { normalizeSeverity } from '../utils/severity';
import RiskCard from './RiskCard'; 

interface PerspectiveCompareProps {
  partyARisks: RiskCardType[];
  partyBRisks: RiskCardType[];
  currentPerspective: PerspectiveType;
  onSwitchPerspective: (p: PerspectiveType) => void;
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

function sortRisks(risks: RiskCardType[]) {
  return [...risks].sort(
    (a, b) => SEVERITY_ORDER[normalizeSeverity(a.severity)] - SEVERITY_ORDER[normalizeSeverity(b.severity)],
  );
}

export default function PerspectiveCompare({
  partyARisks,
  partyBRisks,
  currentPerspective,
  onSwitchPerspective,
  onRiskClick,
}: PerspectiveCompareProps) {
  const highDiff = countBySeverity(partyARisks, 'high') - countBySeverity(partyBRisks, 'high');

  if (partyARisks.length === 0 && partyBRisks.length === 0) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-12 text-center">
        <h3 className="mb-2 text-lg font-medium text-slate-300">暂无对比数据</h3>
        <p className="text-sm text-slate-500">请先在不同视角下完成分析，再查看对比结果。</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">视角对比分析</h2>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-blue-500" />
            <span className="text-slate-400">甲方 {partyARisks.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500" />
            <span className="text-slate-400">乙方 {partyBRisks.length}</span>
          </div>
          {highDiff !== 0 && (
            <span className={`rounded px-2 py-1 text-xs ${highDiff > 0 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
              {highDiff > 0 ? '甲方' : '乙方'}高风险更多 ({Math.abs(highDiff)})
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-700 pb-3">
            <div className="h-3 w-3 rounded-full bg-blue-500" />
            <h3 className="font-medium text-blue-400">甲方视角</h3>
            <span className="text-xs text-slate-500">
              ({countBySeverity(partyARisks, 'high')} 高 / {countBySeverity(partyARisks, 'medium')} 中 / {countBySeverity(partyARisks, 'low')} 低)
            </span>
          </div>
          <AnimatePresence mode="popLayout">
            {sortRisks(partyARisks).map((risk, index) => (
              <RiskCard key={risk.id} risk={risk} index={index} compact onClick={onRiskClick} />
            ))}
          </AnimatePresence>
          {partyARisks.length === 0 && <p className="py-8 text-center text-sm text-slate-500">暂无风险点</p>}
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-700 pb-3">
            <div className="h-3 w-3 rounded-full bg-emerald-500" />
            <h3 className="font-medium text-emerald-400">乙方视角</h3>
            <span className="text-xs text-slate-500">
              ({countBySeverity(partyBRisks, 'high')} 高 / {countBySeverity(partyBRisks, 'medium')} 中 / {countBySeverity(partyBRisks, 'low')} 低)
            </span>
          </div>
          <AnimatePresence mode="popLayout">
            {sortRisks(partyBRisks).map((risk, index) => (
              <RiskCard key={risk.id} risk={risk} index={index} compact onClick={onRiskClick} />
            ))}
          </AnimatePresence>
          {partyBRisks.length === 0 && <p className="py-8 text-center text-sm text-slate-500">暂无风险点</p>}
        </div>
      </div>

      <div className="flex justify-center pt-4">
        <button
          onClick={() => onSwitchPerspective(currentPerspective)}
          className="flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回 {currentPerspective === 'party_a' ? '甲方' : '乙方'} 视角详情
        </button>
      </div>
    </div>
  );
}

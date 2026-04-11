import type { AgentTraceStep } from '../types';

interface AgentTracePanelProps {
  steps: AgentTraceStep[];
}

export default function AgentTracePanel({ steps }: AgentTracePanelProps) {
  if (steps.length === 0) {
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-800 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Agent Trace</h3>
        <p className="text-sm text-slate-400">分析开始后，这里会展示 agent 的决策、检索和验证轨迹。</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Agent Trace</h3>
        <span className="text-xs text-slate-500">{steps.length} steps</span>
      </div>
      <div className="space-y-2">
        {steps.slice(-8).map((step, index) => (
          <div key={`${step.ts ?? index}-${step.action}`} className="rounded border border-slate-700 bg-slate-900/60 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs uppercase tracking-wide text-slate-500">{step.phase}</span>
              <span className="text-xs text-slate-500">{step.policy_hint || step.verdict || 'running'}</span>
            </div>
            <div className="text-sm font-medium text-slate-200">{step.action}</div>
            <p className="mt-1 text-xs text-slate-400">{step.reason}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

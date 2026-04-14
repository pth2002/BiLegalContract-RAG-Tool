import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';
import type { RiskCard } from '../types';

interface RefinementInputProps {
  risk: RiskCard; 
  onRefined: (original: string, refined: string) => void;
  onCancel: () => void;
}

const PRESET_INSTRUCTIONS = [
  { label: '语气更委婉', instruction: '请用更委婉的语气表达' },
  { label: '语气更正式', instruction: '请用更正式的法律语言表达' },
  { label: '增加保护', instruction: '请增加对我方更有利的保护条款' },
  { label: '简化表述', instruction: '请简化表述，使条款更清晰易懂' },
  { label: '自定义', instruction: '' },
];

export default function RefinementInput({ risk, onRefined, onCancel }: RefinementInputProps) {
  const [instruction, setInstruction] = useState('');
  const [isRefining, setIsRefining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useCustom, setUseCustom] = useState(false);

  const handleRefine = async () => {
    if (!instruction.trim()) {
      setError('请输入修改指示');
      return;
    }

    setIsRefining(true);
    setError(null);

    try {
      const result = await api.refineSuggestion(risk.id, {
        instruction,
        original_risk_id: risk.id,
      });

      // @ts-expect-error - backend returns snake_case
onRefined(result.original.suggested_revision, result.refined.suggested_revision);
    } catch (err) {
      setError(err instanceof Error ? err.message : '优化失败，请重试');
    } finally {
      setIsRefining(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="bg-slate-800 rounded-lg border border-slate-700 p-4"
    >
      <h3 className="text-sm font-medium text-slate-300 mb-3">
        优化修改建议
      </h3>

      {/* Original suggestion */}
      <div className="mb-3 p-3 bg-slate-900/50 rounded border border-slate-700">
        <p className="text-xs text-slate-500 mb-1">原始建议</p>
        <p className="text-sm text-green-300">{risk.suggested_revision}</p>
      </div>

      {/* Preset instructions */}
      {!useCustom && (
        <div className="mb-3">
          <p className="text-xs text-slate-500 mb-2">快速选择</p>
          <div className="flex flex-wrap gap-2">
            {PRESET_INSTRUCTIONS.slice(0, -1).map((preset) => (
              <button
                key={preset.label}
                onClick={() => setInstruction(preset.instruction)}
                className={`text-xs px-3 py-1.5 rounded transition-colors ${
                  instruction === preset.instruction
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {preset.label}
              </button>
            ))}
            <button
              onClick={() => setUseCustom(true)}
              className="text-xs px-3 py-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
            >
              自定义
            </button>
          </div>
        </div>
      )}

      {/* Custom instruction input */}
      {(useCustom || instruction) && (
        <div className="mb-3">
          <label className="text-xs text-slate-500 mb-2 block">
            {useCustom ? '自定义指示' : '修改指示'}
          </label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="例如：语气更委婉、增加赔偿条款、简化表述..."
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 resize-none"
            rows={2}
          />
        </div>
      )}

      {/* Error display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-3 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleRefine}
          disabled={isRefining || !instruction.trim()}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
            isRefining || !instruction.trim()
              ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
          }`}
        >
          {isRefining ? (
            <span className="flex items-center justify-center gap-2">
              <div className="spinner"></div>
              优化中...
            </span>
          ) : (
            '开始优化'
          )}
        </button>
        <button
          onClick={onCancel}
          disabled={isRefining}
          className="py-2 px-4 rounded-lg font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          取消
        </button>
      </div>
    </motion.div>
  );
}

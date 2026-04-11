import { motion } from 'framer-motion';
import { useState } from 'react';

interface SuggestionDiffProps {
  original: string;
  refined: string;
  onCopyRefined: () => void;
}

export default function SuggestionDiff({ original, refined, onCopyRefined }: SuggestionDiffProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(refined);
    setCopied(true);
    onCopyRefined();
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="bg-slate-800 rounded-lg border border-slate-700 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-slate-300">
          优化结果
        </h3>
        <button
          onClick={handleCopy}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          {copied ? '已复制!' : '复制优化后的建议'}
        </button>
      </div>

      {/* Diff view */}
      <div className="space-y-3">
        {/* Original */}
        <div>
          <p className="text-xs text-slate-500 mb-1">原始建议</p>
          <div className="p-3 bg-slate-900/50 rounded border border-slate-700">
            <p className="text-sm text-green-300/60 line-through">{original}</p>
          </div>
        </div>

        {/* Arrow */}
        <div className="flex justify-center">
          <div className="text-slate-500">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </div>
        </div>

        {/* Refined */}
        <div>
          <p className="text-xs text-slate-500 mb-1">优化后建议</p>
          <div className="p-3 bg-green-500/10 rounded border border-green-500/30">
            <p className="text-sm text-green-300">{refined}</p>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="mt-3 pt-3 border-t border-slate-700">
        <p className="text-xs text-slate-500">
          建议已根据您的指示优化完成，您可以复制优化后的建议或在原文中使用。
        </p>
      </div>
    </motion.div>
  );
}

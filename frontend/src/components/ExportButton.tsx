import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';
import type { RiskCard, PerspectiveType } from '../types';

interface ExportButtonProps {
  documentId: string; 
  risks: RiskCard[];
  perspective: PerspectiveType;
}

export default function ExportButton({ documentId, perspective }: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const handleExport = async (format: 'docx' | 'markdown') => {
    if (!documentId) return;

    setIsExporting(true);
    setShowMenu(false);

    try {
      const blob = await api.exportReport(documentId, format, perspective, true, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'docx' ? 'docx' : 'md';
      a.download = `合同审查报告_${new Date().toISOString().slice(0, 10)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('导出失败，请重试');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        disabled={isExporting}
        className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 ${
          isExporting
            ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
            : 'bg-emerald-600 hover:bg-emerald-500 text-white'
        }`}
      >
        {isExporting ? (
          <>
            <div className="spinner"></div>
            <span>导出中...</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            <span>导出报告</span>
          </>
        )}
      </button>

      {/* Export Menu */}
      <AnimatePresence>
        {showMenu && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setShowMenu(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute bottom-full mb-2 left-0 right-0 bg-slate-800 rounded-lg border border-slate-700 shadow-xl overflow-hidden z-20"
            >
              <button
                onClick={() => handleExport('markdown')}
                className="w-full px-4 py-3 text-left text-slate-200 hover:bg-slate-700 transition-colors flex items-center gap-3"
              >
                <svg className="w-5 h-5 text-slate-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm0 2h8v8H4V6zm2 2v4h4V8H6zm8 0v4h4V8h-4z" />
                </svg>
                <span>Markdown 格式</span>
              </button>
              <button
                onClick={() => handleExport('docx')}
                className="w-full px-4 py-3 text-left text-slate-200 hover:bg-slate-700 transition-colors flex items-center gap-3"
              >
                <svg className="w-5 h-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm0 2h8v8H4V6zm2 2v4h4V8H6zm8 0v4h4V8h-4z" />
                </svg>
                <span>Word 格式</span>
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

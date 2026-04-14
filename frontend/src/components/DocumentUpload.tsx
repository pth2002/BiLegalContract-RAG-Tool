import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion } from 'framer-motion';

interface DocumentUploadProps {
  onUpload: (file: File, sessionId: string) => void; 
  disabled?: boolean;
}

export default function DocumentUpload({ onUpload, disabled }: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        const sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        onUpload(file, sessionId);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDragEnter: () => setIsDragging(true),
    onDragLeave: () => setIsDragging(false),
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    disabled,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-500 bg-blue-500/10'
            : isDragging
              ? 'border-blue-400 bg-blue-500/5'
              : 'border-slate-600 hover:border-slate-500 bg-slate-700/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />

        <div className="space-y-2">
          <svg
            className="mx-auto h-12 w-12 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>

          {isDragActive ? (
            <p className="text-blue-400">释放文件以上传</p>
          ) : (
            <>
              <p className="text-slate-300">拖拽 PDF 或 DOCX 文件到此处</p>
              <p className="text-slate-500 text-sm">支持上传长文档和短文档</p>
            </>
          )}
        </div>
      </div>

      {fileRejections.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-200 text-sm"
        >
          不支持的文件格式，仅支持 PDF 和 DOCX
        </motion.div>
      )}
    </div>
  );
}

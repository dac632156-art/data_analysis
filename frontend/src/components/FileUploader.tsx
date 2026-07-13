/* FileUploader - 宇宙传送门上传组件 */
import React, { useCallback, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FiUploadCloud, FiFile } from 'react-icons/fi';

const MAX_SIZE_MB = 50;
const MAX_SIZE_TEXT = `${MAX_SIZE_MB}MB`;

interface Props {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

const ACCEPTED = {
  'text/csv': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/json': ['.json'],
  'application/octet-stream': ['.db', '.sqlite'],
};

export default function FileUploader({ onUpload, disabled }: Props) {
  const [uploading, setUploading] = useState(false);
  const uploadingRef = useRef(false);

  const onDrop = useCallback(async (files: File[]) => {
    if (!files.length || uploadingRef.current) return;
    uploadingRef.current = true;
    setUploading(true);
    try {
      await onUpload(files[0]);
    } finally {
      uploadingRef.current = false;
      setUploading(false);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    disabled: disabled || uploading,
  });

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {/* 传送门 */}
      <div
        {...getRootProps()}
        className={`portal-upload ${isDragActive ? 'drag-active' : ''}`}
        role="button"
        aria-label="上传数据文件"
        tabIndex={0}
      >
        <input {...getInputProps()} />

        {/* 外环 */}
        <div className="portal-ring-outer" />

        {/* 中环 - 旋转光圈 */}
        <div className="portal-ring-middle" />

        {/* 第四环 - 第二道光圈（双环感） */}
        <div className="portal-ring-quad" />

        {/* 内环 */}
        <div className="portal-ring-inner" />

        {/* 粒子 */}
        <div className="portal-particles">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="portal-particle" />
          ))}
        </div>

        {/* 能量核心 */}
        <div className="portal-core">
          {uploading ? (
            <div className="w-8 h-8 rounded-full border-2 border-[#a78bfa] border-t-transparent animate-spin" />
          ) : isDragActive ? (
            <FiUploadCloud className="w-8 h-8 text-[#c4b5fd]" />
          ) : (
            <FiFile className="w-8 h-8 text-[#8b5cf6]" />
          )}
        </div>
      </div>

      {/* 提示文字 */}
      <div className="text-center space-y-1">
        <p className="text-sm text-slate-300">
          {isDragActive
            ? '释放以开启数据传送'
            : '点击能量核心或拖拽文件到此'}
        </p>
        <p className="text-xs text-slate-500">
          支持 CSV · Excel · JSON · SQLite（最大 {MAX_SIZE_TEXT}）
        </p>
      </div>

      {/* 格式标签 */}
      <div className="flex gap-2">
        {['csv', 'xlsx', 'json', 'db'].map((ext) => (
          <span
            key={ext}
            className="px-2.5 py-1 text-xs rounded-full bg-white/5 text-slate-400 border border-white/10"
          >
            .{ext}
          </span>
        ))}
      </div>
    </div>
  );
}

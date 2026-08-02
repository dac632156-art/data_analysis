/* FileUploader - 宇宙传送门上传组件 */
import React, { useCallback, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FiUploadCloud, FiFile } from 'react-icons/fi';

// 上传上限：优先读 Vite 环境变量 VITE_MAX_UPLOAD_SIZE_MB（本地 .env.local 可设 5120=5GB）
// 线上未设置该变量时默认 30MB；需与后端 config.py 的 MAX_UPLOAD_SIZE_MB 保持一致（修复八）
const MAX_SIZE_MB = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB) || 30;
const MAX_SIZE_TEXT = MAX_SIZE_MB >= 1024
  ? `${(MAX_SIZE_MB / 1024).toFixed(1)}GB`
  : `${MAX_SIZE_MB}MB`;

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
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (files: File[]) => {
    if (!files.length || uploadingRef.current) return;
    setError(null);
    uploadingRef.current = true;
    setUploading(true);
    // 修复六：逐文件顺序上传，部分失败不影响其余；收集失败提示
    const failures: string[] = [];
    try {
      for (const f of files) {
        try {
          await onUpload(f);
        } catch (e: any) {
          failures.push(`${f.name}：${e?.message || '上传失败'}`);
        }
      }
    } finally {
      uploadingRef.current = false;
      setUploading(false);
    }
    if (failures.length) {
      setError(`部分文件未上传（${failures.length} 个）：${failures[0]}`);
    }
  }, [onUpload]);

  const onDropRejected = useCallback((rejections: any[]) => {
    for (const r of rejections) {
      if (r.errors?.some((e: any) => e.code === 'file-too-large')) {
        setError(`文件超过 ${MAX_SIZE_TEXT} 限制，请上传 ${MAX_SIZE_TEXT} 以内的文件`);
        return;
      }
    }
    if (rejections.length) {
      setError('存在不支持的文件格式（支持 CSV · Excel · JSON · SQLite）');
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: ACCEPTED,
    // 修复八：放开 maxFiles，支持一次性多文件
    maxSize: MAX_SIZE_MB * 1024 * 1024,
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

      {/* 超限警告 */}
      {error && (
        <p className="text-xs text-rose-400 text-center">{error}</p>
      )}

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

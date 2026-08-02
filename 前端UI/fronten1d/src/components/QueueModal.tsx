/* QueueModal - 上传排队等待弹窗（浅色玻璃拟态） */
import React from 'react';

interface QueueModalProps {
  open: boolean;
  /** 当前排队位次（1 起） */
  position: number;
  /** 并发数据插槽上限，用于展示"当前 N/N 位已满" */
  maxSessions: number;
  /** 取消排队回调 */
  onCancel: () => void;
}

export default function QueueModal({ open, position, maxSessions, onCancel }: QueueModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="系统繁忙，正在排队"
    >
      <div
        className="relative w-[90vw] max-w-[380px] rounded-2xl border border-white/70 p-7 text-center glass-card"
      >
        <div className="mx-auto mb-5 h-14 w-14 rounded-full border-2 border-violet-400 border-t-transparent animate-spin" />

        <h2 className="text-2xl font-bold text-slate-900">系统繁忙，正在排队</h2>
        <p className="mt-2 text-sm font-medium text-violet-600">
          当前 {maxSessions}/{maxSessions} 位已满，轮到您将自动上传
        </p>

        <p className="mt-5 text-sm text-slate-500">
          您排在第{' '}
          <span className="text-violet-600 text-4xl font-extrabold align-middle" aria-live="polite">
            {position}
          </span>{' '}
          位
        </p>

        <button
          type="button"
          onClick={onCancel}
          className="mt-6 w-full cursor-pointer rounded-lg border border-slate-300 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-white/70 focus:outline-none focus:ring-2 focus:ring-violet-400/40"
        >
          取消排队
        </button>
      </div>
    </div>
  );
}

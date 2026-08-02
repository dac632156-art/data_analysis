/* QueueModal - 上传排队等待弹窗（Galaxy AI Analytics 银河紫玻璃拟态） */
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#020617]/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="系统繁忙，正在排队"
    >
      <div
        className="relative w-[90vw] max-w-[380px] rounded-2xl border border-[#8B5CF6]/30 p-7 text-center"
        style={{
          background: 'rgba(15,23,42,0.85)',
          boxShadow: '0 0 40px rgba(139,92,246,0.25)',
        }}
      >
        {/* 旋转能量环：表达"系统正在为您排队" */}
        <div className="mx-auto mb-5 h-14 w-14 rounded-full border-2 border-[#a78bfa] border-t-transparent animate-spin" />

        <h2
          className="text-2xl font-bold text-[#F8FAFC]"
          style={{ textShadow: '0 0 18px rgba(167,139,250,0.45)' }}
        >
          系统繁忙，正在排队
        </h2>
        <p className="mt-2 text-sm font-medium text-[#C4B5FD]">
          当前 {maxSessions}/{maxSessions} 位已满，轮到您将自动上传
        </p>

        <p className="mt-5 text-sm text-[#94A3B8]">
          您排在第{' '}
          <span
            className="text-[#8B5CF6] text-4xl font-extrabold align-middle"
            style={{ textShadow: '0 0 20px rgba(139,92,246,0.6)' }}
            aria-live="polite"
          >
            {position}
          </span>{' '}
          位
        </p>

        <button
          type="button"
          onClick={onCancel}
          className="mt-6 w-full cursor-pointer rounded-lg border border-white/15 py-2.5 text-sm text-slate-300 transition hover:bg-[#8B5CF6]/10 focus:outline-none focus:ring-2 focus:ring-[#8B5CF6]/40"
        >
          取消排队
        </button>
      </div>
    </div>
  );
}

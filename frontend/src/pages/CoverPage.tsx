/* CoverPage - 应用封面（浅色科技 landing + 视频背景 + 鼠标水平 seek） */
import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const SENSITIVITY = 0.8;

export default function CoverPage() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const targetTimeRef = useRef<number>(0);
  const seekingRef = useRef<boolean>(false);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // 直接 seek 到目标时间（mousemove 已做节流，避免 flood）
    const seekTo = (t: number) => {
      const clamped = Math.max(0, Math.min(video.duration || 0, t));
      if (Math.abs(video.currentTime - clamped) < 0.005) return;
      if (seekingRef.current) return; // 正在 seek 则跳过，等 seeked 后再处理
      seekingRef.current = true;
      video.currentTime = clamped;
    };

    const handleSeeked = () => {
      seekingRef.current = false;
    };

    // rAF 每帧把 currentTime 立刻拉到目标点（不缓动，跟手）
    const tick = () => {
      if (video.duration > 0 && isFinite(video.duration)) {
        seekTo(targetTimeRef.current);
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    let lastMove = 0;
    const handleMouseMove = (e: MouseEvent) => {
      const now = performance.now();
      if (now - lastMove < 16) return; // 节流到 ~60fps，避免高频 event 触发 seek flood
      lastMove = now;
      if (video.duration === 0 || !isFinite(video.duration)) return;
      const ratio = Math.max(0, Math.min(1, e.clientX / window.innerWidth));
      targetTimeRef.current = Math.max(0, Math.min(video.duration, ratio * SENSITIVITY * video.duration));
    };

    rafRef.current = requestAnimationFrame(tick);
    video.addEventListener('seeked', handleSeeked);
    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      video.removeEventListener('seeked', handleSeeked);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div
      className="relative w-full h-screen overflow-hidden"
      style={{ fontFamily: 'PingFang SC, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif' }}
    >
      {/* 视频背景 */}
      <video
        ref={videoRef}
        src="/机器人.mp4"
        muted
        playsInline
        preload="auto"
        className="absolute inset-0 w-full h-full object-cover"
        style={{ background: '#F8FAFC' }}
      />

      {/* 顶部 Header：只保留左上角 logo（红色框内容已删除） */}
      <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-6">
        {/* 蓝色框：项目图标 + 名称 */}
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-full flex-shrink-0"
            style={{
              background: 'radial-gradient(circle at 30% 30%, #38BDF8 0%, #8B5CF6 70%, #22D3EE 100%)',
              boxShadow: '0 2px 10px rgba(56,189,248,0.35)',
            }}
          />
          <span className="text-lg font-bold tracking-tight" style={{ color: '#0F172A' }}>
            DataMind AI
          </span>
        </div>
      </header>

      {/* 中间 Hero 内容 */}
      <main className="relative z-10 w-full h-full flex flex-col px-8 md:px-16 lg:px-24 pt-28 md:pt-32">
        <div className="max-w-2xl">
          {/* 大标题：放大占位 */}
          <h1
            className="font-bold tracking-tight"
            style={{ color: '#0F172A', fontSize: '96px', fontWeight: 800, lineHeight: 1.05, letterSpacing: '-0.02em' }}
          >
            DataMind AI
          </h1>

          {/* 绿色框：英文翻译成中文 */}
          <p
            className="mt-7"
            style={{ color: '#334155', fontSize: '24px', fontWeight: 400, lineHeight: 1.7 }}
          >
            释放数据的智能潜力，遇见你的 AI 数据伙伴。
          </p>

          {/* 按钮：保留 Start for Free（中文），删除 Learn More（红色框） */}
          <div className="mt-10 flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="px-9 py-4 rounded-full text-lg font-medium transition-all duration-200 hover:scale-105 focus:outline-none"
              style={{
                color: '#FFFFFF',
                background: '#38BDF8',
                boxShadow: '0 6px 20px rgba(56,189,248,0.35)',
                cursor: 'pointer',
              }}
            >
              免费开始
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

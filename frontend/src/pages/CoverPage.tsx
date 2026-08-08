/* CoverPage - 应用封面（浅色科技 landing + 机器人抽帧图 + 鼠标水平驱动）
 * 用 robot_frames 下 160 张抽帧图渲染，鼠标水平位置 → 当前帧。
 * 纯鼠标驱动：鼠标不动则停在首帧，不会自动播放。
 * 性能优化：用 ref 直接改 DOM 的 img.src，不走 React 重渲染，跟手更及时。
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const TOTAL_FRAMES = 160;
const SENSITIVITY = 0.8; // 鼠标滑到右 80% 才走到最后一帧（沿用原手感）
const FRAME_PATH = (i: number) => `/robot_frames/frame_${String(i).padStart(4, '0')}.jpg`;

export default function CoverPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false); // 全部帧预加载完成
  const imgRef = useRef<HTMLImageElement>(null); // 直接改 DOM src，绕开 React 重渲染
  const currentIdxRef = useRef(1); // 上一次帧号，用于去重
  const readyRef = useRef(false);

  // 预加载 160 张帧图，加载完成再显示，避免首帧闪烁
  useEffect(() => {
    let cancelled = false;
    let loaded = 0;
    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      img.src = FRAME_PATH(i);
      img.onload = () => {
        loaded += 1;
        if (loaded === TOTAL_FRAMES && !cancelled) setReady(true);
      };
    }
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const now = performance.now();
      if (now - lastMove < 10) return; // 节流到 ~100fps，跟手更紧（改用 ref 直写后单次切换极轻）
      lastMove = now;
      if (!readyRef.current) return; // 未预加载完不切换，保持首帧
      const ratio = Math.max(0, Math.min(1, e.clientX / window.innerWidth));
      const idx = Math.max(
        1,
        Math.min(TOTAL_FRAMES, Math.round(ratio * SENSITIVITY * TOTAL_FRAMES)),
      );
      if (idx !== currentIdxRef.current) {
        currentIdxRef.current = idx;
        // 直接写 DOM，绕开 React setState → 重渲染链路，换图最快最跟手
        if (imgRef.current) imgRef.current.src = FRAME_PATH(idx);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div
      className="relative w-full h-screen overflow-hidden"
      style={{ fontFamily: 'PingFang SC, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif' }}
    >
      {/* 机器人抽帧图（鼠标水平位置映射帧序号，纯鼠标驱动、不自动播放） */}
      <img
        ref={imgRef}
        src={FRAME_PATH(1)}
        alt="DataMind AI 智能机器人"
        className="absolute inset-0 w-full h-full object-cover"
        style={{
          background: '#F8FAFC',
          opacity: ready ? 1 : 0.6,
          willChange: 'transform',
        }}
        draggable={false}
      />

      {/* 顶部 Header：只保留左上角 logo */}
      <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-6">
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
          <h1
            className="font-bold tracking-tight"
            style={{ color: '#0F172A', fontSize: '96px', fontWeight: 800, lineHeight: 1.05, letterSpacing: '-0.02em' }}
          >
            DataMind AI
          </h1>

          <p
            className="mt-7"
            style={{ color: '#334155', fontSize: '24px', fontWeight: 400, lineHeight: 1.7 }}
          >
            释放数据的智能潜力，遇见你的 AI 数据伙伴。
          </p>

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

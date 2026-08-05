/* CoverPage - 应用封面（浅色科技 landing + 抽帧图序列 + 鼠标水平 seek）
 * 用 80 张静态抽帧图替代原视频，避免浏览器实时解码视频帧导致的卡顿。
 * 鼠标水平位置 → 帧序号映射，切换 <img>.src 即可，零解码、跟手不卡。
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const TOTAL_FRAMES = 80; // robot_frames/frame_0001.jpg ~ frame_0080.jpg
const SENSITIVITY = 0.8; // 鼠标滑到右 80% 才转到最后一帧（沿用原视频手感）
const FRAME_PATH = (i: number) =>
  `/robot_frames/frame_${String(i).padStart(4, '0')}.jpg`;

export default function CoverPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false); // 全部帧预加载完成
  const [currentIdx, setCurrentIdx] = useState(1); // 当前显示的 1-based 帧序号
  const currentIdxRef = useRef(1);
  const readyRef = useRef(false);

  // 预加载全部 80 张图，完成后才启用鼠标切换，避免白屏/切换闪烁
  useEffect(() => {
    let alive = true;
    let loaded = 0;
    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      img.onload = img.onerror = () => {
        loaded += 1;
        if (loaded >= TOTAL_FRAMES && alive) {
          readyRef.current = true;
          setReady(true);
        }
      };
      img.src = FRAME_PATH(i);
    }
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let lastMove = 0;
    const handleMouseMove = (e: MouseEvent) => {
      const now = performance.now();
      if (now - lastMove < 16) return; // 节流到 ~60fps，避免高频 setState
      lastMove = now;
      if (!readyRef.current) return; // 未预加载完不切换，保持首帧
      const ratio = Math.max(0, Math.min(1, e.clientX / window.innerWidth));
      const idx = Math.max(
        1,
        Math.min(
          TOTAL_FRAMES,
          Math.round(ratio * SENSITIVITY * (TOTAL_FRAMES - 1)) + 1
        )
      );
      if (idx !== currentIdxRef.current) {
        currentIdxRef.current = idx;
        setCurrentIdx(idx);
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
      {/* 机器人抽帧图序列（替代视频，鼠标水平位置映射帧） */}
      <img
        src={FRAME_PATH(currentIdx)}
        alt="DataMind AI 智能机器人"
        className="absolute inset-0 w-full h-full object-cover"
        style={{
          background: '#F8FAFC',
          opacity: ready ? 1 : 0.6,
          // 高质量缩放渲染：2K 图铺满时浏览器用高质量插值而非默认钝化，
          // 缓解 object-cover 放大后的边缘发虚（配合已超分的 2K 资源生效）。
          imageRendering: 'high-quality',
          willChange: 'transform',
        } as React.CSSProperties}
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

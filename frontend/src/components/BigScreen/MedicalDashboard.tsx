/* MedicalDashboard - V5 Card BI 包装器
   不再自己渲染布局，只做一件事：
   接收 cards + meta → 交给 CardGrid 渲染 */
import React from 'react';
import CardGrid, { type CardItem, type CardMeta } from '../CardGrid';

interface Props {
  cards?: CardItem[];
  meta?: CardMeta;
  title?: string;
}

export default function MedicalDashboard({ cards = [], meta, title = '数据看板' }: Props) {
  return (
    <div className="big-screen w-full h-full flex flex-col overflow-auto"
      style={{ background: 'linear-gradient(135deg, #020518 0%, #060d2a 50%, #0a0a1e 100%)' }}>

      {/* 顶部标题栏 */}
      <div className="relative flex items-center justify-between px-6 py-3 border-b border-[#1a1f3a]/50">
        <div className="flex items-center gap-3">
          <div className="w-2 h-6 bg-gradient-to-b from-[#22d3ee] to-[#8b5cf6] rounded-full" />
          <h1 className="text-lg font-bold text-white tracking-wider"
            style={{ textShadow: '0 0 20px rgba(34,211,238,0.4)' }}>
            {title}
          </h1>
        </div>
      </div>

      {/* CardGrid 渲染区 */}
      <div className="flex-1 overflow-hidden">
        <CardGrid cards={cards} meta={meta} />
      </div>
    </div>
  );
}
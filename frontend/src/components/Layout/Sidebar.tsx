/* Sidebar - 侧边栏导航 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { FiUpload, FiRefreshCw, FiBarChart2, FiLayout } from 'react-icons/fi';
import { useData, AI_PROVIDERS } from '../../contexts/DataContext';

const navItems = [
  { path: '/upload', label: '数据上传', icon: FiUpload },
  { path: '/clean', label: '数据清洗', icon: FiRefreshCw },
  { path: '/analysis', label: '分析可视化', icon: FiBarChart2 },
  { path: '/dashboard', label: '仪表盘', icon: FiLayout },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useData();
  const hasData = state.rows > 0;
  const currentProvider = AI_PROVIDERS.find(p => p.id === state.aiProvider);
  const defaultModel = currentProvider?.model || '';

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 z-20 flex flex-col"
      style={{
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(139, 92, 246, 0.1)',
        boxShadow: '4px 0 20px rgba(0, 0, 0, 0.3)',
      }}
    >
      {/* Logo */}
      <div className="px-5 py-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-[#f8fafc] tracking-tight"
          style={{ textShadow: '0 0 20px rgba(139, 92, 246, 0.4)' }}
        >
          DataMind AI
        </h1>
        <p className="text-sm text-[#94a3b8] mt-0.5">数据分析智能体</p>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path;
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all ${
                active
                  ? 'bg-[#8b5cf6]/20 text-[#f8fafc] border border-[#8b5cf6]/30 shadow-[0_0_12px_rgba(139,92,246,0.15)]'
                  : 'text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#8b5cf6]/8'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      {/* API Key 配置 */}
      <div className="px-4 py-4 border-t border-white/[0.06] space-y-2">
        <label className="text-xs text-slate-500 block">AI 模型</label>
        <select
          value={state.aiProvider}
          onChange={(e) => dispatch({ type: 'SET_AI_PROVIDER', aiProvider: e.target.value })}
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50 transition-colors"
        >
          {AI_PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <label className="text-xs text-slate-500 block mt-2">模型名称（可选）</label>
        <input
          type="text"
          value={state.customModel}
          onChange={(e) => dispatch({ type: 'SET_CUSTOM_MODEL', customModel: e.target.value })}
          placeholder={defaultModel || '默认模型'}
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8b5cf6]/50 transition-colors"
        />
        <p className="text-[10px] text-slate-500 mt-0.5">
          留空则使用默认模型（{defaultModel || '—'}），可填入其他模型名覆盖
        </p>
        <label className="text-xs text-slate-500 block mt-2">API Key</label>
        <input
          type="password"
          value={state.apiKey}
          onChange={(e) => dispatch({ type: 'SET_API_KEY', apiKey: e.target.value })}
          placeholder="输入 API Key..."
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8b5cf6]/50 transition-colors"
        />
        <p className="text-[10px] text-slate-600 leading-relaxed">
          选择模型后输入对应服务商的 API Key 即可使用
        </p>
      </div>

      {/* 数据信息 */}
      {hasData && (
        <div className="px-4 py-3 border-t border-white/[0.06]">
          <p className="text-xs text-slate-500 truncate">{state.fileName}</p>
          <p className="text-xs text-slate-400">{state.rows.toLocaleString()} 行 · {state.columns} 列</p>
        </div>
      )}
    </aside>
  );
}

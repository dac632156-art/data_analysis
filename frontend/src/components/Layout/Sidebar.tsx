/* Sidebar - 侧边栏导航 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { FiUpload, FiRefreshCw, FiBarChart2, FiLayout, FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import { useData, AI_PROVIDERS } from '../../contexts/DataContext';

const navItems = [
  { path: '/upload', label: '数据上传', icon: FiUpload },
  { path: '/clean', label: '数据清洗', icon: FiRefreshCw },
  { path: '/analysis', label: '分析可视化', icon: FiBarChart2 },
  { path: '/dashboard', label: '仪表盘', icon: FiLayout },
];

export default function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useData();
  const hasData = state.rows > 0;
  const currentProvider = AI_PROVIDERS.find(p => p.id === state.aiProvider);
  const defaultModel = currentProvider?.model || '';
  const defaultBaseUrl = currentProvider?.baseUrl || '';

  return (
    <aside className={`fixed left-0 top-0 h-screen z-20 flex flex-col overflow-y-auto overflow-x-hidden pb-4 transition-[width] duration-300 ${collapsed ? 'w-20' : 'w-64'}`}
      style={{
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(139,92,246,0.1)',
        boxShadow: '4px 0 20px rgba(0, 0, 0, 0.3)',
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(139,92,246,0.35) transparent',
      }}
    >
      {/* Logo + 折叠按钮 */}
      <div className={`flex items-center py-6 border-b border-white/[0.06] ${collapsed ? 'justify-center px-2' : 'px-5 justify-between'}`}>
        {!collapsed && (
          <div>
            <h1 className="text-xl font-bold text-[#f8fafc] tracking-tight"
              style={{ textShadow: '0 0 20px rgba(139,92,246,0.4)' }}
            >
              DataMind AI
            </h1>
            <p className="text-sm text-[#94a3b8] mt-0.5">数据分析智能体</p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
          aria-expanded={!collapsed}
          className="p-1.5 rounded-lg text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#8B5CF6]/10 transition-colors flex-shrink-0"
        >
          {collapsed ? <FiChevronRight className="w-4 h-4" /> : <FiChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-shrink-0 px-3 py-4 space-y-1">
        {navItems.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path;
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              title={collapsed ? label : undefined}
              aria-label={label}
              className={`w-full flex items-center gap-3 rounded-lg text-sm transition-all ${
                collapsed ? 'justify-center px-0' : 'px-4'
              } py-2.5 ${
                active
                  ? 'bg-[#8B5CF6]/20 text-[#f8fafc] border border-[#8B5CF6]/30 shadow-[0_0_12px_rgba(139,92,246,0.15)]'
                  : 'text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#8B5CF6]/8'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </button>
          );
        })}
      </nav>

      {/* API Key 配置（展开时显示） */}
      {!collapsed && (
      <div className="flex-shrink-0 px-4 py-4 border-t border-white/[0.06] space-y-2">
        <label className="text-xs text-slate-500 block">AI 模型</label>
        <select
          value={state.aiProvider}
          onChange={(e) => dispatch({ type: 'SET_AI_PROVIDER', aiProvider: e.target.value })}
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8B5CF6]/50 transition-colors"
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
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-colors"
        />
        <p className="text-[10px] text-slate-500 mt-0.5">
          留空则使用默认模型（{defaultModel || '—'}），可填入其他模型名覆盖
        </p>
        {state.aiProvider === 'qwen' && (
          <p className="text-[10px] text-slate-400 mt-0.5 leading-relaxed">
            常用：qwen3.7-plus / qwen3.7-max / qwen-plus / qwen-max / qwen-turbo<br/>
            新模型需在百炼控制台开通权限，否则会报 model_not_found
          </p>
        )}
        {state.aiProvider === 'deepseek' && (
          <p className="text-[10px] text-slate-400 mt-0.5">
            常用：deepseek-chat / deepseek-reasoner
          </p>
        )}
        {state.aiProvider === 'zhipu' && (
          <p className="text-[10px] text-slate-400 mt-0.5">
            常用：glm-4-flash / glm-4-plus / glm-4-long
          </p>
        )}
        <label className="text-xs text-slate-500 block mt-2">API 地址（可选）</label>
        <input
          type="text"
          value={state.customBaseUrl}
          onChange={(e) => dispatch({ type: 'SET_CUSTOM_BASE_URL', customBaseUrl: e.target.value })}
          placeholder={defaultBaseUrl || '默认地址'}
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-colors"
        />
        <p className="text-[10px] text-slate-500 mt-0.5">
          百炼新版需填：https://{'{'}空间ID{'}'}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
        </p>
        <label className="text-xs text-slate-500 block mt-2">API Key</label>
        <input
          type="password"
          value={state.apiKey}
          onChange={(e) => dispatch({ type: 'SET_API_KEY', apiKey: e.target.value })}
          placeholder="输入 API Key..."
          className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-colors"
        />
        <p className="text-[10px] text-slate-600 leading-relaxed">
          选择模型后输入对应服务商的 API Key 即可使用
        </p>
      </div>
      )}

      {/* 数据信息（展开时显示） */}
      {!collapsed && hasData && (
        <div className="flex-shrink-0 px-4 py-3 border-t border-white/[0.06]">
          <p className="text-xs text-slate-500 truncate">{state.fileName}</p>
          <p className="text-xs text-slate-400">{state.rows.toLocaleString()} 行 · {state.columns} 列</p>
        </div>
      )}
    </aside>
  );
}

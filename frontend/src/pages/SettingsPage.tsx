/* Settings - 会话与会话配置（浅色玻璃主题） */
import React from 'react';
import { useData } from '../contexts/DataContext';
import { clearData } from '../api/client';
import { FiSettings, FiRefreshCw, FiCpu, FiDatabase } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

export default function SettingsPage() {
  const { state, dispatch, ensureValidSession } = useData();
  const navigate = useNavigate();

  const handleRelease = async () => {
    if (!confirm('确定结束会话？该会话的全部数据（上传数据、清洗结果、分析产物、已保存图表）将被彻底清空。')) return;
    try {
      await clearData(state.sessionId);
    } catch { /* ignore */ }
    dispatch({ type: 'CLEAR_DATA' });
    dispatch({ type: 'SET_QUOTA', usedBytes: 0, quotaBytes: 0 });
    await ensureValidSession();
    alert('会话已结束，已自动创建新会话。');
  };

  const info = [
    { label: '会话 ID', value: state.sessionId.slice(0, 8) + '…' },
    { label: '当前报表', value: state.fileName || '（无）' },
    { label: '数据规模', value: state.rows > 0 ? `${state.rows.toLocaleString()} 行 × ${state.columns} 列` : '（无）' },
    { label: 'AI 服务商', value: state.aiProvider },
    { label: '已用额度', value: `${Math.round(state.usedBytes / 1024 / 1024)} MB` },
  ];

  return (
    <div className="page-enter">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/70 border border-violet-200 text-violet-600 shadow-[0_4px_14px_rgba(139,92,246,0.18)]">
          <FiSettings className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Settings</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理当前会话与 AI 配置</p>
        </div>
      </div>

      <div className="glass-card p-6 max-w-2xl space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {info.map((it) => (
            <div key={it.label} className="rounded-xl bg-white/60 border border-slate-200/70 p-4">
              <p className="text-xs text-slate-500 mb-1">{it.label}</p>
              <p className="text-sm font-semibold text-slate-800 truncate">{it.value}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          <button
            onClick={() => navigate('/models')}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold text-violet-700 bg-violet-100 hover:bg-violet-200 transition-colors"
          >
            <FiCpu className="w-4 h-4" /> 配置 AI 模型
          </button>
          <button
            onClick={handleRelease}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-rose-500 hover:bg-rose-600 transition-colors"
          >
            <FiRefreshCw className="w-4 h-4" /> 释放当前会话
          </button>
        </div>

        <p className="text-xs text-slate-600 flex items-center gap-1.5">
          <FiDatabase className="w-3.5 h-3.5" />
          释放会话后需重新上传数据；AI 配置（API Key 等）会保留在本地。
        </p>
      </div>
    </div>
  );
}

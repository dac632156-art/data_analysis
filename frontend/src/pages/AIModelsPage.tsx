/* AI Models - AI 模型配置（浅色玻璃主题，复用 DataContext 的 AI_PROVIDERS） */
import React, { useState } from 'react';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import { saveApiConfig } from '../api/client';
import { FiCpu, FiCheck } from 'react-icons/fi';

export default function AIModelsPage() {
  const { state, dispatch } = useData();
  const [saved, setSaved] = useState(false);

  const selectedProvider = AI_PROVIDERS.find(p => p.id === state.aiProvider);
  const defaultModel = selectedProvider?.model || '';
  const defaultBaseUrl = selectedProvider?.baseUrl || '';

  const onSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await saveApiConfig(state.sessionId, {
        api_key: state.apiKey,
        ai_provider: state.aiProvider,
        custom_model: state.customModel,
        custom_base_url: state.customBaseUrl,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('[AIModelsPage] 保存 AI 配置失败', err);
      alert('保存失败，请稍后重试');
    }
  };

  return (
    <div className="page-enter">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/70 border border-violet-200 text-violet-600 shadow-[0_4px_14px_rgba(139,92,246,0.18)]">
          <FiCpu className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">AI Models</h1>
          <p className="text-sm text-slate-500 mt-0.5">配置用于数据分析与对话的 AI 模型</p>
        </div>
      </div>

      <form onSubmit={onSave} className="glass-card p-6 max-w-2xl space-y-5">
        {/* 服务商下拉 */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">AI 服务商</label>
          <select
            value={state.aiProvider}
            onChange={(e) => dispatch({ type: 'SET_AI_PROVIDER', aiProvider: e.target.value })}
            className="glass-input w-full px-3 py-2.5 text-sm"
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* 模型名称 */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">模型名称（可选，留空使用默认）</label>
          <input
            type="text"
            value={state.customModel}
            onChange={(e) => dispatch({ type: 'SET_CUSTOM_MODEL', customModel: e.target.value })}
            placeholder={defaultModel || '默认模型'}
            className="glass-input w-full px-3 py-2.5 text-sm"
          />
          <p className="text-xs text-slate-400 mt-1">
            默认模型：{defaultModel || '—'}
          </p>
        </div>

        {/* API 地址 */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">API 地址（可选，留空使用默认）</label>
          <input
            type="text"
            value={state.customBaseUrl}
            onChange={(e) => dispatch({ type: 'SET_CUSTOM_BASE_URL', customBaseUrl: e.target.value })}
            placeholder={defaultBaseUrl || '默认地址'}
            className="glass-input w-full px-3 py-2.5 text-sm"
          />
          <p className="text-xs text-slate-400 mt-1">
            默认地址：{defaultBaseUrl || '—'}
          </p>
        </div>

        {/* API Key */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">API Key</label>
          <input
            type="password"
            value={state.apiKey}
            onChange={(e) => dispatch({ type: 'SET_API_KEY', apiKey: e.target.value })}
            placeholder="输入 API Key..."
            className="glass-input w-full px-3 py-2.5 text-sm"
          />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl text-white text-sm font-semibold bg-violet-600 hover:bg-violet-700 transition-colors shadow-[0_4px_14px_rgba(139,92,246,0.35)]"
          >
            保存配置
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-emerald-600 font-medium">
              <FiCheck className="w-4 h-4" /> 已保存
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

/* AI Models - AI 模型配置（从侧边栏迁移而来，浅色玻璃主题） */
import React, { useState } from 'react';
import { useData } from '../contexts/DataContext';
import { FiCpu, FiCheck } from 'react-icons/fi';

const PROVIDERS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  moonshot: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  qwen: ['qwen-turbo', 'qwen-plus', 'qwen-max'],
  gemini: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash'],
  custom: [],
};
const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  moonshot: 'Moonshot',
  qwen: 'Qwen',
  gemini: 'Gemini',
  custom: '自定义',
};

export default function AIModelsPage() {
  const { state, dispatch } = useData();
  const [saved, setSaved] = useState(false);

  const setConfig = (patch: Partial<typeof state>) => dispatch({ type: 'setConfig', payload: patch });

  const onSave = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem('datamind-config', JSON.stringify({
        aiProvider: state.aiProvider,
        customModel: state.customModel,
        customBaseUrl: state.customBaseUrl,
        useCustomKey: state.useCustomKey,
        customKey: state.customKey,
      }));
    } catch { /* ignore */ }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const models = PROVIDERS[state.aiProvider] || [];

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
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">AI 服务商</label>
          <select
            value={state.aiProvider}
            onChange={(e) => setConfig({ aiProvider: e.target.value })}
            className="glass-input w-full px-3 py-2.5 text-sm"
          >
            {Object.keys(PROVIDERS).map((p) => (
              <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
            ))}
          </select>
        </div>

        {state.aiProvider !== 'custom' ? (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">模型</label>
            <select
              value={state.customModel}
              onChange={(e) => setConfig({ customModel: e.target.value })}
              className="glass-input w-full px-3 py-2.5 text-sm"
            >
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">自定义模型名称</label>
            <input
              value={state.customModel}
              onChange={(e) => setConfig({ customModel: e.target.value })}
              placeholder="例如：my-model"
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
        )}

        {state.aiProvider === 'custom' && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">自定义 API Base URL</label>
            <input
              value={state.customBaseUrl}
              onChange={(e) => setConfig({ customBaseUrl: e.target.value })}
              placeholder="https://your-endpoint/v1"
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
        )}

        <div className="flex items-center gap-2.5 pt-1">
          <input
            type="checkbox"
            id="useCustomKey"
            checked={state.useCustomKey}
            onChange={(e) => setConfig({ useCustomKey: e.target.checked })}
            className="w-4 h-4 rounded accent-violet-600"
          />
          <label htmlFor="useCustomKey" className="text-sm text-slate-700">使用自定义 API Key（否则读取环境变量）</label>
        </div>

        {state.useCustomKey && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">API Key</label>
            <input
              type="password"
              value={state.customKey}
              onChange={(e) => setConfig({ customKey: e.target.value })}
              placeholder="sk-..."
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
        )}

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

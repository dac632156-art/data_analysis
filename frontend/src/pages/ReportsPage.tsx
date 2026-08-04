/* Reports - AI 分析报告生成与查看（浅色玻璃主题） */
import React, { useState, useRef } from 'react';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import { FiFileText, FiArrowUpRight } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

interface ReportSection {
  type: string;
  title: string;
  content?: string;
  insights?: Array<string | { chart_title?: string; analysis: string }>;
}

const SECTION_ICON: Record<string, string> = {
  overview: '📋', kpi: '📊', trend: '📈', structure: '🏗️',
  top: '🏆', anomaly: '⚠️', conclusion: '💡', suggestions: '🚀', next_steps: '🎯',
};

export default function ReportsPage() {
  const { state } = useData();
  const navigate = useNavigate();
  const [generating, setGenerating] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [error, setError] = useState('');
  const reqRef = useRef<number>(0);

  const generate = async () => {
    if (!state.sessionId || !state.apiKey) return;
    const reqId = ++reqRef.current;
    setGenerating(true);
    setError('');
    setSections([]);
    setStatusText('🔍 正在进行数据统计分析（阶段1-3）...');
    try {
      const provider = AI_PROVIDERS.find((p) => p.id === state.aiProvider);
      // 已保存分析包以「后端 session.saved_packages」为唯一真相源，后端自读兜底，不携带 localStorage 副本。
      const result = await api.generateAIReport(
        state.sessionId,
        state.apiKey,
        provider?.baseUrl,
        provider?.model,
        undefined,
      );
      if (reqId !== reqRef.current) return;
      setSections(result.sections || []);
      setStatusText('✅ 报告生成完成');
    } catch (e: any) {
      if (reqId !== reqRef.current) return;
      setError(e?.message || '报告生成失败');
      setStatusText('');
    } finally {
      if (reqId === reqRef.current) setGenerating(false);
    }
  };

  return (
    <div className="page-enter">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/70 border border-violet-200 text-violet-600 shadow-[0_4px_14px_rgba(139,92,246,0.18)]">
          <FiFileText className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports</h1>
          <p className="text-sm text-slate-500 mt-0.5">基于当前数据集生成 AI 数据分析报告</p>
        </div>
      </div>

      {!state.sessionId ? (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-600">尚未选择数据集</p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-violet-600 hover:bg-violet-700 transition-colors"
          >
            前往上传数据 <FiArrowUpRight className="w-4 h-4" />
          </button>
        </div>
      ) : !state.apiKey ? (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-600">尚未配置 AI API Key</p>
          <button
            onClick={() => navigate('/models')}
            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-violet-600 hover:bg-violet-700 transition-colors"
          >
            前往配置 AI <FiArrowUpRight className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          <button
            onClick={generate}
            disabled={generating}
            className="px-6 py-3 rounded-xl text-white text-base font-semibold bg-violet-600 hover:bg-violet-700 disabled:opacity-50 transition-colors shadow-[0_4px_14px_rgba(139,92,246,0.35)]"
          >
            {generating ? statusText : '🚀 生成分析报告'}
          </button>

          {generating && <p className="text-sm text-violet-600 animate-pulse">{statusText}</p>}
          {error && (
            <p className="text-sm text-rose-600 bg-rose-50 border border-rose-200 p-3 rounded-lg">{error}</p>
          )}

          {sections.length > 0 && (
            <div className="space-y-4">
              {sections.map((sec, i) => (
                <div key={i} className="glass-card p-5">
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">
                    {SECTION_ICON[sec.type] || '📄'} {sec.title}
                  </h3>
                  {sec.content && <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">{sec.content}</p>}
                  {sec.insights && (
                    <ul className="mt-2 space-y-1.5">
                      {sec.insights.map((ins, j) => (
                        <li key={j} className="text-sm text-slate-600 leading-relaxed">
                          {typeof ins === 'string' ? ins : (
                            <><strong className="text-slate-800">{ins.chart_title}</strong>：{ins.analysis}</>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

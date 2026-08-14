import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FileBarChart, AlertCircle, Clock, Tag, Copy } from 'lucide-react';
import { getSharedPackage } from '../lib/api';

const TYPE_LABELS: Record<string, string> = {
  chart: '图表分析',
  dashboard: '仪表盘',
  report: 'AI 报告',
  insight: '数据洞察',
  clean: '数据清洗',
  unknown: '分析包',
};

export default function SharedPage() {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<{
    share_id: string;
    package_id: string;
    created_at: number;
    expire_at: number | null;
    payload: Record<string, any> | null;
  } | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getSharedPackage(id)
      .then((d) => setData(d))
      .catch((err: any) => setError(err?.message || '加载失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const fmtTime = (t?: number) =>
    t ? new Date(t * 1000).toLocaleString('zh-CN', { hour12: false }) : '—';

  const payload = data?.payload;
  const title = payload?.title || payload?.custom_title || '未命名分析';
  const ptype = payload?.package_type || payload?.type || 'unknown';
  const desc = payload?.description || '';
  const expires = data?.expire_at ? fmtTime(data.expire_at) : '永久有效';

  return (
    <div
      className="min-h-screen w-full bg-cover bg-center flex items-start justify-center py-10 px-4"
      style={{ backgroundImage: "url('/auth-bg.jpg')" }}
    >
      <div className="absolute inset-0 bg-slate-900/55" />
      <div className="relative w-full max-w-3xl">
        <div className="glass-card rounded-3xl p-8 page-enter">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-violet-600 tracking-wide">
              DataMind AI · 公开分享
            </span>
          </div>

          {loading ? (
            <p className="text-slate-400 text-sm py-10 text-center">加载中…</p>
          ) : error ? (
            <div className="flex items-center gap-2 py-10 text-red-500 justify-center">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          ) : (
            <>
              <div className="flex items-start gap-3 mb-4">
                <div className="mt-1 p-2 rounded-xl bg-violet-100 text-violet-600">
                  <FileBarChart className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-bold text-slate-900 truncate">{title}</h1>
                  <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100">
                      <Tag className="w-3 h-3" />
                      {TYPE_LABELS[ptype] || ptype}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      分享于 {fmtTime(data?.created_at)}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      有效期：{expires}
                    </span>
                  </div>
                </div>
              </div>

              {desc && (
                <p className="text-sm text-slate-600 mb-4 leading-relaxed">{desc}</p>
              )}

              <details className="group">
                <summary className="cursor-pointer text-sm text-violet-500 hover:text-violet-700 select-none">
                  查看分析包原始数据
                </summary>
                <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-slate-900/90 text-slate-100 text-xs p-4 leading-relaxed">
                  {JSON.stringify(payload, null, 2)}
                </pre>
              </details>

              <div className="mt-6 pt-4 border-t border-slate-200/60 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  这是只读分享，数据由分享者生成
                </span>
                <div className="flex gap-2">
                  {payload && (
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard?.writeText(JSON.stringify(payload, null, 2));
                      }}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm text-slate-600 bg-white/70 hover:bg-white transition-colors"
                    >
                      <Copy className="w-4 h-4" />
                      复制数据
                    </button>
                  )}
                  <Link
                    to="/"
                    className="px-3 py-1.5 rounded-lg text-sm font-medium text-white bg-violet-600 hover:bg-violet-700 transition-colors"
                  >
                    去 DataMind 体验
                  </Link>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

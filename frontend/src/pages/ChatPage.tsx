/* DataMind AI - 聊天分析页（骨架 + 数据上传入口）
 * 仅走 Agnes，不提供模型选择。
 * 后端 /api/chat/send 用默认 DataAnalysisAgent（Agnes）对当前激活数据做单轮分析。
 * 预留 message.kind='choice' 渲染位（大脑方后续把工具 options 以选择框形式推回）。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Database, AlertTriangle, Upload, MessageSquare, Sparkles, Loader2 } from 'lucide-react';
import { useData } from '../contexts/DataContext';
import { uploadFile, listDatasets, chatSend } from '../api/client';
import type { DatasetInfo } from '../types/api';
import { formatBytes } from '../utils/format';
import { marked } from 'marked';
import EtherealChart from '../components/EtherealCharts/EtherealChart';
import ReportCard from '../components/ReportCard';
import BigScreenCard from '../components/BigScreenCard';

// 与 AnalysisPage / VisualizationRenderer 一致：后端 AI 输出为 Markdown（可信源），渲染成富文本
function renderMarkdown(text: string): string {
  return marked.parse(text || '') as string;
}

const QUOTA_DEFAULT = 30 * 1024 * 1024;
const ACCEPT = '.csv, .xlsx, .xls, .json, .sqlite, .db';

// 把 LLM 写的简单 chart 结构（{chart_type,x,y,data,title}）转成仙气组件认识的 chartNode
function adaptChartToNode(chart: any) {
  // 完整 ECharts option（generate_chart 产出，含 series 字段）→ 直接透传，不转换
  if (chart?.series && Array.isArray(chart.series)) {
    return chart;
  }
  // 以下为 LLM 简单格式兼容（execute_python 产出）
  const t = chart?.chart_type;
  if (t === 'bar' || t === 'line') {
    return { xAxis: { data: chart.x || [] }, series: [{ type: t, data: chart.y || [] }], title: chart.title };
  }
  if (t === 'pie') {
    return { series: [{ type: 'pie', data: (chart.data || []).map((d: any) => ({ name: d.维度, value: d.数值 })) }], title: chart.title };
  }
  if (t === 'ranking') {
    return { data: chart.data || [], title: chart.title };
  }
  if (t === 'table') {
    // EtherealTable 只读 node.rows + node.columns，不认 node.data
    return { rows: chart.data || [], columns: Object.keys((chart.data && chart.data[0]) || {}), title: chart.title };
  }
  return chart; // 其余类型透传兜底
}

// 单个工具执行结果行：图表/报告/大屏按工具类型内联渲染，不藏按钮后
function ToolResultRow({ tr }: { tr: ToolResult }) {
  const chart = tr.data?.chart;
  const isOk = tr.status === 'ok';

  // 报告 / 大屏：整块内联渲染（数据在 data.report / data.bigscreen，无 chart 字段）
  if (tr.tool === 'generate_report' && tr.data?.report) {
    return <ReportCard report={tr.data.report} />;
  }
  if (tr.tool === 'generate_bigscreen' && tr.data?.bigscreen) {
    return <BigScreenCard bigscreen={tr.data.bigscreen} />;
  }

  const badge = isOk ? 'bg-emerald-500/15 border border-emerald-400/40 text-emerald-700'
                     : 'bg-rose-500/15 border border-rose-400/40 text-rose-700';
  return (
    <div className={`text-xs rounded-lg px-2.5 py-1.5 ${badge}`}>
      <div className="flex items-start gap-2">
        <span className="font-medium shrink-0">{tr.tool}</span>
        <span className="opacity-80">{tr.summary || (isOk ? '执行成功' : '执行失败')}</span>
      </div>
      {chart && (
        <div className="mt-2">
          <EtherealChart chartType={chart.chart_type || chart.series?.[0]?.type || tr.data?.packages?.[0]?.type} chartNode={adaptChartToNode(chart)} />
        </div>
      )}
    </div>
  );
}

type Role = 'user' | 'assistant';
interface ChoiceOption {
  id: string;
  label: string;
  description?: string;
}
interface ToolResult {
  tool: string;
  status: string;
  summary?: string;
  data?: any;
}
interface DataPreview {
  rows?: number;
  columns?: string[];
  head?: Array<Record<string, any>>;
}
interface ChatMsg {
  role: Role;
  content: string;
  kind?: 'text' | 'choice';
  choices?: ChoiceOption[];        // kind='choice' 时的选择按钮
  toolResults?: ToolResult[];      // 本轮工具执行结果
  dataPreview?: DataPreview | null; // 清洗后数据预览
  /** 该条助手消息携带待选择的清洗方案时，用户是否已点选（避免重复点） */
  choiceResolved?: boolean;
  /** 请求进行中、尚未返回内容的占位态（渲染"AI 正在分析数据…"加载条） */
  pending?: boolean;
}

export default function ChatPage() {
  const { state, dispatch, ensureValidSession } = useData();
  const navigate = useNavigate();
  const { sessionId, datasets, usedBytes, quotaBytes } = state;
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const hasData = datasets.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 进入页面时同步一次数据集列表（与 UploadPage 一致）
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await listDatasets(sessionId);
        if (!alive) return;
        dispatch({ type: 'SET_DATASETS', datasets: res.datasets });
      } catch { /* 无数据忽略 */ }
    })();
    return () => { alive = false; };
  }, [sessionId, dispatch]);

  // 未上传数据时默认弹出上传入口
  useEffect(() => {
    if (!hasData) setShowUpload(true);
  }, [hasData]);

  const doUpload = useCallback(async (file: File) => {
    setUploadError(null);
    try {
      const res = await uploadFile(file, sessionId);
      const items = (res.datasets && res.datasets.length)
        ? res.datasets
        : [{
            dataset_id: res.dataset_id,
            file_name: res.file_name ?? file.name,
            rows: res.rows,
            columns: res.columns,
            memory_usage: res.memory_usage,
            total_missing: res.total_missing,
            duplicate_rows: res.duplicate_rows,
            preview: res.preview,
            column_info: res.column_info,
            column_names: (res.column_info?.map((c: any) => c.name)) ?? [],
          }];
      items.forEach((d: any, i: number) => {
        const ds: DatasetInfo = {
          dataset_id: d.dataset_id,
          file_name: d.file_name ?? file.name,
          file_size_bytes: i === 0 ? res.file_size_bytes : 0,
          rows: d.rows,
          columns: d.column_names ?? [],
          column_info: d.column_info,
          preview: d.preview,
          uploaded_at: Date.now(),
          is_active: i === 0,
        };
        dispatch({ type: 'ADD_DATASET', payload: ds });
      });
      const usedBytes = (res.datasets ?? []).reduce(
        (s: number, d: any, i: number) => s + (i === 0 ? (res.file_size_bytes ?? 0) : 0), 0,
      );
      dispatch({ type: 'SET_QUOTA', used: usedBytes, quota: quotaBytes ?? QUOTA_DEFAULT });
      setShowUpload(false);
    } catch (e: any) {
      setUploadError(e?.response?.data?.detail || e?.message || '上传失败');
    }
  }, [sessionId, dispatch, quotaBytes]);

  const onPickFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) doUpload(f);
    e.target.value = '';
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) doUpload(f);
  };

  const send = useCallback(async (choiceId?: string) => {
  // 防御：choiceId 必须是字符串，否则（如对象/undefined 经异常路径传入）
  // 会被 String() 成 "[object Object]" 发给后端导致误执行清洗。非字符串一律视为无选择。
  if (typeof choiceId !== 'string') choiceId = '';
  // choiceId 非空：复用上一条助手消息的原文作为提问，回传用户选择
  const safeChoiceId = choiceId ? String(choiceId) : '';
  const text = safeChoiceId ? '' : input.trim();
  // 上一轮请求还在跑：静默忽略会让用户困惑（文字卡在框里），给出轻量提示后返回
  if (!safeChoiceId && sending) {
    setMessages((m) => [...m, {
      role: 'assistant',
      content: '⏳ 上一轮分析还在进行中，请稍候再发消息。',
      pending: false,
    }]);
    return;
  }
  if (!safeChoiceId && !text) return;
  if (!hasData) { setShowUpload(true); return; }

  if (!safeChoiceId) setInput('');
  setSending(true);

    // 用户点选方案 → 先把该选择作为一条 user 消息展示
    if (safeChoiceId) {
      setMessages((m) => [...m, { role: 'user', content: `▶ 选择：${safeChoiceId}` }]);
    } else {
      setMessages((m) => [...m, { role: 'user', content: text }]);
    }

    // 先推一条 pending 占位助手消息，渲染"AI 正在分析数据…"加载条
    setMessages((m) => [...m, { role: 'assistant', content: '', pending: true }]);

    const replaceLast = (msg: ChatMsg) =>
      setMessages((m) => m.map((x, idx) => (idx === m.length - 1 ? msg : x)));

    try {
      const r = await chatSend(sessionId, safeChoiceId ? '' : text, safeChoiceId);
      replaceLast({
        role: 'assistant',
        content: r.content ?? '（无回复）',
        kind: r.kind,
        choices: r.choices ?? [],
        toolResults: r.tool_results ?? [],
        dataPreview: r.data_preview ?? null,
      });
    } catch (e: any) {
      const err = e?.response?.data?.detail || e?.message || 'AI 调用失败';
      replaceLast({ role: 'assistant', content: `⚠️ ${err}` });
    } finally {
      setSending(false);
    }
  }, [input, sending, hasData, sessionId]);

  // 用户点击清洗方案按钮
  const onChoose = useCallback((choiceId: string, msgIndex: number) => {
    // 防御：choiceId 非字符串则直接忽略，绝不把对象传入 send（避免 [object Object]）
    if (typeof choiceId !== 'string') return;
    // 标记该条助手消息已解决，避免重复点
    setMessages((m) => m.map((msg, i) =>
      i === msgIndex ? { ...msg, choiceResolved: true } : msg));
    send(choiceId);
  }, [send]);

  return (
    <div className="relative h-screen">
      <div className="bg-layer" />
      <div className="relative z-10 h-full flex flex-col bg-transparent text-slate-800">
      {/* 顶栏 */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-white/40">
        <Sparkles className="w-5 h-5 text-violet-500" />
        <h1 className="text-lg font-semibold text-slate-800">DataMind AI 对话分析</h1>
        <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-700 border border-violet-400/40">
          模型：Agnes
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <Database className="w-4 h-4" />
          {hasData
            ? <span>{datasets[0].file_name} · {datasets[0].rows} 行</span>
            : <button className="text-violet-600 hover:underline" onClick={() => setShowUpload(true)}>上传数据</button>}
        </div>
      </header>

      {/* 消息区 */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 gap-3">
            <MessageSquare className="w-12 h-12 text-violet-400/70" />
            <p className="max-w-md text-slate-600">上传数据后，直接问我关于这份数据的问题，例如「有哪些列缺失？」「帮我做个趋势分析」。</p>
            {!hasData && (
              <button onClick={() => setShowUpload(true)} className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-500/15 border border-violet-400/40 text-violet-700 hover:bg-violet-500/25">
                <Upload className="w-4 h-4" /> 上传数据
              </button>
            )}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-violet-500/15 border border-violet-400/40 text-slate-800 whitespace-pre-wrap'
                : 'bg-white/60 border border-white/70 text-slate-800 backdrop-blur-sm'
            }`}>
              {m.pending ? (
                <div className="flex items-center gap-2 text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin text-violet-500" />
                  <span>AI 正在分析数据…</span>
                </div>
              ) : m.role === 'user' ? (
                m.content
              ) : (
                <div className="md-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
              )}

              {/* 工具执行结果（含图表/报告/大屏时默认展开，不遮挡内容） */}
              {m.toolResults && m.toolResults.length > 0 && (() => {
                const hasVisual = m.toolResults.some(
                  (tr: ToolResult) => tr.data?.chart || tr.data?.report || tr.data?.bigscreen,
                );
                return (
                <details className="mt-3 group" open={hasVisual}>
                  <summary className="cursor-pointer select-none text-xs text-slate-500 hover:text-violet-600 flex items-center gap-1.5">
                    <span className="text-emerald-500">✓</span>
                    已分析 · 点开看执行过程
                  </summary>
                  <div className="mt-2 space-y-1.5">
                    {m.toolResults.filter((tr) => tr.status !== 'fail').map((tr, ti) => (
                      <ToolResultRow key={ti} tr={tr} />
                    ))}
                  </div>
                </details>
                );
              })()}

              {/* 清洗后数据预览 */}
              {m.dataPreview && m.dataPreview.head && m.dataPreview.head.length > 0 && (
                <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200/60">
                  <table className="text-xs">
                    <thead>
                      <tr className="bg-white/70">
                        {(m.dataPreview.columns || Object.keys(m.dataPreview.head[0])).map((c) => (
                          <th key={c} className="px-2.5 py-1.5 text-left font-medium text-slate-700 whitespace-nowrap">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {m.dataPreview.head.map((row, ri) => (
                        <tr key={ri} className="border-t border-slate-200/50">
                          {(m.dataPreview.columns || Object.keys(row)).map((c) => (
                            <td key={c} className="px-2.5 py-1.5 text-slate-600 whitespace-nowrap">{String(row[c] ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 清洗方案选择按钮 */}
              {m.choices && m.choices.length > 0 && !m.choiceResolved && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {m.choices.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => onChoose(c.id, i)}
                      disabled={sending}
                      className="text-left px-3 py-2 rounded-xl bg-violet-500/15 border border-violet-400/50 text-violet-700 hover:bg-violet-500/25 disabled:opacity-50 transition-colors"
                    >
                      <div className="text-sm font-medium">{c.label}</div>
                      {c.description && <div className="text-xs text-violet-600/70 mt-0.5">{c.description}</div>}
                    </button>
                  ))}
                </div>
              )}
              {m.choices && m.choices.length > 0 && m.choiceResolved && (
                <div className="mt-3 text-xs text-emerald-600">✓ 已执行清洗，等待结果…</div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="px-6 py-4 border-t border-white/40">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            rows={2}
            placeholder={hasData ? '输入你的问题，回车发送…' : '请先上传数据后再提问'}
            className="flex-1 resize-none rounded-xl bg-white/60 border border-slate-300/60 px-4 py-3 text-sm text-slate-800 outline-none focus:border-violet-400/60"
          />
          <button
            onClick={send}
            disabled={sending || !hasData}
            className="px-5 py-3 rounded-xl bg-violet-500/80 border border-violet-500 text-white hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-2"
          >
            <Send className="w-4 h-4" /> {sending ? '思考中…' : '发送'}
          </button>
        </div>
        {!hasData && (
          <p className="mt-2 text-xs text-amber-600 inline-flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> 当前会话没有数据，请先上传。
          </p>
        )}
      </div>

      {/* 上传入口弹窗 */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm" onClick={() => hasData && setShowUpload(false)}>
          <div
            className={`glass-card w-[520px] max-w-[92vw] rounded-2xl p-6 ${dragging ? 'ring-2 ring-violet-400' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-4">
              <Upload className="w-5 h-5 text-violet-500" />
              <h2 className="text-base font-semibold text-slate-800">上传数据</h2>
              {hasData && (
                <button className="ml-auto text-slate-500 hover:text-slate-700" onClick={() => setShowUpload(false)}>关闭</button>
              )}
            </div>
            <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 hover:border-violet-400 px-6 py-10 text-center text-slate-500 transition">
              <Upload className="w-8 h-8 mx-auto mb-2 text-violet-400/70" />
              <p>点击或拖拽文件到此处</p>
              <p className="text-xs mt-1 text-slate-400">支持 {ACCEPT}</p>
              <input type="file" accept={ACCEPT} className="hidden" onChange={onPickFile} />
            </label>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span>已用 {formatBytes(usedBytes || 0)} / {formatBytes(quotaBytes || QUOTA_DEFAULT)}</span>
              <button className="text-violet-600 hover:underline" onClick={() => navigate('/')}>前往完整上传页</button>
            </div>
            {uploadError && (
              <p className="mt-3 text-xs text-rose-600 inline-flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> {uploadError}
              </p>
            )}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

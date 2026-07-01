/* AnalysisPage - 分析与可视化 */
import React, { useState, useEffect, useCallback } from 'react';
import { FiBarChart2, FiMessageSquare, FiTrendingUp, FiZap, FiPlus, FiSave, FiFileText } from 'react-icons/fi';
import EChartView, { EChartsOption } from '../components/EChartView';
import DataTable from '../components/DataTable';
import TbHbTable, { type TbHbRow } from '../components/TbHbTable';
import KPICards, { type KPIItem } from '../components/KPICards';
import VisualizationRenderer from '../components/VisualizationRenderer';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import { marked } from 'marked';

// 安全的 markdown 渲染
function renderMarkdown(text: string): string {
  return marked.parse(text) as string;
}

// 从 ECharts option 中提取标题文字（title 可能是对象 {text: "xxx"} 或纯字符串）
function getOptionTitle(option: Record<string, unknown> | undefined, fallback = '同环比趋势'): string {
  if (!option) return fallback;
  const title = option.title;
  if (typeof title === 'object' && title !== null) {
    return (title as Record<string, unknown>).text as string || fallback;
  }
  return String(title || fallback);
}

type Tab = 'stats' | 'charts' | 'chat';

export default function AnalysisPage() {
  const { state: ds, dispatch: dd } = useData();
  const a = ds.analysis;

  const setAnalysis = (payload: Partial<typeof a>) => dd({ type: 'SET_ANALYSIS', payload });

  const [chatInput, setChatInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [computeQuery, setComputeQuery] = useState('');
  const [computing, setComputing] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [chartInfo, setChartInfo] = useState<{ title: string; option: Record<string, unknown> } | null>(null);
  const [chartSuggestions, setChartSuggestions] = useState<Array<{ type: string; x: string; y: string; title: string }>>([]);
  const [intents, setIntents] = useState<Array<{
    business_question: string; analysis_goal: string; priority: string; reason: string; checked: boolean;
  }>>([]);
  const [analysisPackages, setAnalysisPackages] = useState<Array<Record<string, unknown>>>([]);
  const [selectedPkgIndex, setSelectedPkgIndex] = useState(0);
  const [analysisKpis, setAnalysisKpis] = useState<KPIItem[]>([]);
  const [tbHbData, setTbHbData] = useState<{
    rows: TbHbRow[];
    value_column: string;
    current_year: string;
    previous_year: string | null;
    has_yoy: boolean;
    chart_option?: Record<string, unknown>;
  } | null>(null);

  const hasData = ds.rows > 0;

  // 从 context 获取持久化的 tab
  const tab = a.tab;
  const setTab = (t: Tab) => setAnalysis({ tab: t });

  // 切换到智能绘图 tab 时自动获取 KPI
  useEffect(() => {
    if (tab === 'charts' && hasData && ds.sessionId) {
      api.getDashboardKPIs(ds.sessionId).then(res => {
        if (res.kpis) setAnalysisKpis(res.kpis);
      }).catch(() => {});
    }
  }, [tab, hasData, ds.sessionId]);

  const statsData = a.stats;
  const setStatsData = (s: Record<string, unknown>[] | null) => setAnalysis({ stats: s });
  const heatmapFigure = a.heatmap;
  const setHeatmapFigure = (h: EChartsOption | null) => setAnalysis({ heatmap: h });
  const chartFigure = a.chartFigure;
  const setChartFigure = (c: EChartsOption | null) => setAnalysis({ chartFigure: c });
  const chartType = a.chartType;
  const setChartType = (t: string) => setAnalysis({ chartType: t });
  const chartX = a.chartX;
  const setChartX = (x: string) => setAnalysis({ chartX: x });
  const chartY = a.chartY;
  const setChartY = (y: string) => setAnalysis({ chartY: y });
  const chatHistory = a.chatHistory;
  const setChatHistory = (h: { role: string; content: string }[] | ((prev: { role: string; content: string }[]) => { role: string; content: string }[])) => {
    const next = typeof h === 'function' ? h(a.chatHistory) : h;
    setAnalysis({ chatHistory: next });
  };
  const insights = a.insights;
  const setInsights = (s: string) => setAnalysis({ insights: s });
  const quickInsights = a.quickInsights;
  const setQuickInsights = (q: string[]) => setAnalysis({ quickInsights: q });
  const computeResult = a.computeResult;
  const setComputeResult = (r: string | ((prev: string) => string)) => {
    const next = typeof r === 'function' ? r(a.computeResult) : r;
    setAnalysis({ computeResult: next });
  };
  const savedCount = a.savedCount;
  const setSavedCount = (n: number) => setAnalysis({ savedCount: n });

  const [columns, setColumns] = useState<string[]>(ds.columnInfo.map((c) => c.name));
  const [numericColumns, setNumericColumns] = useState<string[]>(
    ds.columnInfo.filter((c) => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map((c) => c.name)
  );

  // 监听列更新事件（AI 计算后触发）
  useEffect(() => {
    const handler = async () => {
      try {
        const res = await api.getColumnInfo(ds.sessionId);
        if (res.columns) {
          const allCols = res.columns.map((c: Record<string, unknown>) => String(c.name ?? ''));
          const numCols = res.columns
            .filter((c: Record<string, unknown>) => ['float64', 'int64', 'int32', 'float32'].includes(String(c.dtype ?? '')))
            .map((c: Record<string, unknown>) => String(c.name ?? ''));
          setColumns(allCols);
          setNumericColumns(numCols);
        }
      } catch { /* ignore */ }
    };
    window.addEventListener('columns-updated', handler);
    return () => window.removeEventListener('columns-updated', handler);
  }, [ds.sessionId]);

  // 组件挂载或 columnInfo 变化时同步列下拉框
  useEffect(() => {
    if (ds.columnInfo.length > 0) {
      setColumns(ds.columnInfo.map((c) => c.name));
      setNumericColumns(
        ds.columnInfo.filter((c) => ['float64', 'int64', 'int32', 'float32'].includes(c.dtype)).map((c) => c.name)
      );
    }
  }, [ds.columnInfo]);

  const loadStats = useCallback(async () => {
    if (!hasData) return;
    setLoading(true);
    try {
      const res = await api.getDescriptiveStats(ds.sessionId);
      if (res.stats && Array.isArray(res.stats)) {
        setStatsData(res.stats);
      } else if (res.stats && typeof res.stats === 'object') {
        const rows = Object.entries(res.stats).map(([key, val]) => ({
          列名: key,
          ...(val as Record<string, unknown>),
        }));
        setStatsData(rows);
      }
      const heatRes = await api.createEChart(ds.sessionId, { chart_type: 'heatmap', x: '', y: '' });
      if (heatRes.option) setHeatmapFigure(heatRes.option);
    } catch (err) {
      console.error('加载统计失败', err);
    } finally {
      setLoading(false);
    }
  }, [hasData, ds.sessionId]);

  // 页面加载时自动获取快速概览（无需 AI）
  useEffect(() => {
    if (hasData && quickInsights.length === 0) {
      api.getQuickInsights(ds.sessionId).then((res) => {
        if (res.insights) setQuickInsights(res.insights);
      }).catch(() => {});
    }
  }, [hasData, ds.sessionId, quickInsights.length]);

  useEffect(() => {
    if (tab === 'stats') loadStats();
  }, [tab, loadStats]);

  const CHART_TYPES = ['bar','stacked_bar','line','area','scatter','bubble','pie','histogram','box','heatmap','radar','waterfall','treemap','wordcloud','gl_map'];


  const generateChart = async (overrides?: { type?: string; x?: string; y?: string }) => {
    // ★ 防止事件对象传入（如 onClick={generateChart} 会传入 SyntheticEvent，type="click"）
    const overrideType = overrides?.type;
    const type = (overrideType && CHART_TYPES.includes(overrideType)) ? overrideType : chartType;
    const x = overrides?.x || chartX;
    const y = overrides?.y !== undefined ? overrides.y : (chartY || undefined);

    // ★ 表格类型：调用同环比接口获取结构化数据 + 折线图
    if (type === 'table') {
      setLoading(true);
      try {
        // ★ 关键：value_column 必须是真正的数值列（y 可能为空，x 可能是日期列）
        const trueValueCol = numericColumns.find(c => /金额|收入|数量|利润|成本/.test(c))
          || numericColumns[0] || '';
        // date_column 用 x（如果 x 看起来是日期列），否则默认 '日期'
        const dateCol = /日期|时间|月份|年份/.test(x) ? x : '日期';
        if (!trueValueCol) { setLoading(false); return; }
        const res = await api.getTongHuanBi(ds.sessionId, trueValueCol, dateCol);
        if (res.success) {
          setTbHbData({
            rows: res.rows,
            value_column: res.value_column,
            current_year: res.current_year,
            previous_year: res.previous_year,
            has_yoy: res.has_yoy,
            chart_option: res.chart_option,
          });
          // 用后端返回的折线图 option 设置 chartFigure
          if (res.chart_option) {
            setChartFigure(res.chart_option as EChartsOption);
            setChartInfo({
              title: getOptionTitle(res.chart_option as Record<string, unknown>),
              option: res.chart_option,
            });
          } else {
            setChartFigure(null);
            setChartInfo(null);
          }
        }
      } catch { /* ignore */ }
      setLoading(false);
      return;
    }

    // gl_map 允许空 x（后端自动选择地区列）；其他图表必须选 X 轴
    if (type !== 'gl_map' && !x) return;
    setLoading(true);
    setSaveMsg('');
    try {
      const res = await api.createEChart(ds.sessionId, {
        chart_type: type,
        x,
        y,
      });
      if (res.option) {
        setChartFigure(res.option);
        const title = y ? `${x} vs ${y}` : `${x} - ${type}`;
        setChartInfo({ title, option: res.option });
      }
    } catch (err) {
      console.error('图表生成失败', err);
      const errMsg = err instanceof Error ? err.message : '图表生成失败';
      alert(`图表生成失败: ${errMsg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveChart = async () => {
    if (!chartInfo) return;
    try {
      // ★ 如果是同环比表格类型，把表格数据也一起保存
      const isTable = chartType === 'table';
      const tablePayload = isTable && tbHbData ? {
        rows: tbHbData.rows,
        value_column: tbHbData.value_column,
        current_year: tbHbData.current_year,
        previous_year: tbHbData.previous_year,
        has_yoy: tbHbData.has_yoy,
      } : null;
      const res = await api.saveChart(
        ds.sessionId,
        chartInfo.title,
        chartInfo.option,
        isTable ? 'table' : '',
        tablePayload as Record<string, unknown> | null,
      );
      setSavedCount(res.total);
      setSaveMsg(`✅ ${res.message}`);
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (err) {
      setSaveMsg('❌ 保存失败');
    }
  };

  const handleGenerateReport = async () => {
    if (!ds.sessionId || !ds.apiKey) {
      alert('请先在左上角配置 AI API Key');
      return;
    }
    setLoading(true);
    try {
      const saved = await api.getSavedCharts(ds.sessionId);
      const chartCount = saved.total;
      const reportPrompt = chartCount > 0
        ? `请基于以下 ${chartCount} 个已保存的分析图表，生成一份专业的数据分析报告。报告应包含：1）数据概览 2）关键发现 3）图表解读 4）结论与建议。图表数据：${JSON.stringify(saved.charts.map(c => c.title))}`
        : '请基于当前数据生成一份数据分析报告，包含数据概览、关键发现和结论建议。';
      
      const provider = AI_PROVIDERS.find(p => p.id === ds.aiProvider);
      if (!provider) { alert('请先在左上角选择 AI 模型提供商'); setLoading(false); return; }
      const res = await api.chatAnalyze(ds.sessionId, reportPrompt, ds.apiKey, provider.baseUrl, provider.model);
      if (res.answer) {
        setInsights(res.answer);
        setTab('chat');
      }
    } catch (err) {
      console.error('报告生成失败', err);
      alert('报告生成失败');
    } finally {
      setLoading(false);
    }
  };

  const getProviderConfig = () => AI_PROVIDERS.find((p) => p.id === ds.aiProvider);

  const handleCompute = async (autoQuery?: string) => {
    const query = autoQuery || computeQuery.trim();
    if (!query || !ds.apiKey) { setComputeResult('⚠️ 请先配置 API Key 并输入计算需求'); return; }
    setComputing(true);
    setComputeResult('');
    try {
      const provider = getProviderConfig();
      const res = await api.computeData(ds.sessionId, query, ds.apiKey, provider?.baseUrl, provider?.model);
      setComputeResult(`✅ ${res.message}`);
      // 自动刷新列列表
      window.dispatchEvent(new Event('columns-updated'));

      // ★ 如果用户在同环比，自动调用同环比接口展示规范表格 + 折线图
      if (['同比', '环比'].some(kw => query.includes(kw))) {
        try {
          // 从新增列中提取数值列名（如"销售金额"）
          const newCols: string[] = res.new_columns || [];
          const rateCol = newCols.find(c => c.includes('同比') || c.includes('环比'));
          const baseCol = rateCol ? rateCol.replace(/[_-]*(同比|增长率|环比|变化率).*$/, '').replace('_', '') : '';
          // 从原始列中找到匹配的数值列
          const colTypesRes = await api.getColumnTypes(ds.sessionId);
          const numCols: string[] = colTypesRes.numeric_columns || [];
          // 优先匹配包含"金额"、"数量"、"利润"等的列
          const valueCol = numCols.find(c => /金额|收入|数量|利润|成本/.test(c)) || baseCol || numCols[0];
          if (valueCol) {
            const tbRes = await api.getTongHuanBi(ds.sessionId, valueCol, '日期');
            if (tbRes.success) {
              setTbHbData({
                rows: tbRes.rows,
                value_column: tbRes.value_column,
                current_year: tbRes.current_year,
                previous_year: tbRes.previous_year,
                has_yoy: tbRes.has_yoy,
                chart_option: tbRes.chart_option,
              });
              setChartType('table');
              setChartX(valueCol);
              setChartY('');
              // 同时设置折线图
              if (tbRes.chart_option) {
                setChartFigure(tbRes.chart_option as EChartsOption);
                setChartInfo({
                  title: getOptionTitle(tbRes.chart_option as Record<string, unknown>),
                  option: tbRes.chart_option,
                });
              }
              setTab('charts');
              setComputeResult((prev) => prev + `\n📋 已生成同环比规范表格 + 趋势图`);
            }
          }
        } catch { /* ignore */ }
      }

      return res;
    } catch (err) {
      setComputeResult(`❌ ${err instanceof Error ? err.message : '计算失败'}`);
      return null;
    } finally {
      setComputing(false);
    }
  };

  /** V2：一键应用洞察 → 读取 intents[] → 调 /analysis/run → 展示 packages */
  const handleApplyInsights = async (sourceText?: string) => {
    if (!ds.apiKey) {
      alert('请先在左上角配置 AI API Key');
      return;
    }

    try {
      setComputing(true);
      setComputeResult('⏳ 正在调用 AI 生成洞察...');

      const provider = getProviderConfig();
      const res = await api.generateInsights(ds.sessionId, ds.apiKey, provider?.baseUrl, provider?.model);

      if (!res.success || !res.intents || res.intents.length === 0) {
        alert('AI 未返回分析计划，请重试');
        setComputing(false);
        return;
      }

      setIntents(res.intents);
      setComputeResult(`✅ 获取到 ${res.intents.length} 个分析问题，请勾选后点击「执行分析」`);
      setComputing(false);
    } catch (err) {
      setComputeResult(`❌ 失败: ${err instanceof Error ? err.message : '未知错误'}`);
      setComputing(false);
    }
  };

  /** V2：执行选中的分析计划 → 调 /analysis/run */
  const handleRunAnalysis = async () => {
    const selected = intents.filter(i => i.checked);
    if (selected.length === 0) {
      alert('请至少勾选一个分析问题');
      return;
    }
    try {
      setComputing(true);
      setComputeResult('⏳ 正在执行分析...');
      const res = await api.runAnalysis(ds.sessionId, selected);
      if (res.packages) {
        setAnalysisPackages(res.packages);
        setSelectedPkgIndex(0);
        setComputeResult(`✅ 完成 ${res.packages.length} 个分析`);
      }
      if (res.packages && res.packages.length > 0) {
        const first = res.packages[0];
        if (first.charts && first.charts.length > 0) {
          const c = first.charts[0];
          setChartFigure(c.option);
          setChartInfo({ title: c.title, option: c.option });
        }
      }
      setTab('charts');
    } catch (err) {
      setComputeResult(`❌ 分析失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setComputing(false);
    }
  };

  /** V2：保存选中的分析包到 Dashboard */
  const handleSavePackages = async (pkgIds: string[]) => {
    try {
      const res = await api.saveAnalysis(ds.sessionId, pkgIds);
      alert(`已保存 ${res.saved_count} 个分析结果到仪表盘`);
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const generateInsights = async () => {
    if (!ds.apiKey) { alert('请先在左上角配置 AI API Key'); return; }
    setLoading(true);
    try {
      const provider = getProviderConfig();
      const res = await api.generateInsights(ds.sessionId, ds.apiKey, provider?.baseUrl, provider?.model);
      setInsights(res.insights);
    } catch (err) {
      setChatHistory((prev) => [...prev, { role: 'ai', content: `❌ ${err instanceof Error ? err.message : '洞察生成失败'}` }]);
    } finally {
      setLoading(false);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim() || !ds.apiKey) return;
    const question = chatInput.trim();
    setChatInput('');
    setChatHistory((prev) => [...prev, { role: 'user', content: question }]);
    setLoading(true);
    try {
      const provider = getProviderConfig();
      const res = await api.chatAnalyze(ds.sessionId, question, ds.apiKey, provider?.baseUrl, provider?.model);
      setChatHistory((prev) => [...prev, { role: 'ai', content: res.answer }]);
    } catch (err) {
      setChatHistory((prev) => [...prev, { role: 'ai', content: `❌ ${err instanceof Error ? err.message : '请求失败'}` }]);
    } finally {
      setLoading(false);
    }
  };

  if (!hasData) {
    return (
      <div className="page-enter">
        <h1 className="text-2xl font-bold text-[#f8fafc] mb-4"
          style={{ textShadow: '0 0 15px rgba(139,92,246,0.3)' }}
        >
          分析可视化
        </h1>
        <div className="glass-card p-8 text-center text-slate-500">
          请先在「数据上传」页面上传数据
        </div>
      </div>
    );
  }

  const inputClass = "w-full px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8b5cf6]/50 transition-colors";
  const btnClass = "px-4 py-2 text-sm rounded-lg bg-[#8b5cf6]/80 text-white hover:bg-[#8b5cf6] disabled:opacity-50 transition-colors";
  const btnFullClass = "w-full px-4 py-2 text-sm rounded-lg bg-[#8b5cf6]/80 text-white hover:bg-[#8b5cf6] disabled:opacity-50 transition-colors";

  return (
    <div className="page-enter space-y-6">
      <h1 className="text-2xl font-bold text-[#f8fafc]"
        style={{ textShadow: '0 0 15px rgba(139,92,246,0.3)' }}
      >
        分析可视化
      </h1>

      {/* Tab 导航 */}
      <div className="flex gap-1 border-b border-white/[0.06]">
        {[
          { id: 'stats' as Tab, label: '统计分析', icon: FiTrendingUp },
          { id: 'charts' as Tab, label: '智能绘图', icon: FiBarChart2 },
          { id: 'chat' as Tab, label: 'AI 对话', icon: FiMessageSquare },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-all border-b-2 ${
              tab === id
                ? 'text-[#f8fafc] border-[#8b5cf6]'
                : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      {tab === 'stats' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-[#f8fafc] mb-3">描述性统计</h2>
            {statsData ? (
              <DataTable data={statsData} />
            ) : (
              <div className="glass-card p-6 text-center text-slate-500">
                {loading ? '加载中...' : '暂无数据'}
              </div>
            )}
          </div>

          {heatmapFigure && (
            <div>
              <h2 className="text-lg font-semibold text-[#f8fafc] mb-3">相关性热力图</h2>
              <EChartView option={heatmapFigure} height={500} />
            </div>
          )}

          {/* 快速概览（无需 AI，自动生成） */}
          {quickInsights.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-[#f8fafc] mb-3">📋 快速概览</h2>
              <div className="glass-card p-4">
                <ul className="space-y-1.5">
                  {quickInsights.map((item, i) => (
                    <li key={i} className="text-sm text-slate-300">{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-[#f8fafc]">
                🤖 AI 深度洞察
                {!ds.apiKey && <span className="ml-2 text-xs text-slate-500 font-normal">（需配置 API Key）</span>}
              </h2>
              <button onClick={generateInsights} disabled={loading} className={btnClass}>
                {loading ? '分析中...' : '生成洞察'}
              </button>
            </div>
            {!ds.apiKey && (
              <div className="glass-card p-4 text-sm text-slate-500">
                💡 在左侧边栏选择 AI 模型并输入 API Key 后，可使用 AI 对数据进行深度分析。
              </div>
            )}
            {insights && !insights.startsWith('⚠️') && (
              <div className="glass-card p-4 space-y-3">
                <div 
                  className="text-sm text-slate-300 leading-relaxed prose-a:text-[#8b5cf6] prose-strong:text-[#f8fafc] max-h-80 overflow-y-auto pr-2"
                  style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(139,92,246,0.3) transparent' }}
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(insights) }}
                />
                <div className="flex items-center gap-3 pt-2 border-t border-white/[0.06]">



                  <button
                    onClick={() => handleApplyInsights()}
                    disabled={loading || computing}
                    className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-gradient-to-r from-[#22d3ee]/20 to-[#a78bfa]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:from-[#22d3ee]/30 hover:to-[#a78bfa]/30 disabled:opacity-50 transition-all"
                  >
                    <FiZap className="w-4 h-4" />
                    {computing ? '正在生成分析计划...' : '🚀 一键生成分析计划'}
                  </button>
                  <span className="text-xs text-slate-500">AI 自动分析数据 → 生成分析计划 → 勾选后执行</span>
                </div>
              </div>
            )}
            {/* V2：分析计划勾选列表 */}
            {intents.length > 0 && (
              <div className="glass-card p-4 space-y-3">
                <h3 className="text-sm font-semibold text-slate-300">📋 分析计划（勾选要执行的项目）</h3>
                <div className="space-y-2">
                  {intents.map((item, i) => (
                    <label key={i} className="flex items-start gap-3 p-2 rounded hover:bg-white/[0.03] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={item.checked}
                        onChange={() => {
                          const next = [...intents];
                          next[i] = { ...next[i], checked: !next[i].checked };
                          setIntents(next);
                        }}
                        className="mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-slate-200 font-medium">{item.business_question}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{item.analysis_goal} · {item.reason}</p>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        item.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                        item.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-slate-500/20 text-slate-400'
                      }`}>{item.priority}</span>
                    </label>
                  ))}
                </div>
                <div className="flex gap-2 pt-2 border-t border-white/[0.06]">
                  <button
                    onClick={() => {
                      setIntents(intents.map(i => ({ ...i, checked: true })));
                    }}
                    className="px-3 py-1.5 text-xs rounded bg-white/[0.05] text-slate-400 hover:text-white"
                  >全选</button>
                  <button
                    onClick={() => setIntents(intents.map(i => ({ ...i, checked: false })))}
                    className="px-3 py-1.5 text-xs rounded bg-white/[0.05] text-slate-400 hover:text-white"
                  >取消全选</button>
                  <button
                    onClick={handleRunAnalysis}
                    disabled={computing || !intents.some(i => i.checked)}
                    className="ml-auto flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-gradient-to-r from-[#8b5cf6]/80 to-[#a78bfa]/80 text-white hover:from-[#8b5cf6] hover:to-[#a78bfa] disabled:opacity-30 transition-all"
                  >
                    <FiTrendingUp className="w-3.5 h-3.5" />
                    {computing ? '执行中...' : '⚡ 执行分析'}
                  </button>
                </div>
                {computeResult && (
                  <div className="text-xs text-slate-400 whitespace-pre-wrap mt-1">{computeResult}</div>
                )}
              </div>
            )}
            {/* V2：分析结果 */}
            {analysisPackages.length > 0 && (
              <div className="glass-card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-300">📊 分析结果（{analysisPackages.length} 项）</h3>
                  <button
                    onClick={() => {
                      const ids = analysisPackages.filter(p => p.id).map(p => p.id as string);
                      if (ids.length > 0) handleSavePackages(ids);
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30 transition-all"
                  >
                    <FiSave className="w-3.5 h-3.5" />
                    保存到仪表盘
                  </button>
                </div>
                <VisualizationRenderer packages={analysisPackages as unknown as import('../types/api').AnalysisPackage[]} />
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'charts' && (
        <>
          {/* ===== V2 布局：有分析包时显示三栏 ===== */}
          {analysisPackages.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              <div className="lg:col-span-1 space-y-3">
                <div className="glass-card p-3">
                  <h3 className="text-xs font-semibold text-slate-400 mb-2">📋 分析问题列表</h3>
                  {analysisPackages.map((pkg, i) => (
                    <button key={i}
                      onClick={() => {
                        setSelectedPkgIndex(i);
                        const charts = pkg.charts as Array<Record<string, unknown>> | undefined;
                        if (charts && charts.length > 0) {
                          setChartFigure(charts[0].option as EChartsOption);
                          setChartInfo({title:charts[0].title as string, option:charts[0].option as Record<string, unknown>});
                        }
                      }}
                      className={`w-full text-left px-3 py-2 text-xs rounded mb-1 transition-all duration-200 ${
                        i===selectedPkgIndex ? 'bg-[#22d3ee]/10 border border-[#22d3ee]/20 text-[#22d3ee]' : 'bg-white/[0.03] text-slate-400 hover:text-white'
                      }`}>
                      <span className="block truncate">{pkg.business_question as string}</span>
                      <span className="text-[10px] text-slate-500">{pkg.analysis_type as string}</span>
                    </button>
                  ))}
                </div>
                <button onClick={() => {
                    const ids = analysisPackages.filter(p=>p.id).map(p=>p.id as string);
                    if (ids.length>0) handleSavePackages(ids);
                  }}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30">
                  <FiSave className="w-3.5 h-3.5"/>保存到仪表盘
                </button>
              </div>
              <div className="lg:col-span-3">
                <VisualizationRenderer
                  packages={analysisPackages as any}
                  selectedPackageIndex={selectedPkgIndex}
                />
              </div>
            </div>
          ) : (
            /* 旧版：手工图表配置 */
            <>
              {analysisKpis.length > 0 && <KPICards kpis={analysisKpis}/>}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-1 space-y-4">
                  <div className="glass-card p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-slate-300">图表配置</h3>
                    <div className="space-y-3">
                      <div><label className="text-xs text-slate-500 block mb-1">图表类型</label>
                        <select value={chartType} onChange={(e)=>setChartType(e.target.value)} className={inputClass}>
                          <option value="bar">柱状图</option><option value="line">折线图</option>
                          <option value="pie">饼图</option><option value="scatter">散点图</option>
                          <option value="area">面积图</option><option value="heatmap">热力图</option>
                          <option value="box">箱线图</option>
                        </select></div>
                      <div><label className="text-xs text-slate-500 block mb-1">X 轴</label>
                        <select value={chartX} onChange={(e)=>setChartX(e.target.value)} className={inputClass}>
                          <option value="">选择列...</option>
                          {columns.map(c=><option key={c} value={c}>{c}</option>)}
                        </select></div>
                      <div><label className="text-xs text-slate-500 block mb-1">Y 轴（可选）</label>
                        <select value={chartY} onChange={(e)=>setChartY(e.target.value)} className={inputClass}>
                          <option value="">选择列...</option>
                          {numericColumns.map(c=><option key={c} value={c}>{c}</option>)}
                        </select></div>
                      <button onClick={()=>generateChart()} disabled={loading||!chartX} className={btnFullClass}>
                        {loading?'生成中...':'生成图表'}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="lg:col-span-3 space-y-4">
                  {chartFigure && chartType !== 'table' && (<>
                    <EChartView option={chartFigure} height={420}/>
                    <button onClick={handleSaveChart} disabled={!chartInfo}
                      className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30">
                      <FiSave className="w-3.5 h-3.5"/>保存到仪表盘
                    </button>
                  </>)}
                </div>
              </div>
            </>
          )}
        </>
      )}
      {tab === 'chat' && (
        <div className="space-y-4">
          {(!insights || insights.startsWith('⚠️')) && (
            <button onClick={generateInsights} disabled={loading} className="w-full px-6 py-3 text-sm rounded-lg bg-[#8b5cf6]/80 text-white hover:bg-[#8b5cf6] disabled:opacity-50 transition-colors">
              {loading ? '分析中...' : '📊 生成自动数据洞察'}
            </button>
          )}

          {insights && !insights.startsWith('⚠️') && (
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">📊 数据洞察报告</h3>
              <div 
                className="text-sm text-slate-300 leading-relaxed prose-a:text-[#8b5cf6] prose-strong:text-[#f8fafc] max-h-96 overflow-y-auto pr-2"
                style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(139,92,246,0.3) transparent' }}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(insights) }}
              />
              <div className="pt-2 border-t border-white/[0.06]">
                <button
                  onClick={() => handleApplyInsights()}
                  disabled={loading || computing}
                  className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-gradient-to-r from-[#22d3ee]/20 to-[#a78bfa]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:from-[#22d3ee]/30 hover:to-[#a78bfa]/30 disabled:opacity-50 transition-all"
                >
                  <FiZap className="w-4 h-4" />
                  {computing ? '正在生成分析计划...' : '🚀 一键生成分析计划'}
                </button>
              </div>
            </div>
          )}

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {chatHistory.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] p-3 rounded-lg text-sm ${
                    msg.role === 'user'
                      ? 'bg-[#8b5cf6]/30 text-slate-200'
                      : 'glass-card text-slate-300'
                  }`}
                >
                  {msg.role === 'user' ? (
                    <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                  ) : (
                    <div>
                      <div className="leading-relaxed prose-a:text-[#8b5cf6] prose-strong:text-[#f8fafc] max-h-64 overflow-y-auto pr-1"
                        style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(139,92,246,0.3) transparent' }}
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                      />
                      <div className="flex justify-end mt-2 pt-1.5 border-t border-white/[0.06]">
                        <button
                          onClick={() => handleApplyInsights(msg.content)}
                          disabled={loading || computing}
                          className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-[#22d3ee]/10 border border-[#22d3ee]/20 text-[#22d3ee] hover:bg-[#22d3ee]/20 disabled:opacity-50 transition-colors"
                          title="基于这条建议自动计算并生成图表"
                        >
                          <FiZap className="w-3 h-3" />
                          应用
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendChat()}
              placeholder="输入你的数据分析问题..."
              className="flex-1 px-4 py-3 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8b5cf6]/50 transition-colors"
            />
            <button
              onClick={sendChat}
              disabled={loading || !chatInput.trim() || !ds.apiKey}
              className="px-6 py-3 text-sm rounded-lg bg-[#8b5cf6]/80 text-white hover:bg-[#8b5cf6] disabled:opacity-50 transition-colors"
            >
              发送
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

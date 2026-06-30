/* AnalysisPage - 分析与可视化 */
import React, { useState, useEffect, useCallback } from 'react';
import { FiBarChart2, FiMessageSquare, FiTrendingUp, FiZap, FiPlus, FiSave, FiFileText } from 'react-icons/fi';
import EChartView, { EChartsOption } from '../components/EChartView';
import DataTable from '../components/DataTable';
import TbHbTable, { type TbHbRow } from '../components/TbHbTable';
import KPICards, { type KPIItem } from '../components/KPICards';
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

  /** 一键应用洞察：解析建议逐条 → 按需计算 → 自动生成第一张图 → 跳转到智能绘图
   *  @param sourceText 可选，优先使用传入的文本；否则取 chatHistory 最后一条 AI 回复，其次取 insights */
  const handleApplyInsights = async (sourceText?: string) => {
    // 确定源文本
    let rawText = sourceText;
    if (!rawText) {
      const lastAi = [...chatHistory].reverse().find(m => m.role === 'ai');
      if (lastAi) rawText = lastAi.content;
    }
    if (!rawText) rawText = insights;

    if (!rawText) {
      alert('请先生成 AI 洞察或在 AI 对话中讨论分析方向');
      return;
    }
    if (!ds.apiKey) {
      alert('请先在左上角配置 AI API Key');
      return;
    }

    // ---- Step 1: 提取"建议"后面的文本 ----
    let suggestionsText = '';
    const txt = rawText;
    if (txt.includes('分析建议') || txt.includes('建议')) {
      const splitKey = txt.includes('分析建议') ? '分析建议' : '建议';
      suggestionsText = txt.split(splitKey)[1] || '';
    } else {
      suggestionsText = txt;
    }
    suggestionsText = suggestionsText
      .replace(/[#*_`>|]/g, ' ')
      .replace(/\n{3,}/g, '\n')
      .trim();

    if (!suggestionsText) {
      alert('未能从洞察中提取到分析建议，请手动在左侧"AI 数据计算"中输入');
      return;
    }

    setComputing(true);
    setComputeResult('⏳ Step 1: 正在解析建议...');

    // ---- Step 1.5: 逐行解析建议，提取每条的 X/Y/图表类型 ----
    // ★ 关键：地图/省份关键词必须排在"分布"前面，
    //   否则"各省份销售金额分布"会先命中"分布"→被误判为直方图而非地图
    const CHART_KEYWORD_MAP: Record<string, string> = {
      '柱状图': 'bar', '对比': 'bar', '排名': 'bar', '排序': 'bar', '差异': 'bar',
      '饼图': 'pie', '占比': 'pie', '比例': 'pie', '份额': 'pie', '百分比': 'pie',
      '3D地图': 'gl_map', '地图': 'gl_map', '地区分布': 'gl_map', '地理': 'gl_map', '省份': 'gl_map',
      '直方图': 'histogram', '分布': 'histogram', '频次': 'histogram',
      '散点图': 'scatter', '相关': 'scatter', '关联': 'scatter',
      '折线图': 'line', '趋势': 'line', '变化': 'line', '走势': 'line', '增长': 'line',
      '面积图': 'area', '累计': 'area', '覆盖': 'area',
      '堆叠柱状图': 'stacked_bar', '堆叠': 'stacked_bar', '叠加': 'stacked_bar',
      '雷达图': 'radar', '雷达': 'radar', '多维': 'radar',
      '词云图': 'wordcloud', '词云': 'wordcloud', '热词': 'wordcloud', '关键词': 'wordcloud',
      '热力图': 'heatmap', '矩阵': 'heatmap', '交叉': 'heatmap',
      '瀑布图': 'waterfall', '瀑布': 'waterfall', '增减': 'waterfall',
      '树状图': 'treemap', '树状': 'treemap', '层级': 'treemap',
      '气泡图': 'bubble', '气泡': 'bubble',
      '箱线图': 'box', '箱线': 'box',
    };

    // 计算关键词（需要 AI compute 的条目）
    const COMPUTE_KEYWORDS = ['同比', '环比', '累计', '移动平均', '均值', '总和', '占比', '排名', '聚合', '计算'];

    const lines = suggestionsText.split('\n').filter(l => /^\d+[a-z]?\./.test(l.trim()));
    const parsedSuggestions: Array<{
      line: string;
      chartType: string;
      x: string;
      y: string;
      needCompute: boolean;
      computeQuery: string;
    }> = [];

    for (const line of lines) {
      const cleanLine = line.trim().replace(/^\d+[a-z]?\.\s*/, '');
      // 提取 X:xxx, Y:xxx（支持中文列名）
      const xMatch = cleanLine.match(/X[:：]([\w\u4e00-\u9fa5_]+)/);
      const yMatch = cleanLine.match(/Y[:：]([\w\u4e00-\u9fa5_]*)/);
      const xCol = xMatch?.[1] || '';
      const yCol = yMatch?.[1] || '';

      // 提取图表类型：优先匹配"推荐XXX图"或"→ XXX图"，然后匹配关键词
      let chartType = '';
      const chartNameMatch = cleanLine.match(/(?:推荐|→)\s*(\S+图|3D地图)/);
      if (chartNameMatch && CHART_KEYWORD_MAP[chartNameMatch[1]]) {
        chartType = CHART_KEYWORD_MAP[chartNameMatch[1]];
      } else {
        // 按关键词优先级匹配
        for (const [kw, type] of Object.entries(CHART_KEYWORD_MAP)) {
          if (cleanLine.includes(kw)) { chartType = type; break; }
        }
      }
      if (!chartType) chartType = 'bar'; // 默认柱状图

      // 判断是否需要计算
      const needCompute = COMPUTE_KEYWORDS.some(kw => cleanLine.includes(kw));
      // ★ 同环比数据数值波动小，折线图看起来是一条直线，改用表格展示
      if (['同比', '环比'].some(kw => cleanLine.includes(kw))) chartType = 'table';

      parsedSuggestions.push({
        line: cleanLine,
        chartType,
        x: xCol,
        y: yCol,
        needCompute,
        computeQuery: cleanLine,
      });
    }

    // 如果没有解析到带编号的行，用老逻辑兜底
    if (parsedSuggestions.length === 0) {
      // 获取列信息
      let allCols = columns;
      let numCols = numericColumns;
      try {
        const colRes = await api.getColumnInfo(ds.sessionId);
        if (colRes.columns) {
          allCols = colRes.columns.map((c: Record<string, unknown>) => String(c.name ?? ''));
          numCols = colRes.columns
            .filter((c: Record<string, unknown>) => ['float64', 'int64', 'int32', 'float32'].includes(String(c.dtype ?? '')))
            .map((c: Record<string, unknown>) => String(c.name ?? ''));
        }
      } catch { /* ignore */ }

      const catCols = allCols.filter(c => !numCols.includes(c));
      const dimCol = catCols[0] || '地区';
      const text = suggestionsText.slice(0, 500);
      const mentionedNumCols = numCols.filter(c => text.includes(c)).slice(0, 3);
      const mentionedCatCols = catCols.filter(c => text.includes(c)).slice(0, 2);

      // 用关键词匹配兜底
      const fallbackSuggestions: Array<{ type: string; x: string; y: string; title: string }> = [];
      const priorityNumCols = [...new Set([...mentionedNumCols, ...numCols])].slice(0, 5);

      if (text.includes('地图') || text.includes('地区分布') || text.includes('省份')) {
        // ★ 优先选「省份」列（精确匹配 GeoJSON），其次才按通用正则
        const geoCol = allCols.find(c => c === '省份' || c.toLowerCase() === 'province')
          || allCols.find(c => /省/.test(c))
          || allCols.find(c => /市|地区|城市/.test(c))
          || dimCol;
        fallbackSuggestions.push({ type: 'gl_map', x: geoCol, y: priorityNumCols[0] || '', title: '中国地图' });
      }
      if (text.includes('对比') || text.includes('排名')) {
        fallbackSuggestions.push({ type: 'bar', x: mentionedCatCols[0] || dimCol, y: priorityNumCols[0] || '', title: '对比排名' });
      }
      if (text.includes('占比') || text.includes('比例')) {
        fallbackSuggestions.push({ type: 'pie', x: mentionedCatCols[0] || dimCol, y: priorityNumCols[0] || '', title: '占比分布' });
      }
      if (text.includes('趋势') || text.includes('变化') || text.includes('走势')) {
        const dateCol = allCols.find(c => /日期|时间|月份|年份/.test(c.toLowerCase())) || dimCol;
        fallbackSuggestions.push({ type: 'line', x: dateCol, y: priorityNumCols[0] || '', title: '趋势变化' });
      }
      if (text.includes('相关') || text.includes('关联')) {
        if (numCols.length >= 2) fallbackSuggestions.push({ type: 'scatter', x: numCols[0], y: numCols[1], title: '相关性' });
      }
      if (text.includes('分布') || text.includes('频次')) {
        fallbackSuggestions.push({ type: 'histogram', x: priorityNumCols[0] || '', y: '', title: '分布直方图' });
      }
      if (fallbackSuggestions.length === 0) {
        fallbackSuggestions.push({ type: 'bar', x: dimCol, y: priorityNumCols[0] || '', title: '概览' });
      }

      for (const s of fallbackSuggestions) {
        parsedSuggestions.push({
          line: s.title,
          chartType: s.type,
          x: s.x,
          y: s.y,
          needCompute: false,
          computeQuery: '',
        });
      }
    }

    setComputeResult(`✅ Step 1: 解析到 ${parsedSuggestions.length} 条建议`);

    // ---- Step 2: 按需执行 AI 计算 ----
    const needComputeItems = parsedSuggestions.filter(s => s.needCompute);
    if (needComputeItems.length > 0) {
      // 将所有需要计算的建议合并成一个 compute 指令
      const computeLines = needComputeItems.map(s => s.computeQuery).join('\n');
      const computeQueryText = `根据以下分析建议，对数据添加计算列（用现有列名，不要虚构列名）：\n${computeLines}\n\n请生成 Python 代码，为每条建议添加对应的计算列。`;

      setComputeResult((prev) => prev + `\n⏳ Step 2: 正在计算 ${needComputeItems.length} 条建议...`);

      try {
        const provider = getProviderConfig();
        const res = await api.computeData(ds.sessionId, computeQueryText, ds.apiKey, provider?.baseUrl, provider?.model);
        setComputeResult((prev) => prev + `\n✅ Step 2: ${res.message}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '未知错误';
        setComputeResult((prev) => prev + `\n❌ Step 2: 计算失败 - ${msg}`);
        setComputing(false);
        // 计算失败时仍然继续推荐图表（用原始列）
      }

      // 刷新列列表
      window.dispatchEvent(new Event('columns-updated'));
      // 等列刷新完成
      await new Promise(resolve => setTimeout(resolve, 500));
      // ★ 对同环比建议，调用专用接口获取结构化表格数据 + 折线图
      const tbHbItems = parsedSuggestions.filter(s => s.chartType === 'table');
      if (tbHbItems.length > 0) {
        const firstTb = tbHbItems[0];
        try {
          // ★ 用真实数值列（不能用 firstTb.x，那是日期列）
          const numColsForTb = numericColumns;
          const valueColumn = numColsForTb.find(c => /金额|收入|数量|利润|成本/.test(c))
            || numColsForTb[0] || '';
          if (valueColumn && valueColumn !== firstTb.x) {
            const tbRes = await api.getTongHuanBi(ds.sessionId, valueColumn, firstTb.x || '日期');
            if (tbRes.success) {
              setTbHbData({
                rows: tbRes.rows,
                value_column: tbRes.value_column,
                current_year: tbRes.current_year,
                previous_year: tbRes.previous_year,
                has_yoy: tbRes.has_yoy,
                chart_option: tbRes.chart_option,
              });
              if (tbRes.chart_option) {
                setChartFigure(tbRes.chart_option as EChartsOption);
                setChartInfo({
                  title: getOptionTitle(tbRes.chart_option as Record<string, unknown>),
                  option: tbRes.chart_option,
                });
              }
            }
          }
        } catch { /* ignore */ }
      }
    } else {
      setComputeResult((prev) => prev + `\n✅ Step 2: 无需计算（所有建议可直接用原始列）`);
    }

    // ---- Step 3: 刷新列信息 + 构建图表建议 ----
    setComputeResult((prev) => prev + `\n⏳ Step 3: 正在推荐图表...`);

    // 获取最新列信息（可能包含计算新增的列）
    let allCols = columns;
    let numCols = numericColumns;
    try {
      const colRes = await api.getColumnInfo(ds.sessionId);
      if (colRes.columns) {
        allCols = colRes.columns.map((c: Record<string, unknown>) => String(c.name ?? ''));
        numCols = colRes.columns
          .filter((c: Record<string, unknown>) => ['float64', 'int64', 'int32', 'float32'].includes(String(c.dtype ?? '')))
          .map((c: Record<string, unknown>) => String(c.name ?? ''));
        setColumns(allCols);
        setNumericColumns(numCols);
      }
    } catch { /* ignore */ }

    // 验证每条的 X/Y 列是否存在于最新列列表
    const validSuggestions: Array<{ type: string; x: string; y: string; title: string }> = [];
    for (const s of parsedSuggestions) {
      const validX = allCols.includes(s.x) ? s.x : '';
      const validY = numCols.includes(s.y) ? s.y : '';
      // 特殊处理：gl_map 的 y 可以是任何列；histogram/wordcloud/radar/table 不需要 y
      const finalY = (['histogram', 'wordcloud', 'radar', 'table'].includes(s.chartType)) ? '' : validY;

      // 如果 X 列不存在，尝试用关键词找到匹配的列
      if (!validX && s.x) {
        const matchCol = allCols.find(c => c.includes(s.x) || s.x.includes(c));
        if (matchCol) { s.x = matchCol; }
      }

      // 如果 X 还是不存在，跳过或用默认
      const finalX = allCols.includes(s.x) ? s.x :
        (s.chartType === 'table' ? allCols.find(c => /日期|时间|月份|年份/.test(c)) || '' :
         s.chartType === 'gl_map' ? (allCols.find(c => c === '省份' || c.toLowerCase() === 'province') || allCols.find(c => /省/.test(c)) || allCols.find(c => /市|地区|城市/.test(c)) || '') :
         numCols.includes(s.x) ? s.x : allCols.find(c => !numCols.includes(c)) || '');

      if (finalX) {
        const shortLine = s.line.replace(/（X[:：].*?Y[:：].*?）/g, '').replace(/→.*$/, '').trim().slice(0, 30);
        validSuggestions.push({
          type: s.chartType,
          x: finalX,
          y: finalY,
          title: shortLine || `${finalX}${finalY ? ' / ' + finalY : ''} (${s.chartType})`,
        });
      }
    }

    // 兜底：如果都没有有效建议
    if (validSuggestions.length === 0) {
      const catCols = allCols.filter(c => !numCols.includes(c));
      const defaultX = catCols[0] || allCols[0] || '';
      const defaultY = numCols[0] || '';
      if (defaultX) {
        validSuggestions.push({ type: 'bar', x: defaultX, y: defaultY, title: `${defaultY || defaultX} 概览` });
      }
    }

    // 限制最多 8 个
    const finalSuggestions = validSuggestions.slice(0, 8);

    // 设置第一个建议为当前图表配置，但保留所有建议在列表中（包括第一个）
    if (finalSuggestions.length > 0) {
      const first = finalSuggestions[0];
      setChartType(first.type);
      setChartX(first.x);
      setChartY(first.y);
      setChartSuggestions(finalSuggestions);  // 不减 slice(1)，让用户能切回第一张图
    }

    const list = finalSuggestions.map((s, i) => `   ${i + 1}. ${s.title} (${s.type}, X:${s.x}, Y:${s.y})`);
    setComputeResult((prev) =>
      prev + `\n✅ Step 3: 推荐 ${finalSuggestions.length} 个图表：\n${list.join('\n')}`
    );

    // ---- Step 4: 自动生成第一张图表/表格 ----
    setComputeResult((prev) => prev + `\n⏳ 正在自动生成第一张图表...`);

    if (finalSuggestions.length > 0) {
      const first = finalSuggestions[0];
      if (first.type === 'table') {
        // 同环比等用表格展示，调用专用接口
        setComputeResult((prev) => prev + `\n✅ 检测到同环比数据，以表格+趋势图展示`);
        setChartType('table');
        setChartX(first.x);
        setChartY('');
        // ★ 找到真正的数值列（不能用 first.x，那是日期列）
        const valueColumn = numCols.find(c => /金额|收入|数量|利润|成本/.test(c))
          || numCols[0] || '';
        if (valueColumn && valueColumn !== first.x) {
          try {
            const dateCol = first.x || '日期';
            const tbRes = await api.getTongHuanBi(ds.sessionId, valueColumn, dateCol);
            if (tbRes.success) {
              setTbHbData({
                rows: tbRes.rows,
                value_column: tbRes.value_column,
                current_year: tbRes.current_year,
                previous_year: tbRes.previous_year,
                has_yoy: tbRes.has_yoy,
                chart_option: tbRes.chart_option,
              });
              // 同时设置折线图
              if (tbRes.chart_option) {
                setChartFigure(tbRes.chart_option as EChartsOption);
                setChartInfo({
                  title: getOptionTitle(tbRes.chart_option as Record<string, unknown>),
                  option: tbRes.chart_option,
                });
              } else {
                setChartFigure(null);
                setChartInfo(null);
              }
            }
          } catch { /* ignore */ }
        }
      } else {
        try {
          const res = await api.createEChart(ds.sessionId, {
            chart_type: first.type,
            x: first.x,
            y: first.y,
          });
          if (res.option) {
            setChartFigure(res.option);
            const title = first.y ? `${first.x} vs ${first.y}` : `${first.x} - ${first.type}`;
            setChartInfo({ title, option: res.option });
            setComputeResult((prev) => prev + `\n✅ 第一张图表已生成！`);
          }
        } catch (err) {
          setComputeResult((prev) => prev + `\n⚠️ 自动生成图表失败，请手动点击"生成图表"`);
        }
      }
    }

    setComputing(false);

    // 跳转到智能绘图 tab（此时图表已经渲染好了）
    setTab('charts');
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
                    {computing ? '正在应用洞察...' : '🚀 一键应用 — 自动计算 + 绘图'}
                  </button>
                  <span className="text-xs text-slate-500">解析建议 → AI计算列 → 自动生成第一张图表 → 推荐更多</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'charts' && (
        <>
          {/* KPI 指标卡片 */}
          {analysisKpis.length > 0 && <KPICards kpis={analysisKpis} />}

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 space-y-4">
            {/* AI 数据计算面板 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <FiZap className="w-4 h-4 text-yellow-400" /> AI 数据计算
              </h3>
              <p className="text-xs text-slate-500">输入计算需求，AI 自动生成同比/环比/占比等计算列</p>
              <input
                value={computeQuery}
                onChange={(e) => setComputeQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCompute()}
                placeholder="如：计算 age 的均值、总和、同比增长..."
                className="w-full px-3 py-2 text-xs rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#8b5cf6]/50"
              />
              <button onClick={handleCompute} disabled={computing || !computeQuery.trim()}
                className="w-full px-3 py-2 text-xs rounded-lg bg-yellow-600/80 text-white hover:bg-yellow-600 disabled:opacity-50 transition-colors">
                {computing ? '计算中...' : '⚡ 执行计算'}
              </button>
              {computeResult && (
                <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-white/[0.04] rounded p-2 max-h-40 overflow-y-auto"
                  style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(139,92,246,0.3) transparent' }}>
                  {computeResult}
                </div>
              )}
              <div className="text-[10px] text-slate-600 space-y-0.5">
                <p>试试这些：</p>
                <p className="pl-1">· 计算各城市薪资的平均值和总和</p>
                <p className="pl-1">· 按部门计算薪资排名</p>
                <p className="pl-1">· 计算每个部门薪资的占比</p>
                <p className="pl-1">· 计算薪资的累计和移动平均</p>
              </div>
              <button
                onClick={async () => {
                  try {
                    const res = await api.getColumnInfo(ds.sessionId);
                    if (res.columns) {
                      // 触发全局事件通知其他组件列信息已更新
                      window.dispatchEvent(new CustomEvent('columns-updated', { detail: res.columns }));
                      setComputeResult((prev) => prev + '\n✅ 列列表已刷新，新列可在 X/Y 轴下拉框中选择');
                    }
                  } catch {
                    setComputeResult((prev) => prev + '\n❌ 刷新列列表失败');
                  }
                }}
                className="w-full px-3 py-1.5 text-xs rounded bg-white/[0.06] text-slate-400 hover:text-white transition-colors"
              >
                <FiPlus className="w-3 h-3 inline mr-1" />刷新列列表
              </button>
            </div>

            {/* 图表配置 */}
            <div className="glass-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              图表配置
              {chartX && computeResult.includes('已自动推荐图表') && (
                <span className="text-[10px] text-[#22d3ee] font-normal">(AI 已自动推荐)</span>
              )}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-500 block mb-1">图表类型</label>
                <select value={chartType} onChange={(e) => {
                  setChartType(e.target.value);
                  // 词云、雷达图不需要手动选 Y 轴，但 gl_map 需要
                  if (e.target.value === 'wordcloud' || e.target.value === 'radar') setChartY('');
                }} className={inputClass}>
                  <option value="bar">柱状图</option>
                  <option value="stacked_bar">堆叠柱状图</option>
                  <option value="line">折线图</option>
                  <option value="area">面积图</option>
                  <option value="scatter">散点图</option>
                  <option value="bubble">气泡图</option>
                  <option value="pie">饼图</option>
                  <option value="histogram">直方图</option>
                  <option value="box">箱线图</option>
                  <option value="heatmap">热力图</option>
                  <option value="radar">雷达图</option>
                  <option value="waterfall">瀑布图</option>
                  <option value="treemap">树状图</option>
                  <option value="wordcloud">词云图</option>
                  <option value="gl_map">🌍 3D 地图</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-500 block mb-1">
                  {chartType === 'table' ? 'X 轴（请选日期列）' : chartType === 'gl_map' ? 'X 轴（请选地区/省份列）' : chartType === 'wordcloud' ? 'X 轴（词云图请选文本列）' : 'X 轴'}
                </label>
                <select value={chartX} onChange={(e) => setChartX(e.target.value)} className={inputClass}>
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {chartType !== 'wordcloud' && chartType !== 'radar' && chartType !== 'table' && (
                <div>
                  <label className="text-xs text-slate-500 block mb-1">
                    {chartType === 'gl_map' ? 'Y 轴（请选数值列，决定地图柱高度）' : 'Y 轴（可选）'}
                  </label>
                  <select value={chartY} onChange={(e) => setChartY(e.target.value)} className={inputClass}>
                    <option value="">选择列...</option>
                    {numericColumns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}

              <button onClick={() => generateChart()} disabled={loading || (!chartX && chartType !== 'gl_map')} className={btnFullClass}>
                {loading ? '生成中...' : '生成图表'}
              </button>
            </div>
          </div>{/* 图表配置 card 结束 */}
          </div>{/* 左侧栏 wrapper 结束 */}

          <div className="lg:col-span-3 space-y-4">
            {/* AI 推荐的图表建议列表 */}
            {chartSuggestions.length > 0 && (
              <div className="glass-card p-3">
                <h3 className="text-xs font-semibold text-slate-400 mb-2">💡 AI 图表建议（点击切换并生成）</h3>
                <div className="flex flex-wrap gap-2">
                  {chartSuggestions.map((s, i) => {
                    const isFirst = i === 0;
                    return (
                    <button
                      key={i}
                      onClick={() => {
                        if (s.type === 'table') {
                          setChartType('table');
                          setChartX(s.x);
                          setChartY(s.y);
                          const valueColumn = numericColumns.find(c => /金额|收入|数量|利润|成本/.test(c))
                            || numericColumns[0] || '';
                          if (valueColumn && valueColumn !== s.x) {
                            const shouldRefetch = !tbHbData || tbHbData.value_column !== valueColumn;
                            const fetch = () => {
                              api.getTongHuanBi(ds.sessionId, valueColumn, s.x || '日期').then(res => {
                                if (res.success) {
                                  setTbHbData({ rows: res.rows, value_column: res.value_column, current_year: res.current_year, previous_year: res.previous_year, has_yoy: res.has_yoy, chart_option: res.chart_option });
                                  if (res.chart_option) {
                                    setChartFigure(res.chart_option as EChartsOption);
                                    setChartInfo({ title: getOptionTitle(res.chart_option as Record<string, unknown>), option: res.chart_option });
                                  }
                                }
                              }).catch(() => {});
                            };
                            if (shouldRefetch) fetch();
                            else if (tbHbData?.chart_option) {
                              setChartFigure(tbHbData.chart_option as EChartsOption);
                              setChartInfo({ title: getOptionTitle(tbHbData.chart_option as Record<string, unknown>), option: tbHbData.chart_option });
                            }
                          }
                        } else {
                          setChartType(s.type);
                          setChartX(s.x);
                          setChartY(s.y);
                          generateChart({ type: s.type, x: s.x, y: s.y });
                        }
                      }}
                      disabled={loading}
                      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors disabled:opacity-50 ${
                        isFirst
                          ? 'border-[#22d3ee]/40 bg-[#22d3ee]/20 text-[#22d3ee] hover:bg-[#22d3ee]/30'
                          : 'border-white/[0.1] bg-white/[0.06] text-slate-400 hover:text-white hover:border-[#a78bfa]/30'
                      }`}
                    >
                      {i + 1}. {s.title.replace(/^\d+\.\s*/, '')} ({s.type})
                    </button>
                    );
                  })}
                </div>
              </div>
            )}
            {chartFigure && chartType !== 'table' ? (
              <>
                <EChartView option={chartFigure} height={500} />
                <div className="flex items-center gap-3 mt-3">
                  <button onClick={handleSaveChart} disabled={!chartInfo}
                    className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30 transition-colors disabled:opacity-50">
                    <FiSave className="w-3.5 h-3.5" />
                    保存到仪表盘
                    {savedCount > 0 && <span className="text-[10px] bg-[#22d3ee]/30 px-1.5 py-0.5 rounded">已存{savedCount}个</span>}
                  </button>
                  <button onClick={handleGenerateReport} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-[#8b5cf6]/20 border border-[#8b5cf6]/30 text-[#a78bfa] hover:bg-[#8b5cf6]/30 transition-colors">
                    <FiFileText className="w-3.5 h-3.5" />
                    生成分析报告
                  </button>
                  {saveMsg && <span className="text-xs text-[#22d3ee]">{saveMsg}</span>}
                </div>
              </>
            ) : chartType === 'table' && tbHbData && tbHbData.rows.length > 0 ? (
              /* ★ 同环比：折线图 + 规范表格 同时展示 */
              <div className="space-y-4">
                {chartFigure && <EChartView option={chartFigure} height={320} />}
                <TbHbTable
                  data={tbHbData.rows}
                  valueColumn={tbHbData.value_column}
                  currentYear={tbHbData.current_year}
                  previousYear={tbHbData.previous_year}
                  hasYoY={tbHbData.has_yoy}
                  maxHeight="380px"
                />
                <div className="flex items-center gap-3">
                  {chartFigure && chartInfo && (
                    <button onClick={handleSaveChart}
                      className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30 transition-colors">
                      <FiSave className="w-3.5 h-3.5" />
                      保存到仪表盘
                      {savedCount > 0 && <span className="text-[10px] bg-[#22d3ee]/30 px-1.5 py-0.5 rounded">已存{savedCount}个</span>}
                    </button>
                  )}
                  <button onClick={handleGenerateReport} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-[#8b5cf6]/20 border border-[#8b5cf6]/30 text-[#a78bfa] hover:bg-[#8b5cf6]/30 transition-colors">
                    <FiFileText className="w-3.5 h-3.5" />
                    生成分析报告
                  </button>
                  {saveMsg && <span className="text-xs text-[#22d3ee]">{saveMsg}</span>}
                </div>
              </div>
            ) : (
              <div className="glass-card p-12 text-center text-slate-500 flex items-center justify-center" style={{ minHeight: 400 }}>
                选择列并点击「生成图表」
              </div>
            )}
          </div>
        </div>
      </>)}
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
                  {computing ? '正在应用洞察...' : '🚀 一键应用 — 自动计算 + 绘图'}
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

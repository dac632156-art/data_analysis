/* DashboardPage - 大屏仪表盘（3模板 + AI推荐 + ECharts引擎） */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import html2canvas from 'html2canvas';
import { FiDownload, FiFileText, FiGrid, FiRadio, FiActivity, FiSave } from 'react-icons/fi';
import EGridLayout from '../components/BigScreen/EGridLayout';
import CommandScreen from '../components/BigScreen/CommandScreen';
import MedicalDashboard from '../components/BigScreen/MedicalDashboard';
import KPICards, { type KPIItem } from '../components/KPICards';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import { generateEChartsDashboardHTML, downloadEChartsHTML } from '../utils/exportEChartsDashboard';
import type { EChartItem, CardItem, CardMeta } from '../types/api';

type TemplateType = 'command' | 'grid' | 'medical' | 'report';

/** 根据数据列名推断行业/业务领域，生成对应的报告标题 */
function inferIndustryTitle(columns: string[]): string {
  const colStr = columns.join(' ').toLowerCase();

  const industryPatterns: [RegExp, string][] = [
    [/营业额|销售额|售价|sku|库存|订单量|退货数|退货率|销量|品类|门店|渠道|零售|商品名称/, '零售业务数据报告'],
    [/病人|患者|诊断|处方|药物|医院|科室|手术|门诊|体检/, '医疗业务数据报告'],
    [/金额|利率|贷款|存款|投资|收益|基金|股票|债券|收盘价|开盘价|账户/, '金融数据报告'],
    [/学生|成绩|科目|班级|教师|课程|学分|考试|毕业|院系/, '教育数据报告'],
    [/员工|部门|薪资|绩效|考勤|离职|入职|职称|工龄|人事/, '人力资源分析报告'],
    [/面积|房价|户型|楼盘|成交价|均价|租赁|租金|物业/, '房地产数据报告'],
    [/物流|快递|配送|仓库|运输|运费|发货|签收|包裹/, '物流数据报告'],
    [/产量|良品率|次品|机器|流水线|产能|质检|原材料|生产/, '生产制造分析报告'],
    [/菜品|翻台率|外卖|堂食|客单|食材|菜系|配餐/, '餐饮数据报告'],
    [/省份|城市|地区|区域|地图|省份名/, '地区数据报告'],
    [/广告|曝光|点击|转化|cpc|cpm|roi|流量|渠道/, '广告投放分析报告'],
    [/产品|客户|用户|交易|支付|购物|浏览|点击|商品|品类/, '电商数据分析报告'],
  ];

  for (const [re, title] of industryPatterns) {
    if (re.test(colStr)) return title;
  }

  // 兜底：根据字段特征判断
  const hasDate = /\b日期\b|时间|月份|季度|年份|date|time|month|year/i.test(colStr);
  const hasAmount = /金额|价格|收入|支出|成本|利润|费用|value|amount|price/i.test(colStr);
  const hasCategory = /类别|类型|分类|部门|地区|城市|省份/i.test(colStr);

  if (hasDate && hasAmount && hasCategory) return '多维度业务数据分析';
  if (hasDate && hasAmount) return '财务趋势分析';
  if (hasDate) return '时序数据分析';
  if (hasAmount) return '核心指标分析';

  return '数据分析看板';
}

const TEMPLATES: { id: TemplateType; label: string; icon: typeof FiGrid; desc: string }[] = [
  { id: 'command', label: '指挥中心', icon: FiRadio, desc: '3D地球 + 数据面板 + 飞线大屏' },
  { id: 'medical', label: '数据看板', icon: FiActivity, desc: 'KPI数字 + 趋势图 + 雷达图 + 数据表格' },
  { id: 'grid', label: '经典网格', icon: FiGrid, desc: 'KPI条 + 2x3图表 + 联动高亮' },
  { id: 'report', label: '分析报告', icon: FiFileText, desc: '专业图文报告 + AI分析 + 导出' },
];

export default function DashboardPage() {
  const { state: ds } = useData();
  const [template, setTemplate] = useState<TemplateType>('grid');
  const [kpis, setKpis] = useState<KPIItem[]>([]);
  const [echarts, setECharts] = useState<EChartItem[]>([]);
  const [chartTabs, setChartTabs] = useState<Record<string, EChartItem[]>>({
    '数据总览': [], '趋势洞察': [], '分类分析': [], '明细查询': [],
  });
  const [navTabs, setNavTabs] = useState<string[]>(['数据总览', '趋势洞察', '分类分析', '明细查询']);
  const [ringCharts, setRingCharts] = useState<Array<{ title: string; data: Array<{ name: string; value: number }> }>>([]);
  const [reportHtml, setReportHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [hideChartTitle, setHideChartTitle] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [savedTableData, setSavedTableData] = useState<Record<string, unknown>[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [cardMeta, setCardMeta] = useState<CardMeta | null>(null);

  const screenRef = useRef<HTMLDivElement>(null);
  const hasData = ds.rows > 0;

  // ===== 加载 ECharts 仪表盘 =====
  const loadEChartsDashboard = useCallback(async () => {
    if (!hasData) return;
    setLoading(true);
    try {
      const [kpiRes, echartsRes] = await Promise.all([
        api.getDashboardKPIs(ds.sessionId),
        api.getDashboardECharts(ds.sessionId),
      ]);
      if (kpiRes.kpis) setKpis(kpiRes.kpis);
      if (echartsRes.charts) setECharts(echartsRes.charts);
      // 读取 Tab 分类后的图表（新接口返回 tabs 字段）
      if ((echartsRes as any).tabs) {
        setChartTabs((echartsRes as any).tabs);
      }
    } catch (err) {
      console.error('[ECharts Dashboard] load failed:', err);
    } finally { setLoading(false); }
  }, [hasData, ds.sessionId]);

  useEffect(() => {
    loadEChartsDashboard();
  }, [loadEChartsDashboard]);

  // ===== V5: 加载 Cards =====
  const loadCards = useCallback(async () => {
    if (!hasData) return;
    try {
      const res = await api.generateCards(ds.sessionId);
      if (res.success && res.cards) {
        setCards(res.cards as CardItem[]);
        setCardMeta(res.meta || null);
      }
    } catch (err) {
      console.error('[Cards] load failed:', err);
    }
  }, [hasData, ds.sessionId]);

  useEffect(() => {
    loadCards();
  }, [loadCards]);

  // ===== 加载已保存分析包（从分析页收藏） =====
  const handleLoadSaved = async () => {
    setLoading(true);
    try {
      // 优先尝试 V2 saved_packages
      let res: any = null;
      try {
        res = await api.getSavedPackages(ds.sessionId);
      } catch {
        // V2 接口不可用，跳到旧接口
      }

      if (res && res.packages && res.packages.length > 0) {
        // V2：从 saved_packages 中提取图表、KPI 和表格
        const allCharts: EChartItem[] = [];
        const allKpis: KPIItem[] = [];
        const allTableData: Record<string, unknown>[] = [];
        for (const pkg of res.packages) {
          // 图表：rendered_charts（含 option）或 charts
          const pkgCharts = pkg.rendered_charts || pkg.charts || [];
          for (const c of pkgCharts) {
            if (c && c.option) {
              allCharts.push({
                title: c.title || '',
                option: c.option,
                x: c.x || '',
                y: c.y || '',
                analysis_type: pkg.analysis_type || '',
                chart_type: c.chart_type || '',
              } as EChartItem);
            }
          }
          // KPI：rendered_kpis（含 label/value 格式化）或 kpis
          const pkgKpis = pkg.rendered_kpis || pkg.kpis || [];
          for (const k of pkgKpis) {
            if (k) {
              // rendered_kpis 格式: {label, value, change, kpi_type, formatted, color}
              // kpis 格式: {label, value, change, kpi_type}
              allKpis.push({
                label: k.label || '',
                value: k.formatted || k.value || '',
                change: k.change || '',
                kpi_type: k.kpi_type || 'sum',
              });
            }
          }
          // 表格：rendered_tables（含 columns/rows）或 tables
          const pkgTables = pkg.rendered_tables || pkg.tables || [];
          for (const t of pkgTables) {
            if (t && t.rows && t.columns) {
              // RenderedTable 的 rows 是 List[List[RenderedCell]]，需要提取 value
              const tableRows = t.rows.map((row: unknown[]) => {
                return row.map((cell: any) => {
                  return cell && typeof cell === 'object' && 'value' in cell ? cell.value : cell;
                });
              });
              // 将表格转换为 EChartItem 格式，添加到 charts 数组
              // 使用 'analysis_table' 类型区分分析报告表格（与同环比表格 'table' 类型区分）
              allCharts.push({
                title: t.title || '数据表格',
                option: {},
                x: '',
                y: '',
                analysis_type: pkg.analysis_type || '',
                chart_type: 'analysis_table',
                table_data: {
                  rows: tableRows,
                  columns: t.columns,
                },
              } as EChartItem);
            }
          }
        }
        setECharts(allCharts);
        if (allKpis.length > 0) setKpis(allKpis);
        if (allKpis.length === 0) {
          const kpiRes = await api.getDashboardKPIs(ds.sessionId);
          if (kpiRes.kpis) setKpis(kpiRes.kpis);
        }
      } else {
        // V2 无数据 → fallback 到旧接口
        const oldRes = await api.getSavedCharts(ds.sessionId);
        if (oldRes.charts && oldRes.charts.length > 0) {
          // 旧格式：{title, option, type, saved_at, table_data}
          const charts: EChartItem[] = [];
          const allTableData: Record<string, unknown>[] = [];
          for (const c of oldRes.charts) {
            charts.push({
              title: c.title || '',
              option: (c as any).option || c,
              x: (c as any).x || '',
              y: (c as any).y || '',
              analysis_type: '',
              chart_type: (c as any).type || '',
              table_data: (c as any).table_data || null,
            } as EChartItem);
            // 收集表格数据（同环比表格类型）
            if ((c as any).table_data && (c as any).table_data.rows) {
              allTableData.push(...(c as any).table_data.rows);
            }
          }
          setECharts(charts);
          if (allTableData.length > 0) {
            setSavedTableData(allTableData);
          }
          const kpiRes = await api.getDashboardKPIs(ds.sessionId);
          if (kpiRes.kpis) setKpis(kpiRes.kpis);
        } else {
          alert('暂无已保存的分析结果，请先在「分析可视化」页面生成并保存图表');
        }
      }
    } catch (err) {
      console.error('加载保存分析失败', err);
    } finally { setLoading(false); }
  };

  // ===== 报告生成 =====
  const generateReport = async () => {
    setGenerating(true);
    try { const res = await api.generateReport(ds.sessionId); setReportHtml(res.html); }
    catch { /* ignore */ }
    finally { setGenerating(false); }
  };

  // ===== PNG 截图 =====
  const handleDownloadScreen = async () => {
    if (!screenRef.current) return;
    setDownloading(true);
    try {
      const canvas = await html2canvas(screenRef.current, {
        scale: 2, useCORS: true, backgroundColor: '#050816', logging: false,
      });
      const link = document.createElement('a');
      link.download = `数据大屏_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (err) {
      console.error('截图失败', err);
    } finally { setDownloading(false); }
  };

  // ===== HTML 导出 =====
  const handleExportHTML = () => {
    if (template === 'report') {
      handleExportReport();
      return;
    }
    if (template !== 'command' && echarts.length === 0) {
      alert('暂无图表数据');
      return;
    }
    const tableData = savedTableData.length > 0 ? savedTableData : (ds?.preview || []);
    const filename = `数据大屏_${displayTitle}_${new Date().toISOString().slice(0, 10)}.html`;
    const html = generateEChartsDashboardHTML(template, kpis, echarts, displayTitle, hideChartTitle, navTabs, ringCharts, tableData);
    setReportHtml(html);
    downloadEChartsHTML(html, filename);
  };

  // ===== AI 分析报告生成（五阶段流水线） =====
  const [reportGenerating, setReportGenerating] = useState(false);
  const [reportText, setReportText] = useState('');
  const [reportError, setReportError] = useState('');
  const [reportSections, setReportSections] = useState<Array<{
    type: string; title: string; content?: string;
    insights?: Array<string | { chart_title: string; chart_type: string | null; table_type: string | null; rule_id: string | null; insight_label: string | null; analysis: string }>;
    charts_to_create?: Array<{ chart_title: string; chart_type: string; rule_id: string; x_axis: string; y_axis: string; value: string; guide: string }>;
    action_items?: Array<{ priority: number; action: string }>;
  }>>([]);
  const [reportSummary, setReportSummary] = useState('');
  const [reportConclusion, setReportConclusion] = useState('');

  const handleExportReport = async () => {
    if (!ds.apiKey) { alert('请先在左上角配置 AI API Key'); return; }

    setReportGenerating(true);
    setReportError('');
    setReportText('📝 正在提交分析任务...');
    const provider = AI_PROVIDERS.find(p => p.id === ds.aiProvider);
    const pk = ds.apiKey;
    const bu = provider?.baseUrl;
    const md = provider?.model;

    try {
      // ★ 步骤1：提交异步任务（秒回 task_id）
      const { task_id } = await api.submitAIReport(ds.sessionId, pk, bu, md);
      setReportText('🔍 正在进行数据统计分析（阶段1-3）...');

      // ★ 步骤2：轮询任务状态（每 3 秒一次，最长等 5 分钟）
      const POLL_INTERVAL = 3000;   // 3 秒
      const MAX_WAIT = 5 * 60 * 1000; // 5 分钟
      const startTime = Date.now();
      let status = 'pending';

      while (status !== 'done' && status !== 'failed') {
        if (Date.now() - startTime > MAX_WAIT) {
          throw new Error('报告生成超时（超过5分钟），请尝试减少数据量后重试');
        }

        await new Promise(r => setTimeout(r, POLL_INTERVAL));
        const s = await api.getAIReportStatus(task_id);
        status = s.status;
        setReportText(s.message || reportText);

        if (status === 'failed') {
          throw new Error(s.error || '报告生成失败');
        }
      }

      // ★ 步骤3：获取结果
      const result = await api.getAIReportResult(task_id);
      const sections: Array<{
        type: string; title: string; content?: string;
        insights?: Array<string | { chart_title: string; analysis: string }>;
      }> = result.sections || [];

      // 提取概览和结论用于报告头部/尾部
      const overviewSection = sections.find(s => s.type === 'overview');
      const conclusionSection = sections.find(s => s.type === 'conclusion');
      const summaryText = overviewSection?.content || `数据共包含 ${kpis.length} 项关键指标`;
      const conclusionText = conclusionSection?.insights
        ?.map(i => typeof i === 'string' ? i : i.analysis).join('\n') || '';

      setReportSections(sections);
      setReportSummary(summaryText);
      setReportConclusion(conclusionText);
      setReportText('📝 正在生成报告文档...');

      // 生成 HTML 并下载
      const filename = `数据分析报告_${displayTitle}_${new Date().toISOString().slice(0, 10)}.html`;
      const html = generateEChartsDashboardHTML(
        'report', kpis, echarts, displayTitle, hideChartTitle,
        navTabs, ringCharts, ds?.preview || [],
        // ★ 将 ReportSection 转为旧的兼容格式给 buildReportHTML
        sections.map((sec, i) => {
          // 从仪表盘 echarts 里按 section 类型匹配图表（ECharts type 在 option.series[0].type 里）
          const chartIdx = echarts.findIndex(c => {
            const chartType = c.option?.series?.[0]?.type || '';
            if (sec.type === 'trend') return chartType === 'line';
            if (sec.type === 'top') return chartType === 'bar';
            if (sec.type === 'structure') return chartType === 'pie' || !!c.option?.geo;
            return false;
          });
          return {
          title: sec.title,
          subtitle: sec.type === 'overview' ? '数据概览' :
            sec.type === 'kpi' ? '核心指标' :
            sec.type === 'trend' ? '趋势分析' :
            sec.type === 'structure' ? '结构分析' :
            sec.type === 'top' ? 'TOP分析' :
            sec.type === 'anomaly' ? '异常分析' :
            sec.type === 'conclusion' ? '核心结论' :
            sec.type === 'suggestions' ? '业务建议' :
            sec.type === 'next_steps' ? '后续操作' : '分析',
          chartIndex: chartIdx >= 0 ? chartIdx : undefined,
          analysis: sec.type === 'next_steps'
            ? '' // next_steps 由 buildReportHTML 特殊渲染
            : sec.content || sec.insights?.map(j =>
              typeof j === 'string' ? j : (j.chart_title ? `**${j.chart_title}**：${j.analysis}` : j.analysis)
            ).join('\n') || '',
          chartsToCreate: sec.type === 'next_steps' ? (sec as any).charts_to_create : undefined,
          actionItems: sec.type === 'next_steps' ? (sec as any).action_items : undefined,
        };
      }),
        summaryText,
        conclusionText,
      );

      // 同时将 HTML 写入后端返回的结构化 sections 中
      const sectionsHTML = sections.map((sec, i) => {
        let secContent = '';
        if (sec.type === 'next_steps') {
          // next_steps 特殊渲染：操作建议
          const actionsHtml = sec.action_items?.sort((a, b) => (a.priority || 99) - (b.priority || 99)).map(a =>
            `<p style="margin:4px 0 2px 20px;">✅ ${a.priority !== 99 ? a.priority + '. ' : ''}${a.action}</p>`
          ).join('') || '';
          secContent = actionsHtml;
        } else {
          secContent = sec.content || sec.insights?.map(j =>
            typeof j === 'string' ? `<p>${j}</p>` : `<p><strong>${j.chart_title}</strong>：${j.analysis}</p>`
          ).join('') || '';
        }
        const iconMap: Record<string, string> = {
          overview: '📋', kpi: '📊', trend: '📈', structure: '🏗️',
          top: '🏆', anomaly: '⚠️', conclusion: '💡', suggestions: '🚀',
          next_steps: '🎯',
        };
        const icon = iconMap[sec.type] || '📄';
        return `
          <div class="section">
            <h2>${icon} ${sec.title}</h2>
            <div class="analysis-text">${secContent}</div>
            ${i < sections.length - 1 ? '<hr style="border-color:#e9ecef;margin:20px 0;">' : ''}
          </div>`;
      }).join('');

      setReportHtml(html);
      setReportText('✅ 报告生成完成！正在下载...');

      downloadEChartsHTML(html, filename);

      setTimeout(() => setReportText(''), 3000);
    } catch (err) {
      console.error('[Report] 生成失败，完整错误：', err);
      const msg = err instanceof Error ? err.message : '未知错误';
      setReportError('❌ 报告生成失败: ' + msg + (err instanceof Error && err.stack ? '\n详情见控制台(F12)' : ''));
    } finally {
      setReportGenerating(false);
    }
  };

  // 标题：根据数据列名推断 → 兜底
  const displayTitle = inferIndustryTitle(ds.preview?.[0] ? Object.keys(ds.preview[0]) : ds.columnInfo?.map(c => c.name) || [])
    || '数据分析看板';

  if (!hasData) {
    return (
      <div className="page-enter">
        <h1 className="text-2xl font-bold text-white mb-4" style={{ textShadow: '0 0 15px rgba(139,92,246,0.3)' }}>仪表盘</h1>
        <div className="glass-card p-8 text-center text-slate-500">请先在「数据上传」页面上传数据</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 控制栏 */}
      <div className="flex items-center justify-between px-4 py-3" style={{ background: 'rgba(10,10,30,0.8)', borderBottom: '1px solid rgba(139,92,246,0.1)' }}>
        <div className="flex items-center gap-3">
          {/* 模板切换 */}
          <div className="flex rounded-lg overflow-hidden border border-[#1a1f3a]">
            {TEMPLATES.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => setTemplate(tpl.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors ${
                  template === tpl.id
                    ? 'bg-[#8b5cf6]/20 text-[#a78bfa]'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
                title={tpl.desc}
              >
                <tpl.icon className="w-3.5 h-3.5" />
                {tpl.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 恢复默认 */}
          <button onClick={loadEChartsDashboard}
            className="px-2 py-1.5 text-xs rounded text-slate-500 hover:text-slate-300 transition-colors">
            恢复默认
          </button>

          {/* 加载已保存图表 */}
          <button onClick={handleLoadSaved} disabled={loading}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded bg-[#22d3ee]/10 border border-[#22d3ee]/20 text-[#22d3ee] hover:bg-[#22d3ee]/20 transition-colors">
            <FiSave className="w-3 h-3" />
            已制作图表
          </button>

          {/* 标题切换 */}
          <button onClick={() => setHideChartTitle(!hideChartTitle)}
            className={`px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
              hideChartTitle ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'text-slate-500 hover:text-slate-300'
            }`}>
            {hideChartTitle ? '📊 标题已隐藏' : '📊 显示标题'}
          </button>

          {/* PNG截图 + HTML导出 */}
          <button onClick={handleDownloadScreen} disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-l-lg bg-[#22d3ee]/20 border border-[#22d3ee]/20 text-[#22d3ee] hover:bg-[#22d3ee]/30 transition-colors"
            title="导出为 PNG 图片">
            <FiDownload className="w-3.5 h-3.5" />
            {downloading ? '截图中...' : 'PNG截图'}
          </button>
          <button onClick={handleExportHTML}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-r-lg bg-[#22d3ee]/20 border border-l-0 border-[#22d3ee]/20 text-[#22d3ee] hover:bg-[#22d3ee]/30 transition-colors"
            title="导出为可交互 HTML 文件">
            📄 HTML
          </button>
        </div>
      </div>

      {/* 大屏内容 */}
      <div className="flex-1 overflow-hidden" ref={screenRef}>
        {loading ? (
          <div className="flex items-center justify-center h-full"><div className="w-8 h-8 rounded-full border-2 border-[#8b5cf6] border-t-transparent animate-spin" /></div>
        ) : template === 'command' ? (
            <CommandScreen kpis={kpis} dataPreview={ds.preview} echarts={echarts} />
        ) : template === 'medical' ? (
            <MedicalDashboard cards={cards} meta={cardMeta || undefined} title={displayTitle} />
        ) : template === 'report' ? (
          /* 分析报告生成面板 */
          <div className="flex-1 flex items-center justify-center p-8" style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)' }}>
            <div className="max-w-2xl w-full text-center space-y-6 p-12 rounded-2xl bg-white shadow-lg border border-gray-200">
              <div className="text-6xl">📊</div>
              <h2 className="text-2xl font-bold text-gray-800">生成数据分析报告</h2>
              <p className="text-gray-500 leading-relaxed">
                AI 将基于<strong>精确统计数据</strong>，自动执行五阶段分析流水线，生成专业数据分析报告：
              </p>
              <div className="text-left text-sm text-gray-600 space-y-2 bg-gray-50 rounded-lg p-4">
                <div>🔍 <strong>阶段1-2</strong>：字段识别 → 图表规划（Python pandas 精确计算）</div>
                <div>📊 <strong>阶段3</strong>：统计分析 → 趋势/同比/TOP/异常/结构（代码计算）</div>
                <div>💡 <strong>阶段4</strong>：洞察生成 → 5类洞察（趋势/结构/集中度/异常/风险）</div>
                <div>📄 <strong>阶段5</strong>：报告生成 → 结构化报告（概览→指标→趋势→结构→TOP→异常→结论→建议）</div>
              </div>
              {!ds.apiKey && (
                <div className="text-sm text-orange-600 bg-orange-50 p-3 rounded-lg">
                  ⚠️ 请先在左上角配置 AI API Key，报告需要 AI 来编写分析洞察
                </div>
              )}
              <button
                onClick={handleExportReport}
                disabled={reportGenerating || !ds.apiKey}
                className="px-8 py-3 text-base font-semibold rounded-lg bg-gradient-to-r from-[#0d1b2a] to-[#1b4965] text-white hover:shadow-lg disabled:opacity-50 transition-all"
              >
                {reportGenerating ? `⏳ ${reportText}` : '🚀 生成分析报告并下载'}
              </button>
              {reportGenerating && (
                <p className="text-sm text-blue-600 animate-pulse">{reportText}</p>
              )}
              {reportError && (
                <p className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{reportError}</p>
              )}
              {!reportGenerating && !reportError && !ds.apiKey && (
                <p className="text-sm text-slate-400">（请先在左上角配置 AI API Key）</p>
              )}
            </div>
          </div>
        ) : (
            <EGridLayout kpis={kpis} echarts={echarts} title={displayTitle} hideChartTitle={hideChartTitle} tableData={ds.preview} />
        )}
      </div>

      {/* 报告预览 */}
      {reportHtml && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-8" onClick={() => setReportHtml('')}>
          <div className="w-full max-w-4xl h-[80vh] rounded-lg overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center px-4 py-2 bg-[#0f172a]">
              <span className="text-sm text-slate-300">分析报告</span>
              <button onClick={() => setReportHtml('')} className="text-slate-500 hover:text-white">✕</button>
            </div>
            <iframe srcDoc={reportHtml} className="w-full h-full border-0" sandbox="allow-scripts" />
          </div>
        </div>
      )}
    </div>
  );
}

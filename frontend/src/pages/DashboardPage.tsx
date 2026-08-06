/* DashboardPage - 大屏仪表盘（3模板 + AI推荐 + ECharts引擎） */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import html2canvas from 'html2canvas';
import { FiDownload, FiActivity, FiSave } from 'react-icons/fi';
import SmartDashboard from '../components/BigScreen/SmartDashboard';
import type { CardItem, CardMeta } from '../components/cardTypes';
import KPICards, { type KPIItem } from '../components/KPICards';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import { generateEChartsDashboardHTML, downloadEChartsHTML } from '../utils/exportEChartsDashboard';
import type { EChartItem } from '../types/api';

type TemplateType = 'medical';

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

const TEMPLATES: { id: TemplateType; label: string; icon: typeof FiActivity; desc: string }[] = [
  { id: 'medical', label: '数据看板', icon: FiActivity, desc: 'KPI数字 + 趋势图 + 雷达图 + 数据表格' },
];

export default function DashboardPage() {
  const { state: ds } = useData();
  const [searchParams] = useSearchParams();
  const isMock = searchParams.get('mock') === '1';
  const [template, setTemplate] = useState<TemplateType>('medical');
  const [kpis, setKpis] = useState<KPIItem[]>([]);
  const [echarts, setECharts] = useState<EChartItem[]>([]);
  const [chartTabs, setChartTabs] = useState<Record<string, EChartItem[]>>({
    '数据总览': [], '趋势洞察': [], '分类分析': [], '明细查询': [],
  });
  const [navTabs, setNavTabs] = useState<string[]>(['数据总览', '趋势洞察', '分类分析', '明细查询']);
  const [ringCharts, setRingCharts] = useState<Array<{ title: string; data: Array<{ name: string; value: number }> }>>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [hideChartTitle, setHideChartTitle] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [savedTableData, setSavedTableData] = useState<Record<string, unknown>[]>([]);

  // ──── 数据看板（medical / BigScreenDashboard）状态：来自 /dashboard/cards ────
  const [cards, setCards] = useState<CardItem[]>([]);
  const [cardsMeta, setCardsMeta] = useState<CardMeta | undefined>(undefined);
  const [cardsLoading, setCardsLoading] = useState(false);


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

  // ===== 加载数据看板卡片（medical / BigScreenDashboard，来自已保存分析包） =====
  const loadCards = useCallback(async () => {
    if (!hasData) { setCards([]); return; }
    setCardsLoading(true);
    try {
      const res = await api.generateCards(ds.sessionId);
      if (res && res.success) {
        setCards((res.cards as CardItem[]) || []);
        setCardsMeta(res.meta as CardMeta | undefined);
      } else {
        setCards([]);
      }
    } catch (err) {
      console.error('[Cards] 数据看板加载失败:', err);
      setCards([]);
    } finally {
      setCardsLoading(false);
    }
  }, [hasData, ds.sessionId]);

  // 切到「数据看板」时自动加载卡片
  useEffect(() => {
    if (template === 'medical') loadCards();
  }, [template, loadCards]);

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
                raw_data: (c.data || c.raw_data || []) as Record<string, unknown>[],
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
    } finally {
      setLoading(false);
      // 同步刷新数据看板卡片（卡片来自已保存分析包）
      loadCards();
    }
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
    // 数据看板(medical) 以 cards 为数据源；其余模板以 echarts 为数据源
    if (template === 'medical') {
      if (!cards || cards.length === 0) {
        alert('暂无数据看板内容，请先生成卡片');
        return;
      }
    } else if (echarts.length === 0) {
      alert('暂无图表数据');
      return;
    }
    const tableData = savedTableData.length > 0 ? savedTableData : (ds?.preview || []);
    const filename = `数据大屏_${displayTitle}_${new Date().toISOString().slice(0, 10)}.html`;
    // 数据看板（medical）导出以 cards 为数据源，与屏幕上 MedicalDashboard 一致
    const html = generateEChartsDashboardHTML(
      template, kpis, echarts, displayTitle, hideChartTitle, navTabs, ringCharts, tableData,
      undefined, undefined, undefined, 0, cards, cardsMeta,
    );
    downloadEChartsHTML(html, filename);
  };

  // ===== 分析包 JSON 下载 =====
  const handleDownloadPackages = async () => {
    if (!ds.sessionId) {
      alert('请先上传数据，再导出分析包。');
      return;
    }
    try {
      const res = await api.getSavedPackages(ds.sessionId);
      const packages = (res && (res as any).packages) || [];
      if (packages.length === 0) {
        alert('当前没有可导出的分析包，请先在「分析」页生成并收藏分析。');
        return;
      }
      const payload = {
        exported_at: new Date().toISOString(),
        total: (res as any).total ?? packages.length,
        packages,
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `分析包_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('导出分析包 JSON 失败：' + (e instanceof Error ? e.message : '未知错误'));
    }
  };

  // 标题：根据数据列名推断 → 兜底
  const displayTitle = inferIndustryTitle(ds.preview?.[0] ? Object.keys(ds.preview[0]) : ds.columnInfo?.map(c => c.name) || [])
    || '数据分析看板';

  // ★ mock=1 模式：跳转到 SmartDashboard 三模式预览（用真实已保存图表驱动）
  if (isMock) {
    return <SmartDashboard sessionId={ds.sessionId} mock={true} />;
  }

  if (!hasData) {
    return (
      <div className="page-enter">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">仪表盘</h1>
        <div className="glass-card p-8 text-center text-slate-500">请先在「数据上传」页面上传数据</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 控制栏 */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between px-4 py-3" style={{ background: 'rgba(255,255,255,0.35)', borderBottom: '1px solid rgba(255,255,255,0.50)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-3 flex-wrap">
          {/* 模板切换 */}
          <div className="flex rounded-lg overflow-hidden border border-white/40 bg-white/20 flex-wrap">
            {TEMPLATES.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => {
                  setTemplate(tpl.id);
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors ${
                  template === tpl.id
                    ? 'bg-white/50 text-[#0f172a] font-semibold'
                    : 'text-slate-600 hover:text-slate-800 hover:bg-white/30'
                }`}
                title={tpl.desc}
              >
                <tpl.icon className="w-3.5 h-3.5" />
                {tpl.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* 恢复默认 */}
          <button onClick={() => loadEChartsDashboard()}
            className="px-2 py-1.5 text-xs rounded text-slate-600 hover:text-slate-800 transition-colors">
            恢复默认
          </button>

          {/* 加载已保存图表 */}
          <button onClick={handleLoadSaved} disabled={loading}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded bg-white/40 border border-white/50 text-[#0f172a] hover:bg-white/60 transition-colors">
            <FiSave className="w-3 h-3" />
            已制作图表
          </button>

          {/* 标题切换 */}
          <button onClick={() => setHideChartTitle(!hideChartTitle)}
            className={`px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
              hideChartTitle ? 'bg-emerald-100 text-emerald-700 border border-emerald-300' : 'text-slate-600 hover:text-slate-800'
            }`}>
            {hideChartTitle ? '📊 标题已隐藏' : '📊 显示标题'}
          </button>

          {/* PNG截图 + HTML导出 */}
          <button onClick={handleDownloadScreen} disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-l-lg bg-white/40 border border-white/50 text-[#0f172a] hover:bg-white/60 transition-colors"
            title="导出为 PNG 图片">
            <FiDownload className="w-3.5 h-3.5" />
            {downloading ? '截图中...' : 'PNG截图'}
          </button>
          <button onClick={handleExportHTML}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-r-lg bg-white/40 border border-l-0 border-white/50 text-[#0f172a] hover:bg-white/60 transition-colors"
            title="导出为可交互 HTML 文件">
            📄 HTML
          </button>
          <button onClick={handleDownloadPackages}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/40 border border-white/50 text-[#0f172a] hover:bg-white/60 transition-colors"
            title="下载分析包 JSON 文件">
            📦 分析包JSON
          </button>
        </div>
      </div>

      {/* 大屏内容 */}
      <div className="flex-1 min-h-0 overflow-auto relative" ref={screenRef}>
        {loading ? (
          <div className="flex items-center justify-center h-full"><div className="w-8 h-8 rounded-full border-2 border-[#8B5CF6] border-t-transparent animate-spin" /></div>
        ) : (
            <SmartDashboard sessionId={ds.sessionId} mode="A" />
        )}
      </div>
    </div>
  );
}

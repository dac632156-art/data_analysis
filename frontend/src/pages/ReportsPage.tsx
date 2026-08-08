/* Reports - AI 分析报告生成与查看（浅色玻璃主题）
 * 渲染模型：一篇连续文档——报告总标题 + 各章节依次排列，每章=标题/连续正文/就近插图。
 * 图表由后端按章节 chart_titles 解析成 section_charts 嵌入 section，前端就近渲染，
 * 不再单独堆在末尾（呼应「形成一个整体」诉求）。
 */
import React, { useState, useRef } from 'react';
import { marked } from 'marked';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import { FiFileText, FiArrowUpRight } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { EtherealChart } from '../components/EtherealCharts/EtherealChart';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import {
  BarChart, LineChart, PieChart, FunnelChart, RadarChart, ScatterChart,
} from 'echarts/charts';
import {
  GridComponent, TitleComponent, TooltipComponent, LegendComponent,
  ToolboxComponent, DataZoomComponent, MarkLineComponent, GraphicComponent,
} from 'echarts/components';

echarts.use([
  CanvasRenderer,
  BarChart, LineChart, PieChart, FunnelChart, RadarChart, ScatterChart,
  GridComponent, TitleComponent, TooltipComponent, LegendComponent,
  ToolboxComponent, DataZoomComponent, MarkLineComponent, GraphicComponent,
]);
import type { PackageChartItem, ReportInsight } from '../types/api';
// ★ 报告导出复用仙气组件树 UMD（与数据看板导出共用同一份 ethereal-core.js）
// @ts-ignore - ?raw 在 vite/client 已声明
import etherealCoreJs from '../../dist-lib/ethereal-core.js?raw';

/** 报告页图表高度：等于各仙气图表组件自身默认的标准身高（360px），
 *  外部不再强制 '100%'（避免在无确定高度的卡片里塌缩成扁条）。 */
const REPORT_CHART_HEIGHT = 360;

interface ReportSection {
  type: string;
  title: string;
  content?: string;
  chart_titles?: string[];
  section_charts?: PackageChartItem[];
  insights?: Array<string | ReportInsight>;
}

const SECTION_ICON: Record<string, string> = {
  overview: '📋', kpi: '📊', trend: '📈', structure: '🏗️',
  top: '🏆', anomaly: '⚠️', conclusion: '💡', suggestions: '🚀', next_steps: '🎯',
};

/**
 * 把 content 拆成「块」：
 * 1. 先按 markdown 空行分段；
 * 2. 每段内若出现以 **粗体** 开头的小标题行，则从此处再拆成新块。
 * 这样即使 LLM 把多个小论点写在同一段，图也能紧跟对应小标题后的分析。
 */
function splitContentIntoBlocks(content: string): string[] {
  if (!content) return [];
  const paragraphs = content
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  const blocks: string[] = [];
  for (const para of paragraphs) {
    const lines = para.split(/\n/).map((l) => l.trim()).filter((l) => l.length > 0);
    let current = '';
    for (const line of lines) {
      // 以 **粗体** 开头的小标题行：把之前累积的内容作为一个块，然后新开一块
      if (/^\*\*[^*]+\*\*/.test(line) && current) {
        blocks.push(current.trim());
        current = line;
      } else {
        current += (current ? '\n' : '') + line;
      }
    }
    if (current) blocks.push(current.trim());
  }
  return blocks;
}

/** 归一化标题：NFKC + 去空白 + 小写 */
function normTitle(s: string): string {
  return (s || '')
    .normalize('NFKC')
    .replace(/\s+/g, '')
    .toLowerCase();
}

/** 提取标题中的核心关键词（去掉括号内容、标点），用于宽松匹配 */
function extractKeywords(s: string): string {
  return (s || '')
    .normalize('NFKC')
    .replace(/[（(][^)）]*[)）]/g, '')  // 去中文/英文括号内容
    .replace(/[^\u4e00-\u9fff\w]/g, '')  // 只留中文/字母/数字
    .replace(/\s+/g, '')
    .toLowerCase();
}

/** 判断段落是否提到某个图表标题（子串包含，归一化后匹配） */
function findChartsInParagraph(
  paragraph: string,
  charts: PackageChartItem[],
  rendered: Set<string>,
): PackageChartItem[] {
  const normPara = normTitle(paragraph);
  const found: PackageChartItem[] = [];
  for (const chart of charts) {
    if (!chart.title) continue;
    const slot = chart.slot || chart.title;
    if (rendered.has(slot)) continue;
    const nt = normTitle(chart.title);
    // 严格匹配：段落包含完整图表标题
    if (nt && (normPara.includes(nt) || nt.includes(normPara))) {
      found.push(chart);
      rendered.add(slot);
      continue;
    }
    // ★ 宽松匹配（Bug 3 修复）：LLM 可能用缩写/变体引用图表，
    //   提取核心关键词（去括号内容后），若关键词≥3 字且出现在段落中则匹配
    const kw = extractKeywords(chart.title);
    if (kw && kw.length >= 3) {
      const paraKw = extractKeywords(paragraph);
      if (paraKw.includes(kw) || kw.includes(paraKw)) {
        found.push(chart);
        rendered.add(slot);
      }
    }
  }
  return found;
}

/** 图表渲染卡片 */
function ChartCard({ chart, k, sectionIndex }: { chart: PackageChartItem; k: string; sectionIndex?: number }) {
  return (
    <div
      key={k}
      data-chart-slot={chart.slot}
      data-section-index={sectionIndex ?? -1}
      className="rounded-3xl overflow-hidden bg-white/60 border border-slate-200 w-full max-w-2xl"
    >
      <EtherealChart
        slot={chart.slot}
        chartType={chart.chart_type}
        chartNode={chart.option}
        data={chart.raw_data}
        title={chart.title}
        height={REPORT_CHART_HEIGHT}
      />
    </div>
  );
}

const escapeHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ★ waitChartsReady / captureChartImages 已移除：报告导出不再用截图方案，
//   改为将 ECharts option JSON 注入 HTML + CDN 实时渲染，与数据看板导出一致。
//   代码见 handleExportHTML 中「图表 option 注入」部分。

// 报告内 Markdown 局部样式（仅作用于本报告内容，不影响全局）
// 注意：content 由后端保证不含 Markdown 标题（层级由章节标题控制），h2/h3 仅作兜底样式。
const REPORT_MD_STYLE = `
.report-md { color: #334155; line-height: 1.7; }
.report-md h1, .report-md h2, .report-md h3 { font-weight: 700; color: #0f172a; margin: 0.6em 0 0.3em; line-height: 1.3; }
.report-md h1 { font-size: 1.15rem; }
.report-md h2 { font-size: 1.05rem; }
.report-md h3 { font-size: 0.98rem; }
.report-md p { margin: 0.5em 0; }
.report-md ul, .report-md ol { margin: 0.5em 0; padding-left: 1.25em; list-style: disc; }
.report-md ol { list-style: decimal; }
.report-md li { margin: 0.25em 0; }
.report-md strong { color: #1e293b; font-weight: 700; }
.report-md table { width: 100%; border-collapse: collapse; margin: 0.6em 0; font-size: 0.85rem; }
.report-md th, .report-md td { border: 1px solid #e2e8f0; padding: 0.4em 0.6em; text-align: left; }
.report-md th { background: #f8fafc; font-weight: 700; color: #334155; }
.report-md td { color: #475569; }
.report-md code { background: #f1f5f9; padding: 0.1em 0.3em; border-radius: 4px; font-size: 0.85em; }
`;

export default function ReportsPage() {
  const { state } = useData();
  const navigate = useNavigate();
  const [generating, setGenerating] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [reportTitle, setReportTitle] = useState('');
  const [error, setError] = useState('');
  const reqRef = useRef<number>(0);
  const [exporting, setExporting] = useState(false);

  const generate = async () => {
    if (!state.sessionId || !state.apiKey) return;
    const reqId = ++reqRef.current;
    setGenerating(true);
    setError('');
    setSections([]);
    setReportTitle('');
    setStatusText('🔍 正在进行数据统计分析（阶段1-3）...');

    // ★ 修复：报告严格基于「当前激活数据集」的包，而非整会话混合的 saved_packages。
    // 背景：sessionId 全局唯一、所有数据集共享；saved_packages 是 session 级混合列表，
    // 切数据集后 saved_packages 仍含旧数据，会导致报告误用旧数据。
    // 策略：从 saved_packages 取全量，前端按 dataset_id 过滤（分析页保存时携带 dataset_id）。
    let packages: Record<string, unknown>[] | undefined;
    const did = state.activeDatasetId;
    if (did) {
      try {
        const savedRes = await api.getSavedPackages(state.sessionId);
        const allPkgs: Record<string, unknown>[] =
          (savedRes as any).packages || (savedRes as any).data?.packages || [];
        const pkgs = Array.isArray(allPkgs)
          ? allPkgs.filter((p) => p.dataset_id === did)
          : [];
        if (pkgs.length === 0) {
          setError(
            '当前数据集暂无已保存的分析包。请先在「分析」页运行分析，并点击「保存到仪表盘」，再生成报告。',
          );
          setStatusText('');
          setGenerating(false);
          return;
        }
        packages = pkgs;
      } catch {
        // 取包失败时回退到后端 session 级 saved_packages（原行为）
      }
    }

    if (reqId !== reqRef.current) return;
    try {
      const provider = AI_PROVIDERS.find((p) => p.id === state.aiProvider);
      const result = await api.generateAIReport(
        state.sessionId,
        state.apiKey,
        provider?.baseUrl,
        provider?.model,
        packages,
      );
      if (reqId !== reqRef.current) return;
      const secs = result.sections || [];
      console.log('[ReportsPage] sections:', secs.length, 'first section_charts:', secs[0]?.section_charts?.length, 'total charts:', result.charts?.length);
      setSections(secs);
      // 报告标题：优先 LLM 生成的业务标题（如「2024年Q3电商转化分析报告」），无则兜底
      setReportTitle(result.report_title || '数据分析报告');
      setStatusText('✅ 报告生成完成');
    } catch (e: any) {
      if (reqId !== reqRef.current) return;
      setError(e?.message || '报告生成失败');
      setStatusText('');
    } finally {
      if (reqId === reqRef.current) setGenerating(false);
    }
  };

  const handleExportHTML = async () => {
    if (sections.length === 0) return;
    setExporting(true);
    try {
      // 1. 背景图 → base64
      let bgBase64 = '';
      try {
        const resp = await fetch('/report-bg.jpg');
        const blob = await resp.blob();
        bgBase64 = await new Promise<string>(r => {
          const reader = new FileReader();
          reader.onloadend = () => r(reader.result as string);
          reader.readAsDataURL(blob);
        });
      } catch {}

      // 2. ★ 收集所有图表：分配唯一 id，将 ECharts option 注入 HTML，
      //    导出时用 EtherealChart 组件渲染（跟页面一致，非裸 echarts.init）。
      //    Bug 5 修复：chart.slot 可能为空 → 用 index 兜底生成唯一 key。
      const chartRegistry: Array<{ id: string; chartType: string; option: any; title: string }> = [];
      const chartIdMap = new Map<string, string>();
      for (const sec of sections) {
        const secCharts = (sec.section_charts || []) as PackageChartItem[];
        for (let ci = 0; ci < secCharts.length; ci++) {
          const ch = secCharts[ci];
          if (!ch || !ch.option) continue;
          const key = ch.slot || (ch.title + '_' + ci);
          if (chartIdMap.has(key)) continue;
          const id = 'chart_' + chartRegistry.length;
          chartIdMap.set(key, id);
          chartRegistry.push({ id, chartType: ch.chart_type || '', option: ch.option, title: ch.title || '' });
        }
      }
      console.log(`[导出] 图表总数: ${chartRegistry.length}`);

      // 3. 构建 HTML body（段落级就近插图，与页面渲染一致）
      //    图表占位：<div id="chart_N"> 由渲染器里的 EtherealChart 填充
      let bodyHtml = `<h1 style="text-align:center;font-size:1.5rem;margin-bottom:1.5rem;">${escapeHtml(reportTitle || '数据分析报告')}</h1>`;
      for (const sec of sections) {
        bodyHtml += `<h2 style="font-size:1.1rem;font-weight:700;margin:1.5rem 0 0.5rem;color:#0f172a;">${escapeHtml(sec.title)}</h2>`;

        if (sec.content) {
          const secCharts = (sec.section_charts || []).filter((c) => c && c.option) as PackageChartItem[];
          const rendered = new Set<string>();
          const blocks = splitContentIntoBlocks(sec.content);

          for (const block of blocks) {
            bodyHtml += marked.parse(block) as string;
            const matched = findChartsInParagraph(block, secCharts, rendered);
            for (const ch of matched) {
              const key = ch.slot || (ch.title + '_' + secCharts.indexOf(ch));
              const cid = chartIdMap.get(key);
              if (cid) bodyHtml += `<div class="chart-card"><div id="${cid}" style="width:100%;height:420px;"></div></div>`;
            }
          }
          // 兜底：正文未引用的图放 section 末尾
          const remaining = secCharts.filter((c, ci) => !rendered.has(c.slot || c.title + '_' + ci));
          for (const ch of remaining) {
            const key = ch.slot || (ch.title + '_' + secCharts.indexOf(ch));
            const cid = chartIdMap.get(key);
            if (cid) bodyHtml += `<div class="chart-card"><div id="${cid}" style="width:100%;height:420px;"></div></div>`;
          }
        }
      }

      // 4. 序列化图表数据（注入 HTML 供渲染脚本使用）
      const chartsJson = JSON.stringify(chartRegistry.map(c => ({
        id: c.id, chartType: c.chartType, option: c.option, title: c.title,
      }))).replace(/<\/script>/gi, '<\\/script>');

      // 5. 组装完整 HTML：CDN React + 内联 UMD（EtherealChart 组件） + 渲染脚本
      //    与数据看板导出（exportComponentHTML/index.ts）共用同一份 ethereal-core.js，
      //    确保导出图表与页面像素级一致（水彩纹理/毛玻璃/渐变等仙气视觉）。
      const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(reportTitle || '数据分析报告')}</title>
<style>
  body { max-width:900px; margin:2rem auto; padding:0 1.5rem; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; color:#1e293b; line-height:1.75; }
${REPORT_MD_STYLE}
  .chart-card { width:100%; max-width:42rem; margin:1rem auto; }
</style>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script>
// ===== 仙气看板组件树 UMD（含 echarts/gl，与屏幕共用一份代码）=====
${etherealCoreJs as unknown as string}
</script>
</head>
<body>
${bgBase64 ? `<div style="position:fixed;inset:0;z-index:-1;background-image:url(${bgBase64});background-size:cover;background-position:center;background-repeat:no-repeat;opacity:0.6;"></div>` : ''}
${bodyHtml}
<script>
// ★ 报告图表渲染器：用 EtherealChart 组件渲染所有图表（与页面一致）
(function(){
  var React = window.React;
  var ReactDOM = window.ReactDOM;
  var Core = window.EtherealCore;
  if (!Core || !Core.EtherealChart) {
    console.error('[报告导出] EtherealCore 未就绪');
    return;
  }
  var charts = ${chartsJson};
  if (!charts || !charts.length) return;

  function renderAll() {
    charts.forEach(function(c) {
      var dom = document.getElementById(c.id);
      if (!dom) return;
      try {
        ReactDOM.createRoot(dom).render(
          React.createElement(Core.EtherealChart, {
            slot: c.id,
            chartType: c.chartType,
            chartNode: c.option,
            title: c.title,
            height: 420,
          })
        );
      } catch(e) { console.error('[报告图表] 渲染失败:', c.id, c.title, e); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', renderAll);
  else renderAll();
})();
</script>
</body>
</html>`;

      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportTitle || '数据分析报告'}.html`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('[导出 HTML]', e);
    } finally {
      setExporting(false);
    }
  };


  return (
    <div className="page-enter">
      <style>{REPORT_MD_STYLE}</style>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/70 border border-violet-200 text-violet-600 shadow-[0_4px_14px_rgba(139,92,246,0.18)]">
          <FiFileText className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports</h1>
          <p className="text-sm text-slate-500 mt-0.5">基于当前数据集生成 AI 数据分析报告</p>
        </div>
        {sections.length > 0 && (
          <button
            onClick={handleExportHTML}
            disabled={exporting}
            className="ml-auto px-4 py-2 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {exporting ? '导出中...' : '📄 导出 HTML'}
          </button>
        )}
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
            <article
              id="report-content"
              className="relative p-7 md:p-9 report-md rounded-2xl border border-white/50 shadow-lg overflow-hidden bg-white"
            >
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  backgroundImage: 'url(/report-bg.jpg)',
                  backgroundSize: 'contain',
                  backgroundPosition: 'center',
                  opacity: 0.6,
                }}
              />
              <div className="relative z-10">
                <h1 className="text-3xl font-bold text-slate-900 mb-6 text-center tracking-tight">{reportTitle}</h1>

                {sections.map((sec, i) => (
                  <section key={i} className="mb-7">
                    <h2 className="text-lg font-semibold text-slate-900 mb-2 flex items-center gap-2">
                      <span>{SECTION_ICON[sec.type] || '📄'}</span>
                      <span>{sec.title}</span>
                    </h2>

                  {sec.content && (() => {
                    const textBlocks = splitContentIntoBlocks(sec.content);
                    const visibleCharts = (sec.section_charts || []).filter((c) => c && c.option);
                    const rendered = new Set<string>();
                    const blocks: React.ReactNode[] = [];

                    textBlocks.forEach((block, bidx) => {
                      blocks.push(
                        <div
                          key={`p-${bidx}`}
                          className="text-sm text-slate-600 leading-relaxed"
                          dangerouslySetInnerHTML={{ __html: marked.parse(block) as string }}
                        />,
                      );
                      const matched = findChartsInParagraph(block, visibleCharts, rendered);
                      if (matched.length > 0) {
                        blocks.push(
                          <div
                            key={`charts-${bidx}`}
                            className="mt-4 flex flex-wrap justify-center gap-4"
                          >
                            {matched.map((chart) => (
                              <ChartCard key={`${i}-${chart.slot || bidx}`} chart={chart} k={`${i}-${chart.slot || bidx}`} sectionIndex={i} />
                            ))}
                          </div>,
                        );
                      }
                    });

                    // 兜底：正文中未被引用的图统一放在 section 末尾（避免 LLM 没提图名导致图丢失）
                    const remaining = visibleCharts.filter((c) => !rendered.has(c.slot || c.title || ''));
                    if (remaining.length > 0) {
                      blocks.push(
                        <div key="charts-remaining" className="mt-4 flex flex-wrap justify-center gap-4">
                        {remaining.map((chart, idx) => (
                          <ChartCard key={`${i}-rem-${idx}`} chart={chart} k={`${i}-rem-${idx}`} sectionIndex={i} />
                        ))}
                        </div>,
                      );
                    }

                    return <>{blocks}</>;
                  })()}
                </section>
              ))}
              </div>
            </article>
          )}
        </div>
      )}
    </div>
  );
}

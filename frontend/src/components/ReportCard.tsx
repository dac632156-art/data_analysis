/**
 * ReportCard —— ChatPage 对话流内联报告卡片。
 * 消费后端 generate_report 工具返回的 tool_result.data.report：
 *   { report_title, sections, packages_used, degradation, warning }
 * 每个 section 含 title / content(Markdown) / section_charts（已绑定完整 ECharts option）。
 */
import React, { useState } from 'react';
import { FileText, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { marked } from 'marked';
import EtherealChart from './EtherealCharts/EtherealChart';

interface ReportChart {
  title?: string;
  option?: Record<string, unknown>;
  chart_type?: string;
  slot?: string;
}
interface ReportSection {
  type?: string;
  title?: string;
  content?: string;
  insights?: string[];
  section_charts?: ReportChart[];
}
interface ReportData {
  report_title?: string;
  sections?: ReportSection[];
  packages_used?: number;
  degradation?: boolean;
  warning?: string;
}

function renderMarkdown(text: string): string {
  return marked.parse(text || '') as string;
}

const SECTION_ICON: Record<string, string> = {
  executive_summary: '执行摘要',
  trend: '趋势分析',
  structure: '结构分析',
  top: 'TOP 分析',
  anomaly: '异常分析',
  conclusion: '结论',
  suggestions: '建议',
  next_steps: '下一步',
};

const ReportCard: React.FC<{ report: ReportData }> = ({ report }) => {
  const sections = report.sections || [];
  const [openSet, setOpenSet] = useState<Set<number>>(
    () => new Set(sections.map((_, i) => i)),
  );

  const toggle = (i: number) =>
    setOpenSet((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <div className="mt-2 rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-[0_8px_30px_rgba(139,92,246,0.18)] overflow-hidden">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-violet-500/10 to-sky-400/5">
        <FileText className="w-4 h-4 text-violet-300" />
        <span className="text-sm font-semibold text-slate-100">
          {report.report_title || '数据分析报告'}
        </span>
        <span className="ml-auto text-[11px] text-slate-400">
          基于 {report.packages_used ?? 0} 份分析包
        </span>
      </div>

      {/* 降级/警告提示 */}
      {report.warning && (
        <div className="flex items-start gap-2 px-4 py-2 text-[12px] text-amber-300 bg-amber-500/10 border-b border-amber-400/20">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{report.warning}</span>
        </div>
      )}

      {/* 章节列表 */}
      <div className="divide-y divide-white/5">
        {sections.map((sec, i) => {
          const open = openSet.has(i);
          const charts = sec.section_charts || [];
          return (
            <div key={i} className="px-4 py-3">
              <button
                type="button"
                onClick={() => toggle(i)}
                className="w-full flex items-center gap-2 text-left cursor-pointer"
              >
                <span className="text-[13px] font-medium text-slate-200">
                  {sec.title || SECTION_ICON[sec.type || ''] || `章节 ${i + 1}`}
                </span>
                <span className="ml-auto text-[11px] text-slate-500">
                  {open ? '收起' : '展开'}
                </span>
              </button>

              {open && (
                <div className="mt-2">
                  {sec.content && (
                    <div
                      className="text-[13px] leading-relaxed text-slate-300 prose prose-invert max-w-none
                                 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_strong]:text-slate-100
                                 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(sec.content) }}
                    />
                  )}

                  {sec.insights && sec.insights.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {sec.insights.map((ins, j) => (
                        <li key={j} className="flex items-start gap-1.5 text-[12px] text-slate-400">
                          <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 text-emerald-400/70 shrink-0" />
                          <span>{ins}</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  {charts.length > 0 && (
                    <div className="mt-3 grid grid-cols-1 gap-3">
                      {charts.map((c, j) => (
                        <div
                          key={c.slot || j}
                          className="rounded-xl border border-white/10 bg-slate-950/40 p-2"
                        >
                          {c.title && (
                            <div className="text-[12px] text-slate-300 mb-1 px-1">{c.title}</div>
                          )}
                          <div className="h-[280px]">
                            {c.option ? (
                              <EtherealChart
                                chartType={c.chart_type || 'auto'}
                                chartNode={c.option as Record<string, unknown>}
                                title={c.title}
                              />
                            ) : (
                              <div className="flex items-center justify-center h-full text-[12px] text-slate-600">
                                该图表暂无可渲染数据
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ReportCard;

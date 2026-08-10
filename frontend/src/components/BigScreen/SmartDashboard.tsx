/**
 * SmartDashboard —— 三模式大屏预览（用真实已保存分析包驱动）
 *
 * 数据流（真实链路，无假数据）：
 *   sessionId → 后端 saved_packages (getSavedPackages)
 *   → 提取 pkg.rendered_charts / pkg.rendered_kpis / pkg.rendered_tables
 *   → 转为 SmartLayoutChart[] + KPI 列表
 *   → 三模式切换（聚拢 / 上下 / 压顶）→ reassignSlotsByMode 重排 slot
 *   → computeLayout 算 CSS Grid → 按 slot 渲染图表
 *
 * 用法：/dashboard?mock=1 → 跳到此组件（DashboardPage 在 mock 模式渲染它）。
 * 真实大屏（/dashboard，无 mock 参数）走旧 DashboardPage 的 5 模板（已还原）。
 *
 * ★ 关键：图表数据来自用户保存的分析包，与「真实大屏」的数据源完全一致，
 *   只是排版方式（三模式 ABC）不同。绝无假数据。
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { FiCpu, FiAlertTriangle } from 'react-icons/fi';
import * as api from '../../api/client';
import type { SmartLayoutItem, SmartLayoutChart } from '../../types/dashboard';
import type { ComputeLayoutResult, LayoutAssignment } from '../../layout/computeLayout';
import { computeLayout } from '../../layout/computeLayout';
import { renderSmartChart } from '../DashboardRenderer/ChartRegistry';
import MOCK_PACKAGES from './mockPackages';
// ★ 纯布局函数（含其依赖辅助函数/类型）已抽到独立 layout.ts，
// 避免导出函数 import 整个 SmartDashboard 组件树造成循环引用与重依赖。
import {
  buildSemanticLayout,
  extractChartsFromSavedPackages,
} from './layout';
import type { ChartLike } from './layout';

/**
 * 单图级错误边界 —— 隔离 ECharts StrictMode / HMR 卸载时的
 *   `Cannot read properties of null (reading 'getBoundingClientRect')` 等异常。
 */
class ChartErrorBoundary extends React.Component<
  { children: React.ReactNode; slot: string; chartType: string },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(err: any) {
    console.warn('[ChartErrorBoundary] 单图渲染降级:', this.props.slot, err?.message);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex items-center justify-center text-xs text-slate-600 bg-white/30">
          <div className="text-center">
            <FiAlertTriangle className="inline mr-1" />
            <span>图表 {this.props.chartType} 渲染降级</span>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

interface SmartDashboardProps {
  sessionId: string;
  mock?: boolean;
  mode: 'A' | 'B' | 'C';
  onModeChange?: (m: 'A' | 'B' | 'C') => void;
}

export default function SmartDashboard({ sessionId, mock, mode }: SmartDashboardProps) {
  const [data, setData] = useState<{ charts: SmartLayoutChart[]; items: SmartLayoutItem[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let packages: any[] = [];
      if (mock) {
        // ★ 模拟大屏：仅用第一包渲染（单包 ~10 张刚好匹配三模式蓝图槽位，
        //   避免 78 张图溢出到 overflowRow 撑爆布局）。三模式切换在工具条里即可预览。
        packages = (MOCK_PACKAGES as unknown as any[]).slice(0, 1);
      } else {
        if (!sessionId) {
          setError('缺少会话 ID，请先在「数据上传」页面上传数据');
          return;
        }
        // ★ 真实大屏：严格只读取用户已保存的分析包（saved_packages）
        const res: any = await api.getSavedPackages(sessionId);
        packages = (res && res.packages) || [];
      }
      if (packages.length === 0) {
        setError(
          mock
            ? '示例数据加载失败'
            : '暂无可视化内容，请先在「数据分析」页生成并收藏分析图表'
        );
        return;
      }
      const { charts, items } = extractChartsFromSavedPackages(packages);
      console.log('[SmartDashboard] 从 saved_packages 加载:', {
        packagesLen: packages.length,
        chartsLen: charts.length,
        itemsLen: items.length,
        chartTypeHistogram: charts.reduce<Record<string, number>>((acc, c) => {
          const k = (c.chart_type || '<空>').toString();
          acc[k] = (acc[k] || 0) + 1; return acc;
        }, {}),
        tableLikeCandidates: charts
          .filter((c) => /表|表格|明细|列表|清单|table|tabular|grid|cohort|retention|留存|同期群|同环比|行为/.test((c.title || '') + ' ' + (c.chart_type || '')))
          .map((c) => ({ slot: c.slot, type: c.chart_type, title: c.title, hasTableData: !!c.table_data, hasOption: !!c.option })),
      });
      setData({ charts, items });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载已保存分析包失败';
      console.error('[SmartDashboard] 加载失败:', msg);
      setError(`加载失败：${msg}`);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  // 按模式重新分配 slot + 直接生成 layout（语义化分配，绕开 computeLayout 蓝图）
  const remappedData = useMemo(() => {
    if (!data) return null;
    // ★ 直接把原始 data 交给 buildSemanticLayout；它内部会按 chart_type/title
    //   语义选择槽位（如 heatmap→6列、line→3列、kpi→顶栏等），
    //   并保证每个 chart 只被分配一次、slot 永不重复。
    const layoutResult = buildSemanticLayout(
      (data.charts || []) as ChartLike[],
      (data.items || []) as SmartLayoutItem[],
      mode
    );
    return {
      charts: data.charts as SmartLayoutChart[],
      items: data.items as SmartLayoutItem[],
      layout: layoutResult,
    };
  }, [data, mode]);

  const chartMap = useMemo(() => {
    const m: Record<string, SmartLayoutChart> = {};
    if (!remappedData) return m;
    (remappedData.charts || []).forEach((c) => {
      if (c && c.slot) m[c.slot] = c;
    });
    return m;
  }, [remappedData]);

  const layout = remappedData?.layout || null;

  // 诊断
  useEffect(() => {
    if (!layout || !remappedData) return;
    const slots = (remappedData.charts || []).map((c: any) => c.slot);
    const itemSlots = (remappedData.items || []).map((it: any) => it.slot);
    const missing = layout.assignments.filter((a: any) => !chartMap[a.slot]).map((a: any) => a.slot);
    const seen = new Set<string>();
    const dup: string[] = [];
    for (const s of [...itemSlots, ...slots]) {
      if (seen.has(s)) dup.push(s);
      seen.add(s);
    }
    console.log('[SmartDashboard:diagnostics]', {
      mode,
      chartsLen: (remappedData.charts || []).length,
      itemsLen: (remappedData.items || []).length,
      assignments: layout.assignments.length,
      missingAssignments: missing,
      duplicateSlots: Array.from(new Set(dup)),
      rowHeights: layout.rowHeights,
    });
  }, [layout, remappedData, chartMap, mode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-slate-700">
          <div className="w-9 h-9 rounded-full border-2 border-[#8B5CF6] border-t-transparent animate-spin" />
          <span className="text-sm">加载真实已保存图表…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="max-w-md text-center space-y-3 p-8 rounded-2xl bg-white/40 border border-white/50">
          <FiAlertTriangle className="w-8 h-8 mx-auto text-amber-500" />
          <p className="text-sm text-slate-600">{error}</p>
          <button onClick={() => load()}
            className="px-4 py-2 text-xs rounded-lg bg-white/60 border border-white/60 hover:bg-white/80 transition-colors">
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!remappedData || !layout || layout.assignments.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-sm">
        暂无图表可排版。
      </div>
    );
  }

  return (
    <div className="relative w-full" style={{ minHeight: '100%' }}>
      {/* 工具条：来源提示 + 三模式切换 */}
      <div className="sticky top-0 z-10 flex justify-between items-center px-4 py-3"
        style={{
          background: 'rgba(255,255,255,0.45)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
          borderBottom: '1px solid rgba(255,255,255,0.5)',
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[12px] text-slate-600">
            <FiCpu className="w-3.5 h-3.5 text-violet-500" />
            {mock
              ? `模拟大屏 · 示例数据预览 · ${remappedData.charts.length} 张`
              : `真实大屏 · 已保存图表 · ${remappedData.charts.length} 张`}
          </div>
          <div className="flex items-center gap-1 rounded-lg bg-white/50 border border-white/60 p-0.5 backdrop-blur-md">
            {(['A', 'B', 'C'] as const).map((mm) => (
              <button
                key={mm}
                onClick={() => onModeChange?.(mm)}
                className={`px-2.5 py-1 text-[11px] rounded-md transition-colors ${
                  mode === mm
                    ? 'bg-violet-500 text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white/80'
                }`}
                title={`模式${mm}：${mm === 'A' ? '核心聚拢式（图1）' : mm === 'B' ? '上图下表式（图2）' : '宽幅压顶式（图3）'}`}
              >
                {mm === 'A' ? '模式A 聚拢' : mm === 'B' ? '模式B 上下' : '模式C 压顶'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 主网格 */}
      <div
        className="grid gap-3 p-4 w-full mx-auto"
        style={{
          gridTemplateAreas: layout.gridTemplateAreas,
          gridTemplateRows: layout.rowHeights,
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gridAutoRows: '360px', // ★ 兜底：即便 maxRow 算少也不会出现 auto 行
          overflow: 'visible',
          maxWidth: '1920px',
        }}
      >
        {(() => {
          // ★ 防御：computeLayout 可能因上游 slot 重复产出相同 slot 的 assignment，
          //   这里按 slot 去重，保证 React key 绝对唯一（避免 duplicate key 报错）。
          const seenSlots = new Set<string>();
          return layout.assignments.map((a) => {
            if (seenSlots.has(a.slot)) return null;
            seenSlots.add(a.slot);
            const chart = chartMap[a.slot];
            // ★ 占位格子：蓝图每槽必占，缺图时画一个 no-data 占位框，不留空白
            if (!chart || (a as any).placeholder) {
              return (
                <div
                  key={a.slot}
                  style={{
                    gridArea: a.area,
                    minHeight: 0,
                    minWidth: 0,
                    height: '100%',
                    maxHeight: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                  }}
                  className="rounded-xl bg-white/35 border border-dashed border-white/50"
                >
                  <span className="text-[11px] text-slate-600">— 暂无图表 —</span>
                </div>
              );
            }
            return (
              <div
                key={a.slot}
                style={{
                  gridArea: a.area,
                  minHeight: 0,
                  minWidth: 0,
                  // ★ 关键：固定 height/maxHeight，避免父级 fr / 内容反撑
                  height: '100%',
                  maxHeight: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
                className="rounded-xl overflow-hidden bg-white/55 border border-white/60 backdrop-blur-md shadow-sm"
              >
                <ChartErrorBoundary slot={a.slot} chartType={a.chartType}>
                  <div className="w-full flex-1 min-h-0 min-w-0">
                    {renderSmartChart(chart)}
                  </div>
                </ChartErrorBoundary>
              </div>
            );
          });
        })()}
      </div>
    </div>
  );
}

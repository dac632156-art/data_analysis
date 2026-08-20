/**
 * BigScreenCard —— ChatPage 对话流内联数据大屏预览卡片。
 * 消费后端 generate_bigscreen 工具返回的 tool_result.data.bigscreen：
 *   { widgets: Widget.to_dict()[]（含 id/title/widget_type/chart_config/metadata/importance_score）, widget_count }
 * 复用 DashboardRenderer 的 WidgetFactory 渲染每个 Widget（图表/KPI/表格/洞察）。
 *
 * ★ 排版策略（与 RAG 骨架对齐）：
 *   - header 区（顶部 KPI 条）: grid-cols-2 sm:grid-cols-4，最多 4 个 KPI
 *   - main 区（主要分析 2 栏）: grid-cols-1 lg:grid-cols-2，最多 3 个核心图
 *   - secondary 区（辅助分析 3 栏）: grid-cols-1 md:grid-cols-2 lg:grid-cols-3
 *   - footer 区（底部表格/洞察）: 单列堆叠
 * 浅色玻璃主题，与 ChatPage 主体风格一致。
 */
import React from 'react';
import { LayoutDashboard } from 'lucide-react';
import { WidgetFactory } from './DashboardRenderer/WidgetFactory';

interface ScreenWidget {
  id?: string;
  widget_id?: string;
  title?: string;
  widget_type?: string;
  chart_config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  importance_score?: number;
  display_role?: string;
  preferred_size?: string;
}

type SlotZone = 'header' | 'main' | 'secondary' | 'footer';

const ZONE_TITLES: Record<SlotZone, string> = {
  header: '核心指标',
  main: '主要分析',
  secondary: '辅助分析',
  footer: '补充信息',
};

const BigScreenCard: React.FC<{ bigscreen: { widgets?: ScreenWidget[]; widget_count?: number } }> = ({
  bigscreen,
}) => {
  const widgets = bigscreen.widgets || [];

  // 统一 widget_id（Widget.to_dict 输出 id），并把 widget 投到 slot_zone 分组
  const slots = widgets.map((w) => ({
    ...w,
    widget_id: w.widget_id || w.id,
    _zone: ((w.metadata?.slot_zone as SlotZone) || 'secondary') as SlotZone,
  }));

  const groups: Record<SlotZone, typeof slots> = {
    header: [],
    main: [],
    secondary: [],
    footer: [],
  };
  for (const s of slots) {
    if (groups[s._zone]) groups[s._zone].push(s);
    else groups.secondary.push(s);
  }

  const hasAny = slots.length > 0;
  if (!hasAny) return null;

  return (
    <div className="mt-3 rounded-2xl border border-slate-200/80 bg-white/80 backdrop-blur-md shadow-[0_8px_30px_rgba(56,189,248,0.12)] overflow-hidden">
      {/* 标题栏 —— 浅色玻璃风 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200/70 bg-gradient-to-r from-sky-50 to-violet-50">
        <LayoutDashboard className="w-4 h-4 text-sky-600" />
        <span className="text-sm font-semibold text-slate-800">数据大屏预览</span>
        <span className="ml-auto text-[11px] text-slate-500">
          {bigscreen.widget_count ?? widgets.length} 个组件
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* ★ 顶部 KPI 条 */}
        {groups.header.length > 0 && (
          <section
            aria-label={ZONE_TITLES.header}
            className="grid grid-cols-2 sm:grid-cols-4 gap-3"
          >
            {groups.header.map((slot, i) => (
              <KpiShell key={slot.widget_id || i} slot={slot} />
            ))}
          </section>
        )}

        {/* ★ 主要分析 2 栏 */}
        {groups.main.length > 0 && (
          <section aria-label={ZONE_TITLES.main}>
            {groups.main.length > 0 && groups.main.some((s) => s.title) && (
              <ZoneHeader title={ZONE_TITLES.main} count={groups.main.length} />
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {groups.main.map((slot, i) => (
                <WidgetShell key={slot.widget_id || i} slot={slot} />
              ))}
            </div>
          </section>
        )}

        {/* ★ 辅助分析 3 栏 */}
        {groups.secondary.length > 0 && (
          <section aria-label={ZONE_TITLES.secondary}>
            <ZoneHeader title={ZONE_TITLES.secondary} count={groups.secondary.length} />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {groups.secondary.map((slot, i) => (
                <WidgetShell key={slot.widget_id || i} slot={slot} />
              ))}
            </div>
          </section>
        )}

        {/* ★ 底部表格/洞察 */}
        {groups.footer.length > 0 && (
          <section aria-label={ZONE_TITLES.footer}>
            <ZoneHeader title={ZONE_TITLES.footer} count={groups.footer.length} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {groups.footer.map((slot, i) => (
                <WidgetShell key={slot.widget_id || i} slot={slot} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

const ZoneHeader: React.FC<{ title: string; count: number }> = ({ title, count }) => (
  <div className="flex items-center gap-2 mb-2">
    <span className="inline-block w-1 h-3.5 rounded-sm bg-gradient-to-b from-sky-400 to-violet-400" />
    <span className="text-[12px] font-semibold text-slate-700">{title}</span>
    <span className="text-[11px] text-slate-400">· {count}</span>
  </div>
);

/**
 * KpiShell —— 顶部 KPI 条专用：紧凑卡片样式，强调数值
 */
const KpiShell: React.FC<{ slot: ScreenWidget & { widget_id: string } }> = ({ slot }) => (
  <div
    className="rounded-xl border border-slate-200/80 bg-gradient-to-br from-white to-sky-50/60
               shadow-sm hover:shadow-md hover:border-sky-300 transition-all p-3 min-h-[88px]
               flex flex-col justify-between"
  >
    <div className="text-[11px] font-medium text-slate-500 truncate">
      {slot.title || 'KPI'}
    </div>
    <WidgetFactory widget={slot as never} />
  </div>
);

/**
 * WidgetShell —— 普通图表/表格/洞察的容器
 */
const WidgetShell: React.FC<{ slot: ScreenWidget & { widget_id: string } }> = ({ slot }) => (
  <div
    className="rounded-xl border border-slate-200/80 bg-white shadow-sm
               hover:shadow-md hover:border-sky-300 transition-all overflow-hidden"
  >
    <WidgetFactory widget={slot as never} />
  </div>
);

export default BigScreenCard;

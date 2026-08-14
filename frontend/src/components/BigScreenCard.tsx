/**
 * BigScreenCard —— ChatPage 对话流内联数据大屏预览卡片。
 * 消费后端 generate_bigscreen 工具返回的 tool_result.data.bigscreen：
 *   { widgets: Widget.to_dict()[]（含 id/title/widget_type/chart_config/metadata/importance_score）, widget_count }
 * 复用 DashboardRenderer 的 WidgetFactory 渲染每个 Widget（图表/KPI/表格/洞察）。
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
}

const BigScreenCard: React.FC<{ bigscreen: { widgets?: ScreenWidget[]; widget_count?: number } }> = ({
  bigscreen,
}) => {
  const widgets = bigscreen.widgets || [];

  // WidgetFactory 需要 widget_id 字段（Widget.to_dict 输出 id），做一次映射。
  const slots = widgets.map((w) => ({ ...w, widget_id: w.widget_id || w.id }));

  return (
    <div className="mt-2 rounded-2xl border border-white/10 bg-gradient-to-br from-[#0F172A] to-[#020617] shadow-[0_8px_30px_rgba(56,189,248,0.18)] overflow-hidden">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-violet-500/10 to-sky-400/5">
        <LayoutDashboard className="w-4 h-4 text-sky-300" />
        <span className="text-sm font-semibold text-slate-100">数据大屏预览</span>
        <span className="ml-auto text-[11px] text-slate-400">
          {bigscreen.widget_count ?? widgets.length} 个组件
        </span>
      </div>

      {/* Widget 网格（暗色大屏观感） */}
      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {slots.map((slot, i) => (
          <div
            key={slot.widget_id || i}
            className="rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur-sm overflow-hidden
                       hover:border-violet-400/40 hover:shadow-[0_0_18px_rgba(139,92,246,0.25)] transition-all"
          >
            <WidgetFactory widget={slot as never} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default BigScreenCard;

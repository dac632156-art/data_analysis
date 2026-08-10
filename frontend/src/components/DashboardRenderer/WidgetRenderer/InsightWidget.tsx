import React, { memo } from 'react';
import type { WidgetSlot } from '../../../types/dashboard';
import { useDashboardTheme } from '../ThemeProvider';
import { useWidgetAnimation } from '../hooks';
import { FiZap, FiAlertTriangle, FiCheckCircle, FiInfo } from 'react-icons/fi';

interface InsightWidgetProps {
  widget: WidgetSlot;
  onFilter?: (field: string, value: string) => void;
  onClick?: (widgetId: string, data: Record<string, unknown>) => void;
  highlightLabel?: string | null;
  isCrossFilterSource?: boolean;
  hasDrillDown?: boolean;
  onDrillDown?: (widgetId: string, dimension: string, nextLevel: string) => void;
}

export const InsightWidget: React.FC<InsightWidgetProps> = memo(({ widget }) => {
  const theme = useDashboardTheme();
  const text = (widget.chart_config?.text as string) || (widget.metadata?.text as string) || widget.title;

  const { ref: animRef, animationClass, animationStyle } = useWidgetAnimation({
    type: 'fade-in',
    delay: (widget.importance_score % 5) * 70,
  });

  const score = widget.importance_score;
  const icon =
    score >= 80 ? <FiAlertTriangle className="w-4 h-4 text-amber-400" /> :
    score >= 60 ? <FiZap className="w-4 h-4 text-[#7c3aed]" /> :
    <FiInfo className="w-4 h-4 text-slate-600" />;

  return (
    <div ref={animRef}
      className={`${theme.cardBg} ${theme.cardBorder} border rounded-xl
        flex items-start gap-3 db-transition ${animationClass} ${theme.shadow}`}
      style={{
        padding: theme.cardPadding,
        borderRadius: theme.borderRadius,
        ...animationStyle,
      }}
    >
      <div className="mt-0.5 flex-shrink-0">{icon}</div>
      <div>
        <div className={`text-xs font-semibold mb-1 ${theme.textSecondary}`}>{widget.title}</div>
        <div className={`text-sm leading-relaxed ${theme.text}`}>{text}</div>
      </div>
    </div>
  );
});

InsightWidget.displayName = 'InsightWidget';

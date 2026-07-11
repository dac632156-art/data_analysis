import React, { Component, ErrorInfo } from 'react';
import type { WidgetError } from '../../types/dashboard';

/**
 * WidgetErrorBoundary —— Widget 错误隔离
 *
 * 如果某个 Widget 渲染失败，不要整个 Dashboard 崩溃。
 * 自动显示 Widget Error 占位。
 */

interface Props {
  widgetId: string;
  children: React.ReactNode;
  onError?: (error: WidgetError) => void;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export class WidgetErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, errorMessage: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error.message || '渲染失败' };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[WidgetErrorBoundary] Widget ${this.props.widgetId} 渲染失败:`, error, info);
    this.props.onError?.({
      widget_id: this.props.widgetId,
      message: error.message,
      timestamp: Date.now(),
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full min-h-[120px] p-6
          rounded-xl border border-red-500/20 bg-red-500/[0.04] text-center">
          <div className="text-2xl mb-2">⚠️</div>
          <p className="text-xs text-red-400 font-medium">Widget 渲染失败</p>
          <p className="text-[10px] text-slate-500 mt-1 max-w-[200px]">{this.state.errorMessage}</p>
          <p className="text-[10px] text-slate-600 mt-2">ID: {this.props.widgetId}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ErrorBoundary - 全局错误边界 */
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error);
    console.error('[ErrorBoundary] Component stack:', info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="p-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
          <h3 className="font-semibold mb-2">页面渲染出错</h3>
          <p className="text-sm opacity-80">{this.state.error?.message}</p>
          <button
            className="mt-3 px-4 py-1.5 text-sm rounded bg-red-500/20 hover:bg-red-500/30 transition-colors"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

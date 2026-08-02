/* ErrorBoundary - 全局错误边界 */
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  resetKey: number;  // 改变此值强制 children 完全重新挂载，避免残留 DOM 引用导致 insertBefore 报错
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, resetKey: 0 };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error);
    console.error('[ErrorBoundary] Component stack:', info.componentStack);
  }

  handleReset = () => {
    // 重置错误状态并递增 resetKey，强制 children 完全卸载后重新挂载（清空残留 DOM 引用）
    this.setState((prev) => ({ hasError: false, error: null, resetKey: prev.resetKey + 1 }));
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="p-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
          <h3 className="font-semibold mb-2">页面渲染出错</h3>
          <p className="text-sm opacity-80">{this.state.error?.message}</p>
          <button
            className="mt-3 px-4 py-1.5 text-sm rounded bg-red-500/20 hover:bg-red-500/30 transition-colors"
            onClick={this.handleReset}
          >
            重试
          </button>
        </div>
      );
    }
    // key 改变时 React 会完全卸载旧子树并重新挂载，杜绝残留 DOM 引用
    return <React.Fragment key={this.state.resetKey}>{this.props.children}</React.Fragment>;
  }
}

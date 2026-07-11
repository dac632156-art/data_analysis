/* Layout - 全局布局 */
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import StarBackground from './StarBackground';
import ErrorBoundary from '../ErrorBoundary';

export default function Layout() {
  return (
    <div className="min-h-screen relative bg-[#020617]">
      <StarBackground />
      <Sidebar />
      {/* translate="not" 阻止浏览器翻译插件修改此区域 DOM，防止 React 虚拟 DOM 引用失效导致 insertBefore 崩溃 */}
      <main className="ml-64 h-screen p-6 relative z-10 flex flex-col" translate="no">
        <div className="max-w-7xl mx-auto w-full flex-1 page-enter notranslate">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

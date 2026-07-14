/* Layout - 全局布局 */
import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import StarBackground from './StarBackground';
import ErrorBoundary from '../ErrorBoundary';

export default function Layout() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar-collapsed') === '1';
    } catch {
      return false;
    }
  });

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem('sidebar-collapsed', next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen relative bg-[#020617]">
      <StarBackground />
      <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} />
      {/* translate="not" 阻止浏览器翻译插件修改此区域 DOM，防止 React 虚拟 DOM 引用失效导致 insertBefore 崩溃 */}
      <main
        className={`${collapsed ? 'ml-20' : 'ml-64'} h-screen p-6 relative z-10 flex flex-col transition-all duration-300`}
        translate="no"
      >
        <div className="max-w-7xl mx-auto w-full flex-1 page-enter notranslate">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

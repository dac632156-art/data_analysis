/* Layout - 全局布局（浅色玻璃拟态） */
import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { FiMenu } from 'react-icons/fi';
import Sidebar from './Sidebar';
import ErrorBoundary from '../ErrorBoundary';
import AuthButton from '../AuthButton';

export default function Layout() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar-collapsed') === '1';
    } catch {
      return false;
    }
  });
  // 移动端抽屉侧边栏开关（与桌面端 collapsed 无关）
  const [mobileOpen, setMobileOpen] = useState(false);

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
    <div className="min-h-screen relative">
      <div className="bg-layer" />
      <Sidebar
        collapsed={collapsed}
        onToggle={toggleCollapsed}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />
      {/* translate="not" 阻止浏览器翻译插件修改此区域 DOM，防止 React 虚拟 DOM 引用失效导致 insertBefore 崩溃 */}
      <main
        className={`${collapsed ? 'md:ml-20' : 'md:ml-64'} ml-0 h-screen p-4 md:p-6 relative z-10 flex flex-col transition-all duration-300`}
        translate="no"
      >
        {/* 移动端汉堡按钮：仅小屏显示，用于唤出侧边栏抽屉 */}
        <div className="md:hidden flex items-center justify-between gap-2 mb-3 -ml-1">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="打开菜单"
            className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-white/60 transition-colors glass-panel"
          >
            <FiMenu className="w-5 h-5" />
          </button>
          <AuthButton />
        </div>
        {/* 桌面端右上角登录按钮 */}
        <div className="hidden md:flex absolute top-4 right-6 z-20">
          <AuthButton />
        </div>
        <div className="max-w-7xl mx-auto w-full flex-1 page-enter notranslate">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

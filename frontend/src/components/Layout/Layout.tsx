/* Layout - 全局布局 */
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import StarBackground from './StarBackground';

export default function Layout() {
  return (
    <div className="min-h-screen relative bg-[#020617]">
      <StarBackground />
      <Sidebar />
      <main className="ml-64 min-h-screen p-6 relative z-10">
        <div className="max-w-7xl mx-auto page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

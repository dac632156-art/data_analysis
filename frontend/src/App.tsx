/* DataMind AI - 应用入口与路由 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DataProvider } from './contexts/DataContext';
import Layout from './components/Layout/Layout';
import UploadPage from './pages/UploadPage';
import CleanPage from './pages/CleanPage';
import AnalysisPage from './pages/AnalysisPage';
import DashboardPage from './pages/DashboardPage';
import EtherealPreview from './EtherealPreview';
import AIModelsPage from './pages/AIModelsPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import CoverPage from './pages/CoverPage';
import ChatPage from './pages/ChatPage';

export default function App() {
  return (
    <BrowserRouter>
      <DataProvider>
        <Routes>
          {/* 封面为独立全屏页：自带暗色左侧栏，不套 Layout（避免浅色 Sidebar 拼黑底） */}
          <Route path="/" element={<CoverPage />} />
          {/* 独立智能体：不套 Layout，无侧边栏，纯全屏对话体验 */}
          <Route path="/chat" element={<ChatPage />} />
          <Route element={<Layout />}>
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/clean" element={<CleanPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/ethereal-preview" element={<EtherealPreview />} />
            <Route path="/models" element={<AIModelsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </DataProvider>
    </BrowserRouter>
  );
}

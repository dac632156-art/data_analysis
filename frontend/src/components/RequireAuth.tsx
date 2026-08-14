import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { REDIRECT_KEY } from '../lib/api';

/** 路由守卫：未登录跳转 /login，并记录来源路径以便登录后回跳。 */
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) {
    // 初始恢复中，先渲染空（避免闪烁/误判）
    return <div className="min-h-screen flex items-center justify-center text-slate-400">加载中…</div>;
  }

  if (!user) {
    // 记录当前路径，供登录成功后回跳
    sessionStorage.setItem(REDIRECT_KEY, location.pathname + location.search + location.hash);
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export default RequireAuth;

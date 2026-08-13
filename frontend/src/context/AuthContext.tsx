import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  TOKEN_KEY, REFRESH_TOKEN_KEY, REDIRECT_KEY,
  authLogin, authRegister, authLogout, authMe, refreshAuth,
} from '../lib/api';
import { AUTH_LOGOUT_EVENT, AUTH_LOGIN_EVENT } from '../contexts/DataContext';

interface AuthUser { id: number; username: string; }
interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  ready: boolean;            // 是否已完成初始恢复（避免守卫提前误判）
  login: (username: string, password: string, sessionId?: string) => Promise<void>;
  register: (username: string, password: string, sessionId?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // 初始恢复：有 access token 则恢复；access 过期但有 refresh token 则静默续期
  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (t) {
      setToken(t);
      authMe()
        .then((u) => setUser(u))
        .catch(async () => {
          // access 失效：尝试用 refresh 续期
          if (rt) {
            const nt = await refreshAuth();
            if (nt) {
              setToken(nt);
              try {
                const u = await authMe();
                setUser(u);
                return;
              } catch {
                /* 落到下方清除 */
              }
            }
          }
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(REFRESH_TOKEN_KEY);
          setToken(null);
        })
        .finally(() => setReady(true));
    } else {
      setReady(true);
    }
  }, []);

  const persist = (token: string, refreshToken: string, user: AuthUser, sessionId?: string | null) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    setToken(token);
    setUser(user);
    // 把后端分配的 sessionId 写回 localStorage 并通知 DataContext 同步 React state，
    // 避免游客 sessionId 仍指向 user_id=NULL 的旧会话（冷启动清理会把它误删）。
    if (sessionId) {
      localStorage.setItem('sessionId', sessionId);
    }
  };

  const login = useCallback(async (username: string, password: string, sessionId?: string) => {
    const res = await authLogin(username, password, sessionId);
    persist(res.token, res.refresh_token, res.user, res.session_id);
    // 通知 DataContext 同步本次登录后的 sessionId（用于保证 React state 与 localStorage 一致）
    if (res.session_id) {
      window.dispatchEvent(new CustomEvent(AUTH_LOGIN_EVENT, { detail: { sessionId: res.session_id } }));
    }
  }, []);

  const register = useCallback(async (username: string, password: string, sessionId?: string) => {
    // 建议 2：注册成功自动登录（后端直接返回 token）
    const res = await authRegister(username, password, sessionId);
    persist(res.token, res.refresh_token, res.user, res.session_id);
    if (res.session_id) {
      window.dispatchEvent(new CustomEvent(AUTH_LOGIN_EVENT, { detail: { sessionId: res.session_id } }));
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      if (token) await authLogout();
    } catch {
      // 即使后端失败也清除本地态
    }
    // 重要：登出时不要调 clearData(sid) 清服务端数据。
    // 该 session 在登录时已被 reassign 到当前 user_id，登出后仍归该用户所有，
    // 数据需保留以便"历史会话"能恢复上次分析。继续依赖 DataContext 派发的
    // CLEAR_DATA 清前端 React state 即可（实现"登出后分析页为空"的同时不丢数据）。
    // 仅删本地 sessionId/tokens 防止本设备他人以同 sessionId 拉到旧数据。
    localStorage.removeItem('sessionId');
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setToken(null);
    setUser(null);
    // 通知 DataContext 清掉本设备的所有业务数据（datasets/apiKey/分析结果等），
    // 避免 React state 里仍残留上一个用户上传的文件。
    window.dispatchEvent(new CustomEvent(AUTH_LOGOUT_EVENT));
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 <AuthProvider> 内使用');
  return ctx;
}

// 登录成功后调用：优先回跳到登录前页面，否则回首页
export function consumePostLoginRedirect(): string | null {
  const r = sessionStorage.getItem(REDIRECT_KEY);
  if (r) sessionStorage.removeItem(REDIRECT_KEY);
  return r;
}

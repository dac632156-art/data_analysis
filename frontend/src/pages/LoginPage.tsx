import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { User, Lock, AlertCircle } from 'lucide-react';
import { useAuth, consumePostLoginRedirect } from '../context/AuthContext';
import AuthBrandLogo from '../components/AuthBrandLogo';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username || !password) {
      setError('请输入用户名和密码');
      return;
    }
    setLoading(true);
    try {
      const sessionId = localStorage.getItem('sessionId') || undefined;
      await login(username, password, sessionId);
      const redirect = consumePostLoginRedirect();
      // 登录成功的默认落地页：进入应用主界面（上传页），与 cover 上"免费开始"入口一致。
      const target = redirect && redirect !== '/login' && redirect !== '/'
        ? redirect
        : '/upload';
      navigate(target, { replace: true });
    } catch (err: any) {
      setError(err?.message || '登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{
        backgroundImage: "url('/auth-bg.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* 极浅色温润，提升玻璃卡片可读但不压暗背景 */}
      <div className="absolute inset-0 bg-white/8" />
      {/* 底部青紫光圈呼吸（动效档 B） */}
      <div className="aurora-pulse" />

      <div className="relative z-10 w-[420px] max-w-[92vw] page-enter">
        <div className="auth-card rounded-3xl p-9">
          <div className="flex items-center justify-center gap-2.5 mb-6">
            <AuthBrandLogo size={36} />
            <span className="text-[20px] font-semibold tracking-tight text-slate-900">DataMind AI</span>
          </div>

          <h2 className="text-[22px] font-bold text-center text-slate-900 mb-1">Login to Your Account</h2>
          <p className="text-sm text-center text-slate-500 mb-7">欢迎回来，登录以归集你的分析数据</p>

          {error && (
            <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-xl bg-red-50 text-red-600 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            <div className="auth-input-wrap">
              <User className="auth-input-icon" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名"
                className="auth-input"
                autoFocus
              />
            </div>
            <div className="auth-input-wrap">
              <Lock className="auth-input-icon" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="密码"
                className="auth-input"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="auth-submit"
            >
              {loading ? '登录中…' : 'Login'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-600">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="font-semibold text-violet-600 hover:underline">
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
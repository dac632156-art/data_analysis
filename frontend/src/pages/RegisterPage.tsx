import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { User, Lock, AlertCircle } from 'lucide-react';
import { useAuth, consumePostLoginRedirect } from '../context/AuthContext';
import AuthBrandLogo from '../components/AuthBrandLogo';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (username.length < 3) {
      setError('用户名至少 3 位（字母、数字、下划线或中文）');
      return;
    }
    if (password.length < 6) {
      setError('密码至少 6 位');
      return;
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      // 与登录一致：带上当前游客 sessionId（若有），让后端尝试回填或新建会话并绑定到新用户。
      const sessionId = localStorage.getItem('sessionId') || undefined;
      await register(username, password, sessionId);
      const redirect = consumePostLoginRedirect();
      navigate(redirect && redirect !== '/register' ? redirect : '/', { replace: true });
    } catch (err: any) {
      setError(err?.message || '注册失败，请重试');
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
      <div className="absolute inset-0 bg-white/8" />
      <div className="aurora-pulse" />

      <div className="relative z-10 w-[420px] max-w-[92vw] page-enter">
        <div className="auth-card rounded-3xl p-9">
          <div className="flex items-center justify-center gap-2.5 mb-6">
            <AuthBrandLogo size={36} />
            <span className="text-[20px] font-semibold tracking-tight text-slate-900">DataMind AI</span>
          </div>

          <h2 className="text-[22px] font-bold text-center text-slate-900 mb-1">Create Your Account</h2>
          <p className="text-sm text-center text-slate-500 mb-7">注册即归集你的分析数据，跨会话永不丢失</p>

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
                placeholder="用户名（3-32 位字母/数字/下划线/中文）"
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
                placeholder="密码（至少 6 位）"
                className="auth-input"
              />
            </div>
            <div className="auth-input-wrap">
              <Lock className="auth-input-icon" />
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="确认密码"
                className="auth-input"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="auth-submit"
            >
              {loading ? '注册中…' : 'Sign Up'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-600">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-violet-600 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
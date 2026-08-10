/* CleanPage - 数据清洗 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
import { FiAlertTriangle, FiCheck, FiTrash2, FiRefreshCw, FiRotateCcw, FiZap, FiLoader, FiDownload } from 'react-icons/fi';
import DataTable from '../components/DataTable';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';
import type { AICleanStatusResponse } from '../types/api';

export default function CleanPage() {
  const { state: ds, dispatch: dd } = useData();

  const [preview, setPreview] = useState<Record<string, unknown>[]>(ds.preview);
  const [messages, setMessages] = useState<{ type: 'success' | 'error'; text: string }[]>([]);
  const [selectedColumn, setSelectedColumn] = useState('');
  const [missingMethod, setMissingMethod] = useState('fill_mean');
  const [outlierMethod, setOutlierMethod] = useState('iqr');
  const [outlierAction, setOutlierAction] = useState('remove');
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiTask, setAiTask] = useState<AICleanStatusResponse | null>(null);
  const pollRef = useRef<number | null>(null);

  // 用 columnInfo/fileName 判断是否有数据，而不是 rows（清洗删行时 rows 会变导致 hasData 翻转、DOM 树整体卸载重挂）
  const hasData = ds.columnInfo.length > 0 || !!ds.fileName;
  const columns = ds.columnInfo.map((c) => c.name);

  const addMessage = (type: 'success' | 'error', text: string) => {
    setMessages((prev) => [...prev.slice(-4), { type, text }]);
  };

  const refreshAllData = useCallback(async () => {
    // 先并行获取所有数据，再一次性更新状态（避免多次中间渲染导致 insertBefore）
    const [previewRes, colRes] = await Promise.allSettled([
      api.getDataPreview(ds.sessionId),
      api.getColumnInfo(ds.sessionId),
    ]);

    // 同一个同步块中更新所有状态 → React 只渲染一次
    if (previewRes.status === 'fulfilled') {
      setPreview(previewRes.value.preview);
      dd({ type: 'SET_PREVIEW', preview: previewRes.value.preview });
    } else {
      addMessage('error', '刷新预览失败');
      return;
    }
    if (colRes.status === 'fulfilled' && colRes.value.columns) {
      const columnInfo = colRes.value.columns.map((c: Record<string, unknown>) => ({
        name: String(c.name ?? ''),
        dtype: String(c.dtype ?? ''),
        missing: Number(c.missing ?? 0),
        missing_rate: Number(c.missing_rate ?? 0),
        unique: Number(c.unique ?? 0),
        sample: String(c.sample ?? ''),
      }));
      dd({ type: 'SET_DATA', payload: { columnInfo } });
      window.dispatchEvent(new Event('columns-updated'));
    }
  }, [ds.sessionId, dd]);

  const handleMissing = async () => {
    if (!selectedColumn) { addMessage('error', '请先选择列'); return; }
    try {
      await api.handleMissing(ds.sessionId, selectedColumn, missingMethod);
      addMessage('success', `已处理 ${selectedColumn} 的缺失值（${getMethodLabel(missingMethod)}）`);
      await refreshAllData();
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '处理失败');
    }
  };

  const pollAiClean = useCallback(async (taskId: string) => {
    try {
      const status = await api.getAiCleanStatus(taskId);
      setAiTask(status);
      if (status.status === 'running') {
        pollRef.current = window.setTimeout(() => pollAiClean(taskId), 1500);
      } else {
        // 任务结束（完成/出错）→ 刷新当前激活表预览与列信息
        setAiLoading(false);
        pollRef.current = null;
        await refreshAllData();
      }
    } catch {
      setAiLoading(false);
      pollRef.current = null;
    }
  }, [refreshAllData]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  const handleAiClean = async () => {
    if (!aiInput.trim()) return;
    if (!ds.apiKey) { addMessage('error', '请先在左上角配置 AI API Key'); return; }
    const provider = AI_PROVIDERS.find(p => p.id === ds.aiProvider);
    if (!provider) { addMessage('error', '请先在左上角选择 AI 模型提供商'); return; }
    setAiLoading(true);
    setAiTask(null);
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
    try {
      const res = await api.aiClean(
        ds.sessionId, aiInput, ds.apiKey,
        ds.customBaseUrl || provider.baseUrl, ds.customModel || provider.model,
      );
      addMessage('success', `已提交 AI 清洗任务，共 ${res.total} 个处理单元`);
      pollAiClean(res.task_id);
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : 'AI清洗提交失败');
      setAiLoading(false);
    }
  };

  const handleOutliers = async () => {
    if (!selectedColumn) { addMessage('error', '请先选择列'); return; }
    try {
      const actionLabel = outlierAction === 'remove' ? '已删除' : '已将异常值拉回边界';
      await api.handleOutliers(ds.sessionId, selectedColumn, outlierMethod, outlierAction);
      addMessage('success', `${actionLabel} ${selectedColumn} 的异常值`);
      await refreshAllData();
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '处理失败');
    }
  };

  const handleResetData = async () => {
    if (!window.confirm('确认要恢复到上传时的原始数据吗？所有清洗操作将被撤销。')) return;
    try {
      const res = await api.resetData(ds.sessionId);
      // 统一通过 refreshAllData 刷新，避免多次 setPreview 冲突
      dd({ type: 'SET_PREVIEW', preview: res.preview });
      await refreshAllData();
      addMessage('success', '已恢复原始数据');
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '恢复失败');
    }
  };

  const handleDownload = async (original: boolean) => {
    try {
      await api.downloadCSV(ds.sessionId, original);
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '下载失败');
    }
  };

  const handleConvertType = async (targetType: string) => {
    if (!selectedColumn) { addMessage('error', '请先选择列'); return; }
    const typeLabels: Record<string, string> = { datetime: '日期时间', numeric: '数值', string: '字符串', category: '分类' };
    try {
      await api.convertColumnType(ds.sessionId, selectedColumn, targetType);
      addMessage('success', `已将 ${selectedColumn} 转换为 ${typeLabels[targetType] || targetType}`);
      await refreshAllData();
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '转换失败');
    }
  };

  const handleUndo = async () => {
    try {
      const res = await api.undoLastAction(ds.sessionId);
      // 统一通过 refreshAllData 刷新，避免多次 setPreview 冲突
      dd({ type: 'SET_PREVIEW', preview: res.preview });
      await refreshAllData();
      addMessage('success', `已撤销，剩余可撤销 ${res.remain_undo} 步`);
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : '撤销失败');
    }
  };

  return (
    <div className="page-enter space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800"
            style={{ textShadow: '0 0 15px rgba(124,58,237,0.3)' }}
          >
            数据清洗
          </h1>
          <p className="text-[#94a3b8] text-sm mt-1">处理缺失值、异常值、数据类型等数据质量问题</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleDownload(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-green-500/30 text-green-400 hover:bg-green-500/10 transition-colors"
            title="下载上传时的原始数据"
          >
            <FiDownload className="w-4 h-4" /> 原始数据
          </button>
          <button
            onClick={() => handleDownload(false)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors"
            title="下载清洗后的当前数据"
          >
            <FiDownload className="w-4 h-4" /> 清洗后数据
          </button>
          <button
            onClick={handleUndo}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10 transition-colors"
            title="撤销上一步操作"
          >
            <FiRotateCcw className="w-4 h-4" /> 撤销
          </button>
        </div>
      </div>

      {hasData ? (
        <>
          {/* AI 智能清洗面板 */}
          <div className="glass-card p-4 space-y-3" style={{ borderColor: 'rgba(124,58,237,0.3)' }}>
            <h3 className="text-sm font-semibold text-[#7c3aed] flex items-center gap-2">
              <FiZap className="w-4 h-4" /> AI 智能清洗
              <span className="text-[10px] text-slate-500 font-normal">— 用自然语言告诉AI你要如何清洗数据</span>
            </h3>
            <div className="flex gap-2">
              <input
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAiClean()}
                placeholder="例如：把缺失值用均值填充、把日期列转为日期类型、删除利润率大于200%的异常值..."
                className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 placeholder-slate-600 focus:outline-none focus:border-[#7c3aed]/50"
              />
              <button onClick={handleAiClean} disabled={aiLoading || !aiInput.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-[#7c3aed]/20 border border-[#7c3aed]/30 text-[#7c3aed] hover:bg-[#7c3aed]/30 disabled:opacity-50 transition-colors">
                {aiLoading ? <FiLoader className="w-4 h-4 animate-spin" /> : <FiZap className="w-4 h-4" />}
                {aiLoading ? '分析中...' : '执行'}
              </button>
            </div>

            {/* AI 清洗进度（异步多单元）*/}
            {aiTask && (
              <div className="p-3 rounded-lg space-y-3" style={{ background: 'rgba(124,58,237,0.059)', border: '1px solid rgba(124,58,237,0.15)' }}>
                {/* 总览条 */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-600">
                    已完成 {aiTask.completed} / 共 {aiTask.total} 个处理单元
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    aiTask.status === 'done' ? 'bg-emerald-500/15 text-emerald-400'
                    : aiTask.status === 'error' ? 'bg-red-500/15 text-red-400'
                    : 'bg-[#7c3aed]/15 text-[#7c3aed]'
                  }`}>
                    {aiTask.status === 'running' ? '清洗中…' : aiTask.status === 'done' ? '清洗完成' : '清洗出错'}
                  </span>
                </div>

                {/* 整体说明（取首个有说明的单元）*/}
                {(() => {
                  const ex = Object.values(aiTask.datasets).map(d => d.explanation).find(Boolean);
                  return ex ? <p className="text-sm text-slate-700">{ex}</p> : null;
                })()}

                {/* 逐单元卡片 */}
                <div className="space-y-2">
                  {Object.entries(aiTask.datasets).map(([did, st]) => (
                    <div key={did} className="p-2.5 rounded-lg bg-white/50 border border-slate-200">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`w-2 h-2 rounded-full ${
                          st.status === 'done' ? 'bg-emerald-400'
                          : st.status === 'error' ? 'bg-red-400'
                          : 'bg-[#7c3aed] animate-pulse'
                        }`} />
                        <span className="text-xs font-medium text-slate-700">
                          {st.kind === 'merged' ? '宽表（已合并多表）' : '独立单表'}
                        </span>
                        {st.kind === 'merged' && st.sources && (
                          <span className="text-[10px] text-slate-500">来源：{st.sources.length} 张</span>
                        )}
                        <span className="text-[10px] text-slate-500 ml-auto font-mono">{did.slice(0, 8)}</span>
                      </div>
                      {st.steps_applied && st.steps_applied.length > 0 && (
                        <div className="space-y-1">
                          {st.steps_applied.map((s, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                              <span className={s.success ? 'text-green-400 mt-0.5' : 'text-red-400 mt-0.5'}>
                                {s.success ? '✅' : '❌'}
                              </span>
                              <div>
                                <span className="text-slate-700">{s.step}</span>
                                {s.reason && <span className="text-slate-500 ml-2">— {s.reason}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {typeof st.rows_change === 'number' && st.rows_change !== 0 && (
                        <p className="text-[11px] text-slate-600 mt-1">
                          数据行数：<span className={st.rows_change < 0 ? 'text-red-400' : 'text-green-400'}>{st.rows_change > 0 ? '+' : ''}{st.rows_change}</span>
                        </p>
                      )}
                      {st.status === 'error' && st.error && (
                        <p className="text-xs text-red-400 mt-1">⚠ {st.error}</p>
                      )}
                    </div>
                  ))}
                </div>

                {aiTask.error && aiTask.status === 'error' && (
                  <p className="text-xs text-red-400">⚠ {aiTask.error}</p>
                )}
                {aiTask.status === 'done' && (
                  <p className="text-[11px] text-slate-500">已删除被合并的原始表，仅保留清洗后的结果。如需回溯请用「恢复原始数据」。</p>
                )}
              </div>
            )}
          </div>

          {/* 消息通知 */}
          {messages.length > 0 && (
            <div className="space-y-2">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
                    msg.type === 'success'
                      ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                      : 'bg-red-500/10 border border-red-500/20 text-red-400'
                  }`}
                >
                  {msg.type === 'success' ? <FiCheck className="w-4 h-4" /> : <FiAlertTriangle className="w-4 h-4" />}
                  {msg.text}
                </div>
              ))}
            </div>
          )}

          {/* 手动清洗面板 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 列选择 + 缺失值处理 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <FiAlertTriangle className="w-4 h-4 text-yellow-400" /> 缺失值处理
              </h3>
              <div className="flex gap-2">
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  value={missingMethod}
                  onChange={(e) => setMissingMethod(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="fill_mean">均值填充（仅数值）</option>
                  <option value="fill_median">中位数填充（仅数值）</option>
                  <option value="fill_mode">众数填充</option>
                  <option value="fill_0">填充为 0</option>
                  <option value="fill_unknown">填充为 "Unknown"</option>
                  <option value="drop">删除含缺失值的行</option>
                  <option value="drop_column">删除该列</option>
                </select>
                <button onClick={handleMissing} className="px-4 py-2 text-sm rounded-lg bg-[#7c3aed]/80 text-white hover:bg-[#7c3aed] transition-colors">
                  应用
                </button>
              </div>
            </div>

            {/* 异常值处理 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <FiTrash2 className="w-4 h-4 text-red-400" /> 异常值处理
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                <span className="text-emerald-400 font-medium">常规检测</span>：剔除偏离大多数数据的异常点（推荐）
                <span className="mx-1.5">·</span>
                <span className="text-amber-400 font-medium">严格检测</span>：按平均值±3倍标准差筛选，数据越规整越准确
              </p>
              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className="flex-1 min-w-[100px] px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  value={outlierMethod}
                  onChange={(e) => setOutlierMethod(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="iqr">常规检测（推荐）</option>
                  <option value="zscore">严格检测</option>
                </select>
                <select
                  value={outlierAction}
                  onChange={(e) => setOutlierAction(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="remove">直接删除</option>
                  <option value="cap">拉回边界</option>
                </select>
                <button onClick={handleOutliers} className="px-4 py-2 text-sm rounded-lg bg-red-600/80 text-white hover:bg-red-600 transition-colors">
                  执行
                </button>
              </div>
            </div>

            {/* 类型转换 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <FiRefreshCw className="w-4 h-4 text-blue-400" /> 数据类型转换
              </h3>
              <div className="flex gap-2">
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  onChange={(e) => e.target.value && handleConvertType(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/50 border border-slate-200 text-slate-700 focus:outline-none focus:border-[#7c3aed]/50"
                >
                  <option value="">转换到...</option>
                  <option value="datetime">日期时间</option>
                  <option value="numeric">数值</option>
                  <option value="string">字符串</option>
                  <option value="category">分类</option>
                </select>
              </div>
            </div>

            {/* 恢复原始数据 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <FiRotateCcw className="w-4 h-4 text-emerald-400" /> 数据恢复
              </h3>
              <p className="text-xs text-slate-500">撤销所有清洗操作，恢复到上传时的原始数据</p>
              <button onClick={handleResetData} className="px-4 py-2 text-sm rounded-lg bg-emerald-600/80 text-white hover:bg-emerald-600 transition-colors">
                恢复原始数据
              </button>
            </div>
          </div>

          {/* 数据预览 — notranslate 防止翻译插件篡改表格 DOM */}
          <div translate="no" className="notranslate">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-slate-800">数据预览</h2>
              <button onClick={refreshAllData} className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-900 transition-colors">
                <FiRefreshCw className="w-3 h-3" /> 刷新
              </button>
            </div>
            <DataTable key={columns.join('|')} data={preview} />
          </div>
        </>
      ) : (
        <div className="glass-card p-8 text-center text-slate-500">
          请先在「数据上传」页面上传数据
        </div>
      )}
    </div>
  );
}

function getMethodLabel(method: string): string {
  const labels: Record<string, string> = {
    fill_mean: '均值填充',
    fill_median: '中位数填充',
    fill_mode: '众数填充',
    fill_0: '填充为 0',
    fill_unknown: '填充为 "Unknown"',
    drop: '删除含缺失值的行',
    drop_column: '删除该列',
  };
  return labels[method] || method;
}

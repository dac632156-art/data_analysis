/* CleanPage - 数据清洗 */
import React, { useState, useCallback } from 'react';
import { FiAlertTriangle, FiCheck, FiTrash2, FiRefreshCw, FiRotateCcw, FiZap, FiLoader, FiDownload } from 'react-icons/fi';
import DataTable from '../components/DataTable';
import { useData, AI_PROVIDERS } from '../contexts/DataContext';
import * as api from '../api/client';

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
  const [aiResponse, setAiResponse] = useState<{
    explanation: string;
    steps: Array<{ step: string; reason: string; success: boolean }>;
    rows_change: number;
  } | null>(null);

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

  const handleAiClean = async () => {
    if (!aiInput.trim()) return;
    if (!ds.apiKey) { addMessage('error', '请先在左上角配置 AI API Key'); return; }
    const provider = AI_PROVIDERS.find(p => p.id === ds.aiProvider);
    if (!provider) { addMessage('error', '请先在左上角选择 AI 模型提供商'); return; }
    setAiLoading(true);
    setAiResponse(null);
    try {
      const res = await api.aiClean(ds.sessionId, aiInput, ds.apiKey, provider.baseUrl, provider.model);

      const hasSuccess = res.steps_applied?.some((s) => s.success);

      // ── 先获取所有需要的数据，不触发任何状态更新 ──
      let previewData = res.preview ?? ds.preview;
      let newColumnInfo = ds.columnInfo;
      const newRows = res.rows ?? ds.rows;

      if (hasSuccess) {
        // 并行获取预览和列信息
        const [previewRes, colRes] = await Promise.allSettled([
          api.getDataPreview(ds.sessionId),
          api.getColumnInfo(ds.sessionId),
        ]);
        if (previewRes.status === 'fulfilled') {
          previewData = previewRes.value.preview;
        }
        if (colRes.status === 'fulfilled' && colRes.value.columns) {
          newColumnInfo = colRes.value.columns.map((c: Record<string, unknown>) => ({
            name: String(c.name ?? ''),
            dtype: String(c.dtype ?? ''),
            missing: Number(c.missing ?? 0),
            missing_rate: Number(c.missing_rate ?? 0),
            unique: Number(c.unique ?? 0),
            sample: String(c.sample ?? ''),
          }));
        }
      }

      // ── 一次性更新所有状态（同一同步块 → React 18 批处理只渲染一次）──
      if (res.explanation) {
        setAiResponse({
          explanation: res.explanation,
          steps: res.steps_applied || [],
          rows_change: res.rows_change || 0,
        });
      }
      if (hasSuccess) {
        addMessage('success', `AI 清洗完成：${res.steps_applied.filter(s => s.success).length} 步，数据行数变化 ${res.rows_change > 0 ? '+' : ''}${res.rows_change}`);
        setPreview(previewData);
        dd({ type: 'SET_DATA', payload: {
          rows: newRows,
          columns: newColumnInfo.length,
          columnInfo: newColumnInfo,
          preview: previewData,
        } });
        window.dispatchEvent(new Event('columns-updated'));
      }
      if (res.note) {
        addMessage('error', res.note);
      }
    } catch (err) {
      addMessage('error', err instanceof Error ? err.message : 'AI清洗失败');
    } finally {
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

  const handleDropDuplicates = async () => {
    try {
      const res = await api.dropDuplicates(ds.sessionId);
      addMessage('success', `已删除 ${res.rows_dropped} 行重复数据`);
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
          <h1 className="text-2xl font-bold text-[#f8fafc]"
            style={{ textShadow: '0 0 15px rgba(139,92,246,0.3)' }}
          >
            数据清洗
          </h1>
          <p className="text-[#94a3b8] text-sm mt-1">处理缺失值、异常值、数据类型等数据质量问题</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => api.downloadCSV(ds.sessionId, true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-green-500/30 text-green-400 hover:bg-green-500/10 transition-colors"
            title="下载上传时的原始数据"
          >
            <FiDownload className="w-4 h-4" /> 原始数据
          </button>
          <button
            onClick={() => api.downloadCSV(ds.sessionId, false)}
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
          <div className="glass-card p-4 space-y-3" style={{ borderColor: 'rgba(34,211,238,0.3)' }}>
            <h3 className="text-sm font-semibold text-[#22d3ee] flex items-center gap-2">
              <FiZap className="w-4 h-4" /> AI 智能清洗
              <span className="text-[10px] text-slate-500 font-normal">— 用自然语言告诉AI你要如何清洗数据</span>
            </h3>
            <div className="flex gap-2">
              <input
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAiClean()}
                placeholder="例如：把缺失值用均值填充、删除重复行、把日期列转为日期类型、删除利润率大于200%的异常值..."
                className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#22d3ee]/50"
              />
              <button onClick={handleAiClean} disabled={aiLoading || !aiInput.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-[#22d3ee]/20 border border-[#22d3ee]/30 text-[#22d3ee] hover:bg-[#22d3ee]/30 disabled:opacity-50 transition-colors">
                {aiLoading ? <FiLoader className="w-4 h-4 animate-spin" /> : <FiZap className="w-4 h-4" />}
                {aiLoading ? '分析中...' : '执行'}
              </button>
            </div>

            {/* AI 响应结果 */}
            {aiResponse && (
              <div className="p-3 rounded-lg" style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)' }}>
                <p className="text-sm text-slate-300 mb-2">{aiResponse.explanation}</p>
                {aiResponse.steps.length > 0 && (
                  <div className="space-y-1.5">
                    {aiResponse.steps.map((s, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className={s.success ? 'text-green-400 mt-0.5' : 'text-red-400 mt-0.5'}>
                          {s.success ? '✅' : '❌'}
                        </span>
                        <div>
                          <span className="text-slate-300">{s.step}</span>
                          {s.reason && <span className="text-slate-500 ml-2">— {s.reason}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {aiResponse.rows_change !== 0 && (
                  <p className="text-xs text-slate-400 mt-2">
                    数据行数：<span className={aiResponse.rows_change < 0 ? 'text-red-400' : 'text-green-400'}>{aiResponse.rows_change > 0 ? '+' : ''}{aiResponse.rows_change}</span>
                  </p>
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
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <FiAlertTriangle className="w-4 h-4 text-yellow-400" /> 缺失值处理
              </h3>
              <div className="flex gap-2">
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  value={missingMethod}
                  onChange={(e) => setMissingMethod(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="fill_mean">均值填充（仅数值）</option>
                  <option value="fill_median">中位数填充（仅数值）</option>
                  <option value="fill_mode">众数填充</option>
                  <option value="fill_0">填充为 0</option>
                  <option value="fill_unknown">填充为 "Unknown"</option>
                  <option value="drop">删除含缺失值的行</option>
                  <option value="drop_column">删除该列</option>
                </select>
                <button onClick={handleMissing} className="px-4 py-2 text-sm rounded-lg bg-[#8b5cf6]/80 text-white hover:bg-[#8b5cf6] transition-colors">
                  应用
                </button>
              </div>
            </div>

            {/* 异常值处理 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
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
                  className="flex-1 min-w-[100px] px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  value={outlierMethod}
                  onChange={(e) => setOutlierMethod(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="iqr">常规检测（推荐）</option>
                  <option value="zscore">严格检测</option>
                </select>
                <select
                  value={outlierAction}
                  onChange={(e) => setOutlierAction(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
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
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <FiRefreshCw className="w-4 h-4 text-blue-400" /> 数据类型转换
              </h3>
              <div className="flex gap-2">
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="">选择列...</option>
                  {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  onChange={(e) => e.target.value && handleConvertType(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg bg-white/[0.04] border border-white/[0.08] text-slate-300 focus:outline-none focus:border-[#8b5cf6]/50"
                >
                  <option value="">转换到...</option>
                  <option value="datetime">日期时间</option>
                  <option value="numeric">数值</option>
                  <option value="string">字符串</option>
                  <option value="category">分类</option>
                </select>
              </div>
            </div>

            {/* 删除重复行 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <FiTrash2 className="w-4 h-4 text-orange-400" /> 重复行处理
              </h3>
              <button onClick={handleDropDuplicates} className="px-4 py-2 text-sm rounded-lg bg-orange-600/80 text-white hover:bg-orange-600 transition-colors">
                删除所有重复行
              </button>
            </div>

            {/* 恢复原始数据 */}
            <div className="glass-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <FiRotateCcw className="w-4 h-4 text-emerald-400" /> 数据恢复
              </h3>
              <p className="text-xs text-slate-500">撤销所有清洗操作，恢复到上传时的原始数据</p>
              <button onClick={handleResetData} className="px-4 py-2 text-sm rounded-lg bg-emerald-600/80 text-white hover:bg-emerald-600 transition-colors">
                恢复原始数据
              </button>
            </div>
          </div>

          {/* 数据预览 */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-[#f8fafc]">数据预览</h2>
              <button onClick={refreshAllData} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
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

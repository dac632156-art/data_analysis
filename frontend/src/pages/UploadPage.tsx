/* UploadPage - 数据上传与预览 */
import React, { useState, useRef, useCallback } from 'react';
import FileUploader from '../components/FileUploader';
import DataTable from '../components/DataTable';
import MetricCard from '../components/MetricCard';
import ErrorBoundary from '../components/ErrorBoundary';
import QueueModal from '../components/QueueModal';
import { useData } from '../contexts/DataContext';
import { uploadFile, uploadGate, getUploadQueueStatus, cancelUploadQueue, releaseUploadSlot } from '../api/client';

// 并发数据插槽上限（与后端 SessionManager.max_sessions 保持一致，仅用于弹窗展示）
const MAX_SESSIONS = 5;

export default function UploadPage() {
  const { state, dispatch } = useData();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [queue, setQueue] = useState<{ open: boolean; position: number; ticketId: string | null }>({
    open: false,
    position: 1,
    ticketId: null,
  });
  const cancelRef = useRef(false);

  // 真正执行上传（含 session_id 同步与数据写入），供直接上传与排到后自动上传复用
  const doUpload = useCallback(async (file: File, sessionId: string) => {
    const res = await uploadFile(file, sessionId);
    // 同步后端返回的 session_id，确保后续页面能找到数据
    if (res.session_id && res.session_id !== state.sessionId) {
      dispatch({ type: 'SET_SESSION', sessionId: res.session_id });
      localStorage.setItem('sessionId', res.session_id);
    }
    // 防御性处理：确保所有字段都有默认值
    const safeRes = {
      file_name: res.file_name ?? file.name,
      rows: res.rows ?? 0,
      columns: res.columns ?? 0,
      preview: Array.isArray(res.preview) ? res.preview : [],
      column_info: Array.isArray(res.column_info) ? res.column_info.map((col: Record<string, unknown>) => ({
        name: String(col.name ?? ''),
        dtype: String(col.dtype ?? ''),
        missing: Number(col.missing ?? 0),
        missing_rate: Number(col.missing_rate ?? 0),
        unique: Number(col.unique ?? 0),
        sample: String(col.sample ?? ''),
      })) : [],
      memory_usage: String(res.memory_usage ?? ''),
      total_missing: Number(res.total_missing ?? 0),
      duplicate_rows: Number(res.duplicate_rows ?? 0),
    };
    dispatch({
      type: 'SET_DATA',
      payload: {
        fileName: safeRes.file_name,
        rows: safeRes.rows,
        columns: safeRes.columns,
        preview: safeRes.preview,
        columnInfo: safeRes.column_info,
        dataInfo: {
          rows: safeRes.rows,
          columns: safeRes.columns,
          memory_usage: safeRes.memory_usage,
          total_missing: safeRes.total_missing,
          duplicate_rows: safeRes.duplicate_rows,
        },
      },
    });
  }, [state.sessionId, dispatch]);

  // 后台轮询排队状态，轮到（ready）返回可用 session_id；取消/失效则抛错
  const waitForTurn = useCallback(async (ticketId: string): Promise<string> => {
    const POLL_INTERVAL = 2500;
    while (true) {
      if (cancelRef.current) throw new Error('已取消排队');
      const st = await getUploadQueueStatus(ticketId);
      if (st.status === 'ready') return st.session_id as string;
      if (st.status === 'expired') throw new Error('排队已失效，请重新上传');
      setQueue((q) => ({ ...q, position: st.position ?? q.position }));
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
    }
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    cancelRef.current = false;
    setUploadError(null);
    dispatch({ type: 'SET_LOADING', loading: true });
    try {
      // 1) 先过闸门预约数据插槽
      const gate = await uploadGate(state.sessionId);
      let sessionId = gate.session_id ?? state.sessionId;
      if (!gate.granted) {
        // 2) 满员 → 进入排队弹窗并后台轮询，轮到后自动上传
        setQueue({ open: true, position: gate.position ?? 1, ticketId: gate.ticket_id ?? null });
        sessionId = await waitForTurn(gate.ticket_id as string);
      }
      // 3) 拿到插槽后上传（直接 or 排到自动）
      await doUpload(file, sessionId);
    } catch (err) {
      const message = err instanceof Error ? err.message : '上传失败';
      setUploadError(message);
      console.error('[UploadPage] Upload failed:', message);
    } finally {
      setQueue({ open: false, position: 1, ticketId: null });
      dispatch({ type: 'SET_LOADING', loading: false });
    }
  }, [state.sessionId, dispatch, waitForTurn, doUpload]);

  // 取消排队：置标志 + 通知后端移除票据 + 关闭弹窗
  const handleCancelQueue = useCallback(async () => {
    cancelRef.current = true;
    if (queue.ticketId) {
      try {
        await cancelUploadQueue(queue.ticketId);
      } catch {
        // 尽力而为，忽略后端异常
      }
    }
    setUploadError('已取消排队');
    setQueue({ open: false, position: 1, ticketId: null });
    dispatch({ type: 'SET_LOADING', loading: false });
  }, [queue.ticketId, dispatch]);

  // 手动释放数据插槽：二次确认后释放并清空本地预览，让排队中的用户自动入队
  const handleReleaseSlot = useCallback(async () => {
    const ok = window.confirm(
      '确认结束本会话并释放数据插槽？释放后排队中的用户可自动入队，您需要重新上传才能继续使用。'
    );
    if (!ok) return;
    try {
      const res = await releaseUploadSlot(state.sessionId);
      if (res.released) {
        dispatch({ type: 'CLEAR_DATA' });
        setUploadError(null);
      } else {
        setUploadError('当前会话未占用插槽，无需释放');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '释放插槽失败';
      setUploadError(message);
    }
  }, [state.sessionId, dispatch]);

  const hasData = state.rows > 0;
  const memoryUsage = state.dataInfo?.memory_usage || '';

  return (
    <ErrorBoundary>
      <div className="page-enter space-y-6">
        <div>
          <h1 className="text-4xl font-extrabold text-[#f8fafc] tracking-wide"
            style={{ textShadow: '0 0 18px rgba(167,139,250,0.45), 0 0 36px rgba(196,181,253,0.25)' }}
          >
            数据上传
          </h1>
          <p
            className="mt-2 text-sm font-medium"
            style={{ color: '#c4b5fd', textShadow: '0 0 10px rgba(196,181,253,0.4)' }}
          >
            支持 CSV、Excel、JSON、SQLite 格式
          </p>
        </div>

        {/* 宇宙传送门上传 */}
        <FileUploader onUpload={handleUpload} disabled={state.loading} />

        {uploadError && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {uploadError}
          </div>
        )}

        <QueueModal
          open={queue.open}
          position={queue.position}
          maxSessions={MAX_SESSIONS}
          onCancel={handleCancelQueue}
        />

        {state.loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 rounded-full border-2 border-[#a78bfa] border-t-transparent animate-spin" />
            <span className="ml-3 text-[#94a3b8]">正在加载数据...</span>
          </div>
        )}

        {hasData && !state.loading && (
          <>
            {/* 数据概览 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard title="总行数" value={String(state.rows)} icon="database" />
              <MetricCard title="总列数" value={state.columns} icon="columns" />
              <MetricCard title="内存占用" value={memoryUsage || '-'} icon="database" color="#c4b5fd" />
              <MetricCard title="文件名" value={state.fileName || '-'} icon="target" color="#8b5cf6" />
            </div>

            {/* 结束会话 / 释放插槽：给排队用户腾出空位 */}
            <div className="flex justify-end">
              <button
                onClick={handleReleaseSlot}
                className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors hover:bg-[#8b5cf6]/[0.25]"
                style={{
                  background: 'rgba(139,92,246,0.15)',
                  border: '1px solid rgba(139,92,246,0.4)',
                  color: '#c4b5fd',
                }}
              >
                结束会话 / 释放插槽
              </button>
            </div>

            {/* 数据预览 */}
            {state.preview.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-[#f8fafc] mb-3">数据预览</h2>
                <DataTable data={state.preview} />
              </div>
            )}

            {/* 字段信息 */}
            {state.columnInfo.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-[#f8fafc] mb-3">字段信息</h2>
                <div className="glass-card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ background: 'rgba(196,181,253,0.25)' }}>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">列名</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">类型</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">缺失值</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">缺失率</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">唯一值</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">示例值</th>
                      </tr>
                    </thead>
                    <tbody>
                      {state.columnInfo.map((col) => (
                        <tr key={col.name} className="border-t border-white/[0.04] hover:bg-[#8b5cf6]/[0.06]">
                          <td className="px-4 py-2.5 text-slate-200 font-medium">{col.name}</td>
                          <td className="px-4 py-2.5">
                            <span className="px-2 py-0.5 text-xs rounded bg-[#a78bfa]/20 text-[#c4b5fd]">
                              {col.dtype}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-slate-400">{col.missing ?? '-'}</td>
                          <td className="px-4 py-2.5 text-slate-400">{((col.missing_rate ?? 0) * 100).toFixed(1)}%</td>
                          <td className="px-4 py-2.5 text-slate-400">{col.unique ?? '-'}</td>
                          <td className="px-4 py-2.5 text-slate-400 max-w-[200px] truncate">{String(col.sample ?? '-')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}

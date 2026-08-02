import { useEffect, useState, useCallback } from 'react';
import { FileText, Trash2, AlertTriangle, Database, GitMerge } from 'lucide-react';
import MetricCard from '../components/MetricCard';
import DataTable from '../components/DataTable';
import FileUploader from '../components/FileUploader';
import { useData } from '../contexts/DataContext';
import { formatBytes } from '../utils/format';
import {
  uploadFile, listDatasets, removeDataset, selectDataset,
  releaseUploadSlot,
} from '../api/client';
import type { DatasetInfo } from '../types/api';

const QUOTA_DEFAULT = 30 * 1024 * 1024;

export default function UploadPage() {
  const { state, dispatch } = useData();
  const { sessionId, datasets, activeDatasetId, usedBytes, quotaBytes, fileName, rows, columns, loading, error, preview, columnInfo } = state;
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 修复九：挂载拉回列表 + 额度（刷新后内存清空，从后端恢复）
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await listDatasets(sessionId);
        if (!alive) return;
        dispatch({ type: 'SET_DATASETS', datasets: res.datasets });
        dispatch({ type: 'SET_QUOTA', usedBytes: res.used_bytes, quotaBytes: res.quota_bytes });
        const active = res.datasets.find(d => d.is_active);
        if (active) dispatch({ type: 'SELECT_DATASET', datasetId: active.dataset_id });
      } catch { /* 会话暂无数据，忽略 */ }
    })();
    return () => {
      alive = false;
    };
  }, [sessionId]);

  // 逐文件上传（修复四 + 修复八：累计额度前置判断）
  const doUpload = useCallback(async (file: File) => {
    if (state.usedBytes + file.size > (state.quotaBytes || QUOTA_DEFAULT)) {
      throw new Error('累计上传额度已满，无法继续上传');
    }
    setUploadError(null);
    try {
      const res = await uploadFile(file, sessionId);
      // 多 sheet Excel 会返回 datasets 列表，单表时为长度为 1 的列表；统一走列表
      const items = (res.datasets && res.datasets.length)
        ? res.datasets
        : [{
            dataset_id: res.dataset_id,
            file_name: res.file_name ?? file.name,
            rows: res.rows,
            columns: res.columns,
            memory_usage: res.memory_usage,
            total_missing: res.total_missing,
            duplicate_rows: res.duplicate_rows,
            preview: res.preview,
            column_info: res.column_info,
            column_names: (res.column_info?.map(c => c.name)) ?? [],
          }];
      items.forEach((d, i) => {
        const ds: DatasetInfo = {
          dataset_id: d.dataset_id,
          file_name: d.file_name ?? file.name,
          file_size_bytes: i === 0 ? res.file_size_bytes : 0,
          rows: d.rows,
          columns: d.column_names ?? [],
          column_info: d.column_info,
          preview: d.preview,
          uploaded_at: Date.now(),
          is_active: i === 0,
        };
        dispatch({ type: 'ADD_DATASET', payload: ds });
      });
      dispatch({ type: 'SET_QUOTA', usedBytes: res.used_bytes, quotaBytes: res.quota_bytes });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '上传失败';
      throw new Error(msg);
    }
  }, [sessionId, state.usedBytes, state.quotaBytes]);

  const handleSelect = useCallback(async (datasetId: string) => {
    try { await selectDataset(sessionId, datasetId); } catch { /* ignore */ }
    dispatch({ type: 'SELECT_DATASET', datasetId });
  }, [sessionId]);

  const handleRemove = useCallback(async (datasetId: string) => {
    try { await removeDataset(sessionId, datasetId); } catch { /* ignore */ }
    try {
      const res = await listDatasets(sessionId);
      dispatch({ type: 'SET_DATASETS', datasets: res.datasets });
      dispatch({ type: 'SET_QUOTA', usedBytes: res.used_bytes, quotaBytes: res.quota_bytes });
      const active = res.datasets.find(d => d.is_active);
      if (active) dispatch({ type: 'SELECT_DATASET', datasetId: active.dataset_id });
    } catch { /* ignore */ }
  }, [sessionId]);

  const handleRelease = async () => {
    if (!confirm('确定释放插槽？所有已上传报表与额度将被清空。')) return;
    await releaseUploadSlot(sessionId);
    dispatch({ type: 'CLEAR_DATA' });
    dispatch({ type: 'SET_QUOTA', usedBytes: 0, quotaBytes: 0 });
  };

  const handleDeleteAll = useCallback(async () => {
    if (!confirm('确定删除全部已上传报表？此操作不可撤销。')) return;
    setDeleting(true);
    try {
      for (const ds of datasets) {
        await removeDataset(sessionId, ds.dataset_id);
      }
      const res = await listDatasets(sessionId);
      dispatch({ type: 'SET_DATASETS', datasets: res.datasets });
      dispatch({ type: 'SET_QUOTA', usedBytes: res.used_bytes, quotaBytes: res.quota_bytes });
      const active = res.datasets.find(d => d.is_active);
      if (active) dispatch({ type: 'SELECT_DATASET', datasetId: active.dataset_id });
    } catch { /* ignore */ }
    finally { setDeleting(false); }
  }, [sessionId, datasets]);

  // 额度进度条
  const quota = quotaBytes || QUOTA_DEFAULT;
  const pct = quota > 0 ? Math.min(100, (usedBytes / quota) * 100) : 0;
  const full = usedBytes >= quota;
  const warn = pct > 80;
  const barColor = full ? '#fb7185' : warn ? '#fbbf24' : '#8b5cf6';


  return (
    <div className="text-[#f8fafc]">
          {/* 额度进度条 */}
          <div className="glass-card p-4 mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-[#94a3b8]">上传额度</span>
              <span className="text-sm font-medium" style={{ color: full ? '#fb7185' : warn ? '#fbbf24' : '#8b5cf6' }}>
                已用 {formatBytes(usedBytes)} / {formatBytes(quota)}
              </span>
            </div>
            <div className="h-2 rounded-full bg-[#1e293b] overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: barColor, boxShadow: `0 0 12px ${barColor}` }} />
            </div>
            {full && <p className="text-xs text-[#fb7185] mt-2">额度已用尽，请删除部分报表或释放插槽。</p>}
          </div>

          {/* 上传区 */}
          <FileUploader onUpload={doUpload} disabled={full} />
          {uploadError && (
            <div className="mt-3 glass-card p-3 text-sm text-[#fb7185] flex items-center gap-2">
              <AlertTriangle size={14} />{uploadError}
            </div>
          )}

          {/* 已上传报表列表 */}
          <div className="glass-card p-5 mt-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2"><Database size={18} className="text-[#8b5cf6]" />已上传报表
                <span className="text-xs text-[#94a3b8]">（{datasets.length}）</span>
              </h2>
              <button
                onClick={handleDeleteAll}
                disabled={deleting || datasets.length === 0}
                className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: 'linear-gradient(135deg,#8b5cf6,#a78bfa)', color: '#fff', boxShadow: '0 0 16px rgba(139,92,246,0.4)' }}
              >
                {deleting ? '删除中…' : '一键删除'}
              </button>
            </div>

            {datasets.length === 0 ? (
              <p className="text-sm text-[#94a3b8] py-6 text-center">暂无报表，请拖拽文件上传。</p>
            ) : (
              <div className="flex flex-col gap-3">
                {datasets.map((ds) => {
                  const isActive = ds.dataset_id === activeDatasetId;
                  return (
                    <div
                      key={ds.dataset_id}
                      onClick={() => handleSelect(ds.dataset_id)}
                      className={`relative flex items-center justify-between p-4 rounded-xl cursor-pointer transition-all duration-300 border ${isActive ? 'border-[#8b5cf6] bg-[#8b5cf6]/10' : 'border-white/10 bg-white/5 hover:border-[#8b5cf6]/50'}`}
                      style={isActive ? { boxShadow: '0 0 20px rgba(139,92,246,0.35)' } : undefined}
                    >
                      {isActive && <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-[#8b5cf6]" />}
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText size={20} className="text-[#8b5cf6] shrink-0" />
                        <div className="min-w-0">
                          <p className="font-medium text-[#f8fafc] truncate">{ds.file_name}</p>
                          {ds.is_merged && (
                            <span className="mt-1 inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-[#8b5cf6]/15 text-[#a78bfa] border border-[#8b5cf6]/30">
                              <GitMerge size={11} />合并宽表
                              {ds.merge_keys && ds.merge_keys.length > 0 ? ` · 按 ${ds.merge_keys.join('/')} 关联` : ''}
                              {ds.sources && ds.sources.length > 0 ? ` · 来源${ds.sources.length}表` : ''}
                            </span>
                          )}
                          <p className="text-xs text-[#94a3b8]">{formatBytes(ds.file_size_bytes)} · {ds.rows} 行 × {ds.columns.length} 列</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleRemove(ds.dataset_id)}
                          className="p-1.5 rounded-lg text-[#94a3b8] hover:text-[#fb7185] hover:bg-[#fb7185]/10 transition-colors"
                          title="删除该报表"
                        ><Trash2 size={16} /></button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 当前数据集概览与预览（active 数据集）*/}
          {fileName ? (
            <div className="mt-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <MetricCard label="当前报表" value={fileName} hint="文件名" />
                <MetricCard label="总行数" value={rows.toString()} hint="数据规模" />
                <MetricCard label="总列数" value={columns.toString()} hint="字段数量" />
              </div>
              {columnInfo && columnInfo.length > 0 && (
                <div className="glass-card p-5 mb-6">
                  <h3 className="text-base font-medium mb-4">字段信息</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-[#94a3b8] border-b border-white/10">
                          <th className="py-2 pr-4">字段名</th><th className="py-2 pr-4">类型</th>
                          <th className="py-2 pr-4">缺失值</th><th className="py-2 pr-4">唯一值</th><th className="py-2">示例</th>
                        </tr>
                      </thead>
                      <tbody>
                        {columnInfo.map((c, i) => (
                          <tr key={i} className="border-b border-white/5">
                            <td className="py-2 pr-4 text-[#f8fafc]">{c.name}</td>
                            <td className="py-2 pr-4 text-[#94a3b8]">{c.dtype}</td>
                            <td className="py-2 pr-4 text-[#94a3b8]">{c.missing}（{c.missing_rate}%）</td>
                            <td className="py-2 pr-4 text-[#94a3b8]">{c.unique}</td>
                            <td className="py-2 text-[#94a3b8] truncate max-w-xs">{c.sample}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <div className="glass-card p-5">
                <h3 className="text-base font-medium mb-4">数据预览（前 100 行）</h3>
                <DataTable data={preview} maxRows={100} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-[#94a3b8] mt-6 text-center py-6">请选择一张报表以查看预览。</p>
          )}

          {/* 底部操作栏 */}
          <div className="mt-6 flex justify-end">
            <button
              onClick={handleRelease}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-[#fb7185]/15 text-[#fb7185] hover:bg-[#fb7185]/25 transition-colors"
            >结束会话 / 释放插槽</button>
          </div>
    </div>
  );
}

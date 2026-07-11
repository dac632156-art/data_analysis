/**
 * DashboardV2Page — Dashboard Generator 前端入口
 *
 * 调用 getDashboardSchema → DashboardRenderer 渲染
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useData } from '../contexts/DataContext';
import { getDashboardSchema } from '../api/client';
import { DashboardRenderer } from '../components/DashboardRenderer';
import type { DashboardSchema } from '../types/dashboard';

export default function DashboardV2Page() {
  const { state: ds } = useData();
  const [schema, setSchema] = useState<DashboardSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSchema = useCallback(async () => {
    if (!ds.sessionId) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await getDashboardSchema(ds.sessionId, ds.fileName || '数据分析驾驶舱');
      setSchema(res.schema);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [ds.sessionId, ds.fileName]);

  useEffect(() => { fetchSchema(); }, [fetchSchema]);

  return (
    <div className="page-enter">
      <DashboardRenderer
        schema={schema}
        loading={loading}
        error={error}
        onFilterChange={(field, value) => {
          console.log('[DashboardV2] filter:', field, value);
        }}
      />
    </div>
  );
}

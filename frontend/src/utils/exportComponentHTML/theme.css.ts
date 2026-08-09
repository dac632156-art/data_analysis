/**
 * theme.css.ts —— 导出 HTML 的内联仙气主题 CSS。
 *
 * 视觉与屏幕数据看板（SmartDashboard）保持一致的浅色玻璃拟态风格：
 *   - 淡紫白水彩背景图（由 index.ts 以 --bg-card DataURL 注入）
 *   - 白色半透明毛玻璃卡片（backdrop-blur + 圆角 + 微妙阴影）
 *   - 星光蓝 #38BDF8 / 银河紫 #8B5CF6 / 极光青 #22D3EE 点缀
 *   - hover 微动效
 */
export const THEME_CSS = `
:root {
  --bg-accent: #38BDF8;
  --bg-ai: #8B5CF6;
  --bg-interaction: #22D3EE;
  --ink: #0F172A;
  --ink-2: #334155;
  --ink-3: #94A3B8;
  --card-glass: rgba(255, 255, 255, 0.55);
  --card-border: rgba(255, 255, 255, 0.65);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  color: var(--ink);
  background-color: #F8FAFC;
  /* 水彩背景图：由 index.ts 注入 --bg-card 变量（淡紫白水彩 png base64） */
  background-image: var(--bg-card);
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
  min-height: 100vh;
}
#root { min-height: 100vh; }

/* 顶部标题栏 */
.ed-topbar {
  position: sticky; top: 0; z-index: 20;
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 22px;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.55);
}
.ed-title {
  font-size: 20px; font-weight: 700;
  background: linear-gradient(90deg, #38BDF8, #8B5CF6);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.ed-mode-badge {
  font-size: 12px; font-weight: 600; color: #fff;
  padding: 4px 12px; border-radius: 999px;
  background: linear-gradient(135deg, #8B5CF6, #38BDF8);
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35);
}

/* 主网格 */
.ed-grid {
  display: grid; gap: 12px; padding: 16px; width: 100%; max-width: 1920px; margin: 0 auto;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

/* 图表卡片 */
.ed-card {
  position: relative; min-height: 0; min-width: 0; height: 100%;
  display: flex; flex-direction: column; overflow: hidden;
  border-radius: 16px;
  background:
    linear-gradient(rgba(255,255,255,0.32), rgba(255,255,255,0.32)),
    var(--bg-card);
  background-size: cover; background-position: center;
  border: 1px solid var(--card-border);
  box-shadow: 0 8px 22px rgba(31, 41, 55, 0.12), inset 0 1px 0 rgba(255,255,255,0.6);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.ed-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 32px rgba(139, 92, 246, 0.22), inset 0 1px 0 rgba(255,255,255,0.7);
}
.ed-card-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px 6px;
  font-size: 14px; font-weight: 600; color: #8B5CF6;
}
.ed-card-body { flex: 1; min-height: 0; min-width: 0; padding: 4px 8px 10px; }

/* KPI 卡片 */
.ed-kpi {
  display: flex; flex-direction: column; justify-content: center; align-items: flex-start;
  padding: 14px 18px; gap: 4px;
}
.ed-kpi-label { font-size: 12px; color: var(--ink-2); }
.ed-kpi-value {
  font-size: 26px; font-weight: 800; color: var(--ink);
  background: linear-gradient(90deg, #38BDF8, #8B5CF6);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.ed-kpi-change { font-size: 12px; font-weight: 600; }
.ed-kpi-change.up { color: #34D399; }
.ed-kpi-change.down { color: #FB7185; }

/* 表格 */
.ed-table { width: 100%; border-collapse: collapse; font-size: 12px; color: var(--ink-2); }
.ed-table th {
  text-align: left; padding: 7px 10px; font-weight: 600; color: #38BDF8;
  background: rgba(56, 189, 248, 0.10); border-bottom: 1px solid rgba(56,189,248,0.25);
}
.ed-table td { padding: 6px 10px; border-bottom: 1px solid rgba(148,163,184,0.18); }
.ed-table tbody tr:nth-child(even) { background: rgba(255,255,255,0.30); }

/* 底部说明栏 */
.ed-footer {
  padding: 16px 22px 28px; text-align: center;
  font-size: 12px; color: var(--ink-3);
}
.ed-placeholder {
  display: flex; align-items: center; justify-content: center; height: 100%;
  font-size: 11px; color: var(--ink-3);
  border: 1px dashed rgba(148,163,184,0.5); border-radius: 12px;
}
`;

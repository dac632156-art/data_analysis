/**
 * etherealCore UMD 入口
 *
 * 把「仙气看板组件树」（EtherealChart 分发 + 9 个子组件 + EChartView 增强层 +
 * 饼图 canvas 染色 + 单位函数 + 阈值线）整体打包成一个 UMD 文件，
 * 供「单文件导出 HTML」直接 <EtherealCore.EtherealChart .../> 复用。
 *
 * 这样导出端和屏幕端共用同一份组件代码 → 像素级一致，且不用重写任何逻辑。
 *
 * 构建：vite build --config vite.lib.config.ts → dist-lib/ethereal-core.js
 * 运行时：UMD external react/react-dom（走 CDN），echarts/echarts-gl 打进 UMD。
 */
import { EtherealChart } from './EtherealChart';
import { EtherealMetricCard } from './EtherealMetricCard';

export { EtherealChart, EtherealMetricCard };

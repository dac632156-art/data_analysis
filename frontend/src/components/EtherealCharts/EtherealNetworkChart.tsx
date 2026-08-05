import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { CustomChart } from 'echarts/charts';
import { TooltipComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';
import { Palette } from '../../theme/Palette';
import 背景 from '../../assets/ethereal/背景.png';

echarts.use([CustomChart, TooltipComponent, TitleComponent, CanvasRenderer]);

interface Props {
  chartNode: Record<string, unknown>;
  height?: number | string;
  /** 标题（来自 EtherealChart 透传的 chart.title，优先于 chartNode.title） */
  title?: string;
}

// 动态调色板：复用 VDS 10 色有序分类色板（SSOT = Palette.ts），不再写死类目→颜色。
// 类目按实际出现顺序去重后循环取色，保证任何类目都能上色，不会落灰/变白。
const CATEGORY_PALETTE: string[] = [
  Palette.primary, // 星光蓝（数据主色，打头）
  Palette.catIndigo, // 靛蓝
  Palette.catSkyBlue, // 天空蓝
  Palette.catLake, // 湖水绿
  Palette.catGold, // 金色
  Palette.catRose, // 玫瑰粉
  Palette.catCoral, // 珊瑚橙
  Palette.catLime, // 青柠绿
  Palette.catLightPurple, // 淡紫
  Palette.interaction, // 极光青（交互冷色收尾）
];

/** 根据「实际出现的类目列表」动态生成 类目→颜色 映射（循环取色板） */
function buildCategoryColorMap(categories: string[]): Map<string, string> {
  const map = new Map<string, string>();
  categories.forEach((cat, i) => {
    if (!map.has(cat)) {
      map.set(cat, CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]);
    }
  });
  return map;
}

// 商品 → 类目映射（兜底用：当节点名没有「（类目）」包裹时，按商品名关键词归类）
function getCategoryByName(name: string): string {
  const map: Record<string, string[]> = {
    美妆个护: ['口红', '面膜', '洗面奶', '精华液', '美妆'],
    服饰: ['连衣裙', '服饰', '衣服'],
    运动户外: ['运动服', '跑步鞋', '瑜伽垫', '运动水壶', '运动'],
    母婴: ['婴儿奶粉', '纸尿裤', '奶瓶', '母婴'],
    食品: ['纯牛奶', '果汁', '咖啡', '零食', '食品'],
    宠物: ['狗粮', '猫砂', '宠物'],
    数码办公: ['电子书阅读器', '机械键盘', '无线鼠标', '护眼台灯', '数码'],
    汽车用品: ['行车记录仪', '车载支架', '车载充电器', '汽车'],
    家居: ['玻璃水杯', '棉柔毛巾', '家居'],
    图书文具: ['畅销小说', '金属书签', '手账笔记本', '图书'],
  };
  for (const [cat, names] of Object.entries(map)) {
    if (names.some((n) => name.includes(n))) return cat;
  }
  return '其他';
}

// 主入口：优先从「商品名（类目）」的括号里提取类目；提取不到则把整个名当类目返回。
// 后端聚合后节点名已是纯类目（如「食品生鲜」），无括号，此时直接返回原名即可。
function getCategory(name: string): string {
  const m = name.match(/[（(]([^（）()]+)[)）]/);
  if (m && m[1]) {
    return m[1].trim();
  }
  return name;
}

export const EtherealNetworkChart: React.FC<Props> = ({ chartNode, title: titleProp, height = 420 }) => {
  const ref = useRef<HTMLDivElement>(null);
  const title = (titleProp as string) || (chartNode.title as string) || '商品关联网络图';

  useEffect(() => {
    if (!ref.current) return;
    const chartDom = ref.current;

    // 卡片样式接管（对齐原版第 21-35 行）
    chartDom.style.backgroundImage = `url(${背景})`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.backgroundColor = 'transparent';
    chartDom.style.backdropFilter = 'blur(18px)';
    chartDom.style.WebkitBackdropFilter = 'blur(18px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.6)';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)';
    chartDom.style.padding = '26px 30px 44px 30px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.overflow = 'hidden';
    chartDom.style.fontFamily = "'Microsoft YaHei', sans-serif";
    chartDom.style.position = 'relative';

    // 1. 数据三层兜底（对齐模板库 关联图组件.js 第 71-96 行）
    //    chartNode 可能是两种形态：
    //      a) 包装型 { option: {...} }（部分调用方把 option 包了一层）
    //      b) 直接型 = 后端 graph option 本身（series 在顶层，无外层 option）
    //    EtherealChart 传入的 chartNode 是形态 b，故必须兼容 optNode = chartNode.option || chartNode，
    //    否则 chartNode.option 为 undefined → seriesData 空 → 节点走边表去重构建（无 value）→ hover 显示 0。
    const optNode =
      ((chartNode.option as Record<string, unknown>) ||
        (chartNode as Record<string, unknown>)) as Record<string, unknown>;
    const seriesArr = (optNode.series as Array<Record<string, unknown>>) || [];
    const series0 = seriesArr[0] || {};
    const seriesData = (series0.data as Array<Record<string, unknown>>) || [];
    const seriesLinks = (series0.links as Array<Record<string, unknown>>) || [];

    const dataProp = (chartNode.data as Array<Record<string, unknown>>) || [];

    let rawNodes: Array<Record<string, unknown>> = [];
    let rawLinks: Array<Record<string, unknown>> = [];

    // 边表优先：data prop（含 lift） → option.series[0].links
    if (dataProp.length > 0) {
      rawLinks = dataProp.map((l) => ({ ...l }));
    } else if (seriesLinks.length > 0) {
      rawLinks = seriesLinks.map((l) => ({ ...l }));
    }

    // 节点表：option.series[0].data
    if (seriesData.length > 0 && typeof seriesData[0] === 'object') {
      rawNodes = seriesData.map((n) => ({ ...n }));
    }

    // 节点表为空时，从边表去重构建
    if (rawNodes.length === 0 && rawLinks.length > 0) {
      const nameSet = new Set<string>();
      rawLinks.forEach((l) => {
        if (l.source !== undefined) nameSet.add(String(l.source));
        if (l.target !== undefined) nameSet.add(String(l.target));
      });
      rawNodes = Array.from(nameSet).map((name) => ({ name }));
    }

    if (rawNodes.length === 0 || rawLinks.length === 0) {
      chartDom.innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94A3B8;">无足够关联数据</div>';
      return;
    }

    // lift 补全映射（data prop 里的 lift 优先）
    const liftMap = new Map<string, number>();
    if (dataProp.length > 0) {
      dataProp.forEach((l) => {
        if (l.lift !== undefined) liftMap.set(`${l.source}→${l.target}`, Number(l.lift));
      });
    }

    // 2. 构造节点（按类目聚合排序，与原版一致）
    // 先收集所有出现的类目，动态生成 类目→颜色 映射（不再写死字典）
    const allCats = Array.from(
      new Set(
        rawNodes.map((n) => getCategory(String(n.name ?? ''))),
      ),
    );
    const catColorMap = buildCategoryColorMap(allCats);

    // 显示名：去掉商品ID前缀，只保留「（类目）」里的类目部分（如 S060（食品生鲜）→ 食品生鲜）
    const stripId = (full: string): string => {
      const m = full.match(/[（(]([^（）()]+)[)）]/);
      if (m && m[1]) return m[1].trim();
      return full; // 无括号包裹时回退到原名
    };

    const nodes = rawNodes
      .map((n) => {
        const name = String(n.name ?? '');
        const cat = getCategory(name);
        return {
          id: name,
          name,
          displayName: stripId(name),
          value: Number(n.value || 0),
          category: cat,
          color: catColorMap.get(cat) || Palette.textMuted,
        };
      })
      .sort((a, b) => {
        if (a.category !== b.category) return a.category.localeCompare(b.category, 'zh-CN');
        return a.name.localeCompare(b.name, 'zh-CN');
      });

    const nodeMap = new Map(nodes.map((n, i) => [n.name, i]));

    const links = rawLinks
      .map((l) => {
        const s = String(l.source ?? '');
        const t = String(l.target ?? '');
        const sIdx = nodeMap.get(s);
        const tIdx = nodeMap.get(t);
        if (sIdx === undefined || tIdx === undefined) return null;
        const lift = l.lift !== undefined ? Number(l.lift) : liftMap.get(`${s}→${t}`) || 1;
        return {
          source: s,
          target: t,
          sIdx,
          tIdx,
          value: Number(l.value || 0),
          lift,
        };
      })
      .filter(Boolean) as Array<{
      source: string;
      target: string;
      sIdx: number;
      tIdx: number;
      value: number;
      lift: number;
    }>;

    const chart = echarts.init(chartDom);

    // 3. 和弦图布局工具
    function polar(cx: number, cy: number, r: number, angle: number) {
      return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    }

    const N = nodes.length;
    const gap = 0.14;
    const step = (2 * Math.PI) / N;
    const maxLinkValue = Math.max(1, ...links.map((l) => l.value));

    const renderData: Array<Record<string, unknown>> = [];

    // 3.1 弦带（先绘制，位于扇区下方）
    links.forEach((link) => {
      renderData.push({
        type: 'ribbon',
        source: link.source,
        target: link.target,
        value: link.value,
        lift: link.lift,
        sIdx: link.sIdx,
        tIdx: link.tIdx,
        color: nodes[link.sIdx].color,
        opacity: link.lift > 1 ? 0.56 : 0.3,
      });
    });

    // 3.2 外圈扇区
    nodes.forEach((node, i) => {
      renderData.push({
        type: 'sector',
        name: node.displayName,
        value: node.value,
        category: node.category,
        color: node.color,
        idx: i,
      });
    });

    // 3.3 标签
    nodes.forEach((node, i) => {
      renderData.push({
        type: 'label',
        name: node.displayName,
        idx: i,
      });
    });

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      title: {
        text: title,
        left: 'center',
        top: 6,
        textStyle: {
          fontSize: 16,
          fontWeight: 500,
          color: '#334155',
          fontFamily: "'Microsoft YaHei', sans-serif",
        },
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255,255,255,0.92)',
        borderColor: 'rgba(200,210,230,0.6)',
        borderWidth: 1,
        textStyle: { color: '#334155', fontSize: 13, fontFamily: "'Microsoft YaHei', sans-serif" },
        formatter: (p: { data?: Record<string, unknown> }) => {
          const d = p.data || {};
          if (d.type === 'ribbon') {
            return `${d.source} ↔ ${d.target}<br/>共现次数：<b>${d.value}</b><br/>提升度：${((d.lift as number) || 0).toFixed(2)}`;
          }
          if (d.type === 'sector') {
            return `<b>${d.name}</b><br/>关联总量：${d.value}`;
          }
          return (d.name as string) || '';
        },
      },
      series: [
        {
          type: 'custom',
          coordinateSystem: 'none',
          // renderItem 回调参数用 any，对齐模板库 JS（避免 ECharts 严格类型与二次贝塞尔计算冲突）
          renderItem: (params: any, api: any) => {
            const item = renderData[params.dataIndex];
            if (!item) return;

            const width = api.getWidth();
            const height = api.getHeight();
            const cyOffset = 10;
            const cx = width / 2;
            const cy = height / 2 + cyOffset;
            const rOut = Math.min(width, height) / 2 - 72;
            const rIn = rOut - 22;
            const sectorAngle = step * (1 - gap);

            if (item.type === 'ribbon') {
              const a1 = -Math.PI / 2 + (item.sIdx as number) * step;
              const a2 = -Math.PI / 2 + (item.tIdx as number) * step;

              let delta = a2 - a1;
              while (delta <= -Math.PI) delta += 2 * Math.PI;
              while (delta > Math.PI) delta -= 2 * Math.PI;
              const dAngle = Math.abs(delta);
              const midAngle = a1 + delta / 2;

              const maxRibbonAngle = step * 0.34;
              const minRibbonAngle = step * 0.18;
              const hw = Math.min(
                maxRibbonAngle / 2,
                Math.max(minRibbonAngle / 2, ((item.value as number) / maxLinkValue) * (maxRibbonAngle / 2)),
              );

              const p1 = polar(cx, cy, rIn, a1 - hw);
              const p2 = polar(cx, cy, rIn, a1 + hw);
              const p3 = polar(cx, cy, rIn, a2 - hw);
              const p4 = polar(cx, cy, rIn, a2 + hw);

              const controlFactor = 0.28 + 0.52 * Math.min(1, dAngle / (Math.PI * 0.85));
              const rControl = rIn * controlFactor;
              const c1 = polar(cx, cy, rControl, midAngle);

              const path = `M ${p1.x} ${p1.y} Q ${c1.x} ${c1.y} ${p3.x} ${p3.y} L ${p4.x} ${p4.y} Q ${c1.x} ${c1.y} ${p2.x} ${p2.y} Z`;

              return {
                type: 'path',
                shape: { pathData: path },
                style: {
                  fill: item.color,
                  opacity: Math.max(item.opacity as number, 0.38),
                  stroke: 'rgba(255,255,255,0.55)',
                  lineWidth: 1,
                },
                styleEmphasis: {
                  opacity: 0.88,
                  stroke: 'rgba(255,255,255,0.9)',
                  lineWidth: 1.5,
                  shadowBlur: 10,
                  shadowColor: item.color,
                },
                z2: 1,
              };
            }

            if (item.type === 'sector') {
              const a = -Math.PI / 2 + (item.idx as number) * step;
              return {
                type: 'sector',
                shape: {
                  cx,
                  cy,
                  r: rOut,
                  r0: rIn,
                  startAngle: a - sectorAngle / 2,
                  endAngle: a + sectorAngle / 2,
                },
                style: {
                  fill: item.color,
                  stroke: 'rgba(255,255,255,0.92)',
                  lineWidth: 2,
                },
                styleEmphasis: {
                  shadowBlur: 14,
                  shadowColor: item.color,
                  stroke: '#fff',
                  lineWidth: 3,
                },
                z2: 3,
              };
            }

            if (item.type === 'label') {
              const a = -Math.PI / 2 + (item.idx as number) * step;
              const r = rOut + 30;
              const pos = polar(cx, cy, r, a);
              const isRight = Math.cos(a) >= 0;
              return {
                type: 'text',
                style: {
                  text: item.name,
                  x: pos.x,
                  y: pos.y,
                  fill: '#475569',
                  fontSize: 10,
                  fontWeight: 400,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                  textAlign: isRight ? 'left' : 'right',
                  textVerticalAlign: 'middle',
                },
                z2: 4,
              };
            }
          },
          data: renderData,
          emphasis: { focus: 'self' },
        },
      ],
    };

    chart.setOption(option, true);

    // 4. 底部类目图例（HTML DOM，className 清理对齐气泡图）
    let legendEl = chartDom.querySelector('.ethereal-network-legend') as HTMLDivElement | null;
    if (legendEl) legendEl.remove();
    legendEl = document.createElement('div');
    legendEl.className = 'ethereal-network-legend';
    legendEl.style.cssText = `
      position: absolute;
      bottom: 12px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 10px;
      font-size: 10px;
      color: #64748B;
      font-family: 'Microsoft YaHei', sans-serif;
      max-width: 90%;
    `;
    const cats = Array.from(new Set(nodes.map((n) => n.category)));
    legendEl.innerHTML = cats
      .map(
        (cat) =>
          `<span style="display:inline-flex;align-items:center;gap:4px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${catColorMap.get(cat) || Palette.textMuted};display:inline-block;"></span>
            ${cat}
          </span>`,
      )
      .join('');
    chartDom.appendChild(legendEl);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartDom);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [chartNode]);

  return <div ref={ref} style={{ width: '100%', height, borderRadius: 24 }} />;
};

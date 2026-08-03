/**
 * 关联图组件（商品关联网络图 — 和弦图 Chord Diagram）
 * 数据来源：mock11.json → slot: ar_network （位于 association_rules 包）
 *
 * 设计风格：
 *   - 外圈扇区 = 商品 SKU，均匀分布在圆周上
 *   - 扇区之间保留白色间隙
 *   - 内部弦带 = 商品间的关联关系，颜色跟随源商品类目
 *   - 弦带越宽 = 共现次数越多
 *   - 毛玻璃卡片外壳，仙气柔雾风
 *
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中查找到的完整节点
 * @param {string} cardBgUrl - 卡片背景图路径
 * @param {string} titleText - 图表标题
 */
function renderEtherealNetworkChart(domId, chartNode, cardBgUrl, titleText = '') {
    const container = document.getElementById(domId);
    if (!container) return;

    // 1. 卡片样式接管
    container.style.backgroundImage = `url('${cardBgUrl}')`;
    container.style.backgroundSize = 'cover';
    container.style.backgroundPosition = 'center';
    container.style.borderRadius = '24px';
    container.style.backgroundColor = 'transparent';
    container.style.backdropFilter = 'blur(18px)';
    container.style.webkitBackdropFilter = 'blur(18px)';
    container.style.border = '1px solid rgba(255, 255, 255, 0.6)';
    container.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)';
    container.style.padding = '26px 30px 44px 30px';
    container.style.boxSizing = 'border-box';
    container.style.overflow = 'hidden';
    container.style.fontFamily = "'Microsoft YaHei', sans-serif";
    container.style.position = 'relative';

    // 2. 商品 → 类目映射 + 淡彩色配色
    function getCategory(name) {
        const map = {
            '美妆个护': ['口红', '面膜', '洗面奶', '精华液'],
            '服饰': ['连衣裙'],
            '运动户外': ['运动服', '跑步鞋', '瑜伽垫', '运动水壶'],
            '母婴': ['婴儿奶粉', '纸尿裤', '奶瓶'],
            '食品': ['纯牛奶', '果汁', '咖啡', '零食大礼包'],
            '宠物': ['狗粮', '猫砂', '宠物玩具'],
            '数码办公': ['电子书阅读器', '机械键盘', '无线鼠标', '护眼台灯'],
            '汽车用品': ['行车记录仪', '车载支架', '车载充电器'],
            '家居': ['玻璃水杯', '棉柔毛巾'],
            '图书文具': ['畅销小说', '金属书签', '手账笔记本']
        };
        for (const [cat, names] of Object.entries(map)) {
            if (names.some(n => name.includes(n))) return cat;
        }
        return '其他';
    }

    const CATEGORY_COLORS = {
        '美妆个护': '#F9A8D4',
        '服饰': '#FCD34D',
        '运动户外': '#FCA5A5',
        '母婴': '#C4B5FD',
        '食品': '#86EFAC',
        '宠物': '#FDBA74',
        '数码办公': '#7DD3FC',
        '汽车用品': '#A5B4FC',
        '家居': '#6EE7B7',
        '图书文具': '#F0ABFC',
        '其他': '#94A3B8'
    };

    // 3. 解析数据（优先使用带 option 的完整节点，同时用 chartNode.data 补全 lift）
    const series = (chartNode.option && chartNode.option.series && chartNode.option.series[0]) || null;

    let rawNodes = [];
    let rawLinks = [];

    // 边表优先从 chartNode.data 取（它包含 lift 字段）
    if (Array.isArray(chartNode.data)) {
        rawLinks = chartNode.data.map(l => ({ ...l }));
    }

    if (series) {
        if (Array.isArray(series.data) && series.data.length > 0) {
            rawNodes = series.data.map(n => ({ ...n }));
        }
        if (Array.isArray(series.links) && series.links.length > 0) {
            rawLinks = series.links.map(l => ({ ...l }));
        }
    }

    // 如果仍无节点数据，从边表自动构建
    if (rawNodes.length === 0 && rawLinks.length > 0) {
        const nameSet = new Set();
        rawLinks.forEach(l => { nameSet.add(l.source); nameSet.add(l.target); });
        rawNodes = Array.from(nameSet).map(name => ({ name }));
    }

    if (rawNodes.length === 0 || rawLinks.length === 0) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94A3B8;">无足够关联数据</div>';
        return;
    }

    // lift 补全映射
    const liftMap = new Map();
    if (Array.isArray(chartNode.data)) {
        chartNode.data.forEach(l => {
            if (l.lift !== undefined) {
                liftMap.set(`${l.source}→${l.target}`, l.lift);
            }
        });
    }

    // 4. 构造节点 / 连线
    const nodes = rawNodes.map(n => {
        const cat = getCategory(n.name);
        return {
            id: n.name,
            name: n.name,
            value: n.value || 0,
            category: cat,
            color: CATEGORY_COLORS[cat]
        };
    }).sort((a, b) => {
        // 按类目聚合，同一类目内按商品名排序
        if (a.category !== b.category) {
            return a.category.localeCompare(b.category, 'zh-CN');
        }
        return a.name.localeCompare(b.name, 'zh-CN');
    });

    const nodeMap = new Map(nodes.map((n, i) => [n.name, i]));

    const links = rawLinks.map(l => {
        const sIdx = nodeMap.get(l.source);
        const tIdx = nodeMap.get(l.target);
        if (sIdx === undefined || tIdx === undefined) return null;
        const lift = l.lift !== undefined ? l.lift : (liftMap.get(`${l.source}→${l.target}`) || 1);
        return {
            source: l.source,
            target: l.target,
            sIdx,
            tIdx,
            value: l.value || 0,
            lift
        };
    }).filter(Boolean);

    // 5. 创建 ECharts 容器
    const chartDom = document.createElement('div');
    chartDom.style.width = '100%';
    chartDom.style.height = '100%';
    container.appendChild(chartDom);

    const myChart = echarts.init(chartDom, null, {
        renderer: 'svg',
        devicePixelRatio: window.devicePixelRatio || 1
    });
    window.__echartsInstances = window.__echartsInstances || [];
    window.__echartsInstances.push(myChart);

    // 6. 和弦图布局工具
    function polar(cx, cy, r, angle) {
        return {
            x: cx + r * Math.cos(angle),
            y: cy + r * Math.sin(angle)
        };
    }

    const N = nodes.length;
    const gap = 0.14;                 // 扇区间隙比例
    const step = 2 * Math.PI / N;     // 每个节点占用的角度步长
    const maxLinkValue = Math.max(1, ...links.map(l => l.value));

    const renderData = [];

    // 6.1 弦带（先绘制，位于扇区下方）
    links.forEach(link => {
        renderData.push({
            type: 'ribbon',
            source: link.source,
            target: link.target,
            value: link.value,
            lift: link.lift,
            sIdx: link.sIdx,
            tIdx: link.tIdx,
            color: nodes[link.sIdx].color,
            opacity: link.lift > 1 ? 0.56 : 0.30
        });
    });

    // 6.2 外圈扇区
    nodes.forEach((node, i) => {
        renderData.push({
            type: 'sector',
            name: node.name,
            value: node.value,
            category: node.category,
            color: node.color,
            idx: i
        });
    });

    // 6.3 标签
    nodes.forEach((node, i) => {
        renderData.push({
            type: 'label',
            name: node.name,
            idx: i
        });
    });

    // 7. ECharts 配置
    const option = {
        backgroundColor: 'transparent',
        title: {
            text: titleText || chartNode.title || '商品关联网络图',
            left: 'center',
            top: 6,
            textStyle: {
                fontSize: 16,
                fontWeight: 500,
                color: '#334155',
                fontFamily: "'Microsoft YaHei', sans-serif"
            }
        },
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255,255,255,0.92)',
            borderColor: 'rgba(200,210,230,0.6)',
            borderWidth: 1,
            textStyle: { color: '#334155', fontSize: 13, fontFamily: "'Microsoft YaHei', sans-serif" },
            formatter: function(p) {
                const d = p.data || {};
                if (d.type === 'ribbon') {
                    return `${d.source} ↔ ${d.target}<br/>共现次数：<b>${d.value}</b><br/>提升度：${(d.lift || 0).toFixed(2)}`;
                }
                if (d.type === 'sector') {
                    return `<b>${d.name}</b><br/>类目：${d.category}<br/>关联总量：${d.value}`;
                }
                return d.name || '';
            }
        },
        series: [{
            type: 'custom',
            coordinateSystem: 'none',
            renderItem: function(params, api) {
                const item = renderData[params.dataIndex];
                if (!item) return;

                const width = api.getWidth();
                const height = api.getHeight();
                // 整体稍微下移，避免顶部标题与标签重叠
                const cyOffset = 10;
                const cx = width / 2;
                const cy = height / 2 + cyOffset;
                // 为标题、标签、图例留出足够边距
                const rOut = Math.min(width, height) / 2 - 72;
                const rIn = rOut - 22;
                const sectorAngle = step * (1 - gap);

                if (item.type === 'ribbon') {
                    const a1 = -Math.PI / 2 + item.sIdx * step;
                    const a2 = -Math.PI / 2 + item.tIdx * step;

                    // 取短弧的角度差与中点
                    let delta = a2 - a1;
                    while (delta <= -Math.PI) delta += 2 * Math.PI;
                    while (delta > Math.PI) delta -= 2 * Math.PI;
                    const dAngle = Math.abs(delta);
                    const midAngle = a1 + delta / 2;

                    // 弦带宽度：保证最小宽度，避免中间过度收窄导致"断开"
                    const maxRibbonAngle = step * 0.34;
                    const minRibbonAngle = step * 0.18;
                    const hw = Math.min(
                        maxRibbonAngle / 2,
                        Math.max(minRibbonAngle / 2, (item.value / maxLinkValue) * maxRibbonAngle / 2)
                    );

                    const p1 = polar(cx, cy, rIn, a1 - hw);
                    const p2 = polar(cx, cy, rIn, a1 + hw);
                    const p3 = polar(cx, cy, rIn, a2 - hw);
                    const p4 = polar(cx, cy, rIn, a2 + hw);

                    // 控制点沿短弧中点方向内收，但不到圆心，保持弦带中间仍有宽度
                    const controlFactor = 0.28 + 0.52 * Math.min(1, dAngle / (Math.PI * 0.85));
                    const rControl = rIn * controlFactor;
                    const c1 = polar(cx, cy, rControl, midAngle);

                    // 二次贝塞尔弦带
                    const path = `M ${p1.x} ${p1.y} Q ${c1.x} ${c1.y} ${p3.x} ${p3.y} L ${p4.x} ${p4.y} Q ${c1.x} ${c1.y} ${p2.x} ${p2.y} Z`;

                    return {
                        type: 'path',
                        shape: { pathData: path },
                        style: {
                            fill: item.color,
                            opacity: Math.max(item.opacity, 0.38),
                            stroke: 'rgba(255,255,255,0.55)',
                            lineWidth: 1
                        },
                        styleEmphasis: {
                            opacity: 0.88,
                            stroke: 'rgba(255,255,255,0.9)',
                            lineWidth: 1.5,
                            shadowBlur: 10,
                            shadowColor: item.color
                        },
                        z2: 1
                    };
                }

                if (item.type === 'sector') {
                    const a = -Math.PI / 2 + item.idx * step;
                    return {
                        type: 'sector',
                        shape: {
                            cx, cy,
                            r: rOut,
                            r0: rIn,
                            startAngle: a - sectorAngle / 2,
                            endAngle: a + sectorAngle / 2
                        },
                        style: {
                            fill: item.color,
                            stroke: 'rgba(255,255,255,0.92)',
                            lineWidth: 2
                        },
                        styleEmphasis: {
                            shadowBlur: 14,
                            shadowColor: item.color,
                            stroke: '#fff',
                            lineWidth: 3
                        },
                        z2: 3
                    };
                }

                if (item.type === 'label') {
                    const a = -Math.PI / 2 + item.idx * step;
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
                            textVerticalAlign: 'middle'
                        },
                        z2: 4
                    };
                }
            },
            data: renderData,
            emphasis: {
                focus: 'self'
            }
        }]
    };

    myChart.setOption(option);

    // 8. 底部类目图例（HTML DOM）
    const legend = document.createElement('div');
    legend.style.cssText = `
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
    const cats = [...new Set(nodes.map(n => n.category))];
    legend.innerHTML = cats.map(cat => `
        <span style="display:inline-flex;align-items:center;gap:4px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${CATEGORY_COLORS[cat]};display:inline-block;"></span>
            ${cat}
        </span>
    `).join('');
    container.appendChild(legend);

    window.addEventListener('resize', () => myChart.resize());
}

/**
 * 气泡矩阵图组件（散点图，X=价值层，Y=流失状态，气泡大小=人数，颜色=挽回优先级）
 * 数据来源：mock9.json → slot: bubble_matrix__retention_priority
 *
 * 设计风格：淡彩系气泡（柠檬黄/天蓝/淡紫/青柠绿/玫瑰红/樱花粉），毛玻璃卡片外壳
 *
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中查找到的完整节点（含 data / chart_config / x / y / color）
 * @param {string} cardBgUrl - 卡片背景图路径
 * @param {string} titleText - 图表标题
 */
function renderEtherealBubbleChart(domId, chartNode, cardBgUrl, titleText = '') {
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
    container.style.padding = '30px 36px';
    container.style.boxSizing = 'border-box';
    container.style.overflow = 'hidden';
    container.style.position = 'relative';

    // 2. 解析数据
    const rawData = chartNode.data || [];
    const xField = chartNode.x || '价值层';
    const yField = chartNode.y || '流失状态';
    const colorField = chartNode.color || '挽回优先级';
    const sizeField = '人数';

    // 收集 X/Y 轴类别、尺寸和优先级标签
    const xCategories = [];
    const yCategories = [];
    const sizeValues = [];
    const priorityLabels = [];

    rawData.forEach(item => {
        const xv = item[xField];
        const yv = item[yField];
        const sv = item[sizeField];
        const cv = item[colorField];
        
        if (xv && !xCategories.includes(xv)) xCategories.push(xv);
        if (yv && !yCategories.includes(yv)) yCategories.push(yv);
        if (sv !== undefined) sizeValues.push(sv);
        if (cv !== undefined && cv !== null && !priorityLabels.includes(cv)) priorityLabels.push(cv);
    });

    // ── 配色系统：按挽回优先级严格映射 ──────────────────────────────
    const BASE_COLORS = [
        '#FDE047', // 柠檬黄
        '#5AA9D6', // 天蓝
        '#A78BFA', // 淡紫
        '#A3E635', // 青柠绿
        '#FB7185', // 玫瑰红
        '#FECDD3'  // 樱花粉
    ];

    const priorityColorMap = {};
    priorityLabels.forEach((label, idx) => {
        priorityColorMap[label] = BASE_COLORS[idx % BASE_COLORS.length];
    });

    function getBubbleColor(priority) {
        return priorityColorMap[priority] || BASE_COLORS[0];
    }

    // ── X 轴排序：低价值 → 中价值 → 高价值 ──────────────────
    const xOrder = ['低价值', '中价值', '高价值'];
    const sortedXCategories = [...xCategories].sort((a, b) => {
        const idxA = xOrder.indexOf(a);
        const idxB = xOrder.indexOf(b);
        return (idxA !== -1 ? idxA : 999) - (idxB !== -1 ? idxB : 999);
    });

    // ── Y 轴排序：ECharts yAxis默认自下而上渲染，因此底部放首位 ──
    const yOrder = ['已流失', '流失预警']; 
    const sortedYCategories = [...yCategories].sort((a, b) => {
        const idxA = yOrder.indexOf(a);
        const idxB = yOrder.indexOf(b);
        return (idxA !== -1 ? idxA : 999) - (idxB !== -1 ? idxB : 999);
    });

    // ── 气泡大小缩放 ─────────────────────────────────────────
    const minSize = 20;
    const maxSize = 75;
    const minCount = sizeValues.length > 0 ? Math.min(...sizeValues) : 1;
    const maxCount = sizeValues.length > 0 ? Math.max(...sizeValues) : 10;

    function scaleSize(count) {
        if (maxCount === minCount) return (minSize + maxSize) / 2;
        return minSize + ((count - minCount) / (maxCount - minCount)) * (maxSize - minSize);
    }

    // ── 构建 scatter 数据 ─────────────────────────────────────
    const scatterData = rawData.map(item => {
        const xv = item[xField];
        const yv = item[yField];
        const sv = item[sizeField] || 1;
        const priority = item[colorField];
        
        const xi = sortedXCategories.indexOf(xv);
        const yi = sortedYCategories.indexOf(yv);
        const bubbleColor = getBubbleColor(priority);

        return {
            value: [xi, yi, sv],
            rawXLabel: xv,
            rawYLabel: yv,
            priority: priority, // 注入优先级数据供 tooltip 使用
            name: `${xv} | ${yv}`,
            symbolSize: scaleSize(sv),
            itemStyle: {
                color: bubbleColor,
                opacity: 0.38,
                borderColor: 'rgba(255,255,255,0.75)',
                borderWidth: 2.5,
                shadowBlur: 20,
                shadowColor: 'rgba(0,0,0,0.06)'
            },
            label: { show: false }
        };
    });

    // ── ECharts 初始化与配置 ─────────────────────────────────
    const myChart = echarts.init(container);

    const option = {
        backgroundColor: 'transparent',
        title: {
            text: titleText || chartNode.title || '气泡矩阵',
            left: 'center',
            top: 8,
            textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 }
        },
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255, 255, 255, 0.96)',
            borderColor: '#E2E8F0',
            borderWidth: 1,
            padding: [12, 16],
            textStyle: { color: '#475569', fontWeight: 'bold' },
            extraCssText: 'box-shadow: 0 10px 20px -3px rgba(0,0,0,0.12); border-radius: 14px;',
            formatter: function(params) {
                const d = params.data;
                const priority = d.priority || '—';
                const dc = getBubbleColor(priority);
                
                return `<div style="margin-bottom:6px;font-weight:700;color:#1E293B;font-size:13px;">
                    ${d.rawXLabel} × ${d.rawYLabel}
                </div>
                <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
                    <span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:${dc};"></span>
                    <span>${colorField}: <b>${priority}</b></span>
                </div>
                <div style="margin:3px 0;">${sizeField}: <b>${d.value[2]}</b></div>`;
            }
        },
        toolbox: {
            right: 24, top: 12, z: 9999,
            feature: {
                saveAsImage: { title: '下载图片', show: true },
                myExport: {
                    show: true, title: '导出数据',
                    icon: 'path://M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
                    onclick: function() {
                        const exportData = rawData.map(d => ({
                            [xField]: d[xField], [yField]: d[yField],
                            [colorField]: d[colorField], [sizeField]: d[sizeField]
                        }));
                        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url; a.download = 'bubble_matrix_data.json'; a.click();
                    }
                }
            }
        },
        legend: { show: false }, 
        grid: {
            top: 60,
            left: 100,
            right: 160, 
            bottom: 60,
            containLabel: false
        },
        xAxis: {
            type: 'category',
            data: sortedXCategories,
            name: xField,
            nameLocation: 'middle',
            nameGap: 38,
            nameTextStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 },
            axisLabel: {
                show: true,
                color: '#334155', fontWeight: 600, fontSize: 12, margin: 14
            },
            axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)', width: 1.5 } },
            axisTick: { show: true, length: 5, lineStyle: { color: 'rgba(148,163,184,0.35)' } },
            splitLine: { lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.22)', width: 1 } }
        },
        yAxis: {
            type: 'category',
            data: sortedYCategories,
            name: yField,
            nameLocation: 'middle',
            nameGap: 52,
            nameTextStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 },
            axisLabel: {
                show: true,
                color: '#334155', fontWeight: 600, fontSize: 12, margin: 14
            },
            axisLine: { lineStyle: { color: 'rgba(148,163,184,0.45)', width: 1.5 } },
            axisTick: { show: true, length: 5, lineStyle: { color: 'rgba(148,163,184,0.35)' } },
            splitLine: { lineStyle: { type: 'dashed', color: 'rgba(148,163,184,0.22)', width: 1 } }
        },
        series: [{
            type: 'scatter',
            data: scatterData,
            symbol: 'circle',
            symbolKeepAspect: true,
            emphasis: {
                scale: 1.15,
                itemStyle: {
                    shadowBlur: 22,
                    shadowColor: 'rgba(0,0,0,0.18)',
                    borderColor: '#fff',
                    borderWidth: 3
                }
            },
            animationDelay: function(idx) { return idx * 80; },
            animationEasingUpdate: 'elasticOut'
        }],
        animationDuration: 1200,
        animationEasing: 'cubicOut'
    };

    myChart.setOption(option, true);
    window.addEventListener('resize', () => myChart.resize());

    // ── HTML DOM 图例 ─────────────────────────────────────────
    let existingLegend = document.getElementById(domId + '-legend');
    if (existingLegend) existingLegend.remove();

    const legendEl = document.createElement('div');
    legendEl.id = domId + '-legend';
    legendEl.style.cssText = `
        position: absolute;
        right: 32px;
        top: 85px;
        z-index: 100;
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    `;
    
    let legendHtml = `<div style="font-weight:bold;font-size:13px;color:#1E293B;margin-bottom:12px;">${colorField}</div>`;
    
    // 渲染以挽回优先级为维度的图例项
    priorityLabels.forEach(label => {
        const c = getBubbleColor(label);
        legendHtml += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${c};opacity:0.85;flex-shrink:0;"></span>
            <span style="font-size:13px;color:#334155;font-weight:500;">${label}</span>
        </div>`;
    });
    
    legendEl.innerHTML = legendHtml;
    container.appendChild(legendEl);
}
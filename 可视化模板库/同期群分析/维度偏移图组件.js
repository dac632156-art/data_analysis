/**
 * 维度偏移图组件（水平条形图，正负值分色，按维度分组）
 * 数据来源：mock9.json → slot: hbar__attr_dim_offset
 *
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中查找到的完整节点（含 data / chart_config）
 * @param {string} cardBgUrl - 卡片背景图路径
 * @param {string} titleText - 图表标题
 */
function renderEtherealDimOffsetChart(domId, chartNode, cardBgUrl, titleText = '') {
    const container = document.getElementById(domId);
    if (!container) return;

    // 1. 卡片样式接管（与项目其他组件统一风格）
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

    // 2. 解析数据

    // 2. 解析数据
    let rawData = chartNode.data || [];

    // 支持按维度筛选：只取指定维度的数据
    const targetDim = (chartNode._filter && chartNode._filter['维度']) || null;
    if (targetDim) {
        rawData = rawData.filter(item => (item['维度'] || '') === targetDim);
    }

    const dimsConfig = (chartNode.chart_config && chartNode.chart_config.dims) || [];

    // 按维度分组
    const dimGroups = {};
    rawData.forEach(item => {
        const dim = item['维度'] || '未知';
        if (!dimGroups[dim]) dimGroups[dim] = [];
        dimGroups[dim].push({
            name: item['维度取值'] || '',
            value: item['偏移值'] !== undefined ? item['偏移值'] : 0
        });
    });

    // 确定维度顺序：优先用 chart_config.dims，否则用数据出现顺序
    const orderedDims = dimsConfig.length > 0
        ? dimsConfig.filter(d => dimGroups[d])
        : Object.keys(dimGroups);

    // 构建系列数据（每个维度一个 series）
    const seriesData = [];
    let allCategories = []; // 收集所有类别名用于去重

    orderedDims.forEach((dimName, dimIdx) => {
        const group = dimGroups[dimName];
        group.forEach(item => {
            if (!allCategories.includes(item.name)) allCategories.push(item.name);
            seriesData.push({
                category: item.name,
                value: item.value,
                dimension: dimName,
                dimIndex: dimIdx
            });
        });
    });

    // 按偏移值降序排列（大的在上面）
    seriesData.sort((a, b) => b.value - a.value);
    const sortedCategories = seriesData.map(d => d.category);
    const sortedValues = seriesData.map(d => d.value);
    const sortedDims = seriesData.map(d => d.dimension);

    // 维度配色方案（与项目整体风格一致）
    const dimPalette = [
        '#FCCDDF', // 城市粉（正值）
        '#C8E1F5', // 省份蓝
        '#D7EFE5', // 类目绿
        '#E2C9F3', // 备用紫
        '#FCDDC8', // 备用橙
        '#BAC2F0'  // 备用靛
    ];

    // 负值青柠绿（设计图风格：负值用绿色系）
    const NEG_COLOR = '#A7E6D7'; // 青柠绿
    const POS_COLOR = '#FCCDDF'; // 粉红色

    function getDimColor(dimName) {
        const idx = orderedDims.indexOf(dimName);
        return dimPalette[idx % dimPalette.length];
    }

    // 正负值颜色加深/变淡处理
    function getBarColor(baseColor, value) {
        const isPositive = value >= 0;
        // 正值用原色稍深，负值用灰调
        if (isPositive) {
            return baseColor; // 保持明亮
        } else {
            // 负值稍微降低饱和度
            return baseColor.replace(')', ', 0.7)').replace('rgb', 'rgba');
        }
    }

    // 3. ECharts 初始化与配置
    const myChart = echarts.init(container);

    const barData = sortedValues.map((val, i) => {
        const isPositive = val >= 0;
        // 正值粉红，负值青柠绿（与设计图一致）
        const barColor = isPositive ? POS_COLOR : NEG_COLOR;
        return {
            value: val,
            itemStyle: {
                // 负值用纯色确保可见（不再依赖渐变）
                color: barColor,
                opacity: 0.85,
                borderRadius: isPositive ? [0, 6, 6, 0] : [6, 0, 0, 6],
                borderColor: 'rgba(255, 255, 255, 0.5)',
                borderWidth: 1
            },
            label: {
                show: true,
                position: isPositive ? 'right' : 'left',
                color: isPositive ? '#E11D48' : '#059669',
                fontWeight: 700,
                fontSize: 12,
                distance: 8,
                formatter: function(p) {
                    const v = p.value;
                    return (v >= 0 ? '+' : '') + v.toFixed(1);
                }
            }
        };
    });

    const option = {
        backgroundColor: 'transparent',
        title: {
            text: titleText || chartNode.title || '维度偏移分析',
            left: 'center',
            top: 8,
            textStyle: {
                color: '#1E293B',
                fontSize: 16,
                fontWeight: 600
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#E2E8F0',
            borderWidth: 1,
            padding: [10, 14],
            textStyle: { color: '#475569', fontWeight: 'bold' },
            extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border-radius: 12px;',
            formatter: function(params) {
                const p = params[0];
                const dimName = sortedDims[p.dataIndex];
                const color = getDimColor(dimName);
                const val = p.value;
                const sign = val >= 0 ? '+' : '';
                return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${color};"></span>
                    <span style="font-weight:700;">${p.name}</span>
                    <span style="color:#94A3B8;font-size:11px;">(${dimName})</span>
                </div>
                <div style="margin-top:4px;padding-top:4px;border-top:1px solid #E2E8F0;">
                    偏移值: <b style="color:${val >= 0 ? '#059669' : '#DC2626'}">${sign}${val.toFixed(1)}pp</b>
                </div>`;
            }
        },
        toolbox: {
            right: 20, top: 10, z: 9999,
            feature: {
                saveAsImage: { title: '下载图片', show: true },
                myExport: {
                    show: true, title: '导出数据',
                    icon: 'path://M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
                    onclick: function() {
                        const exportData = rawData.map(d => ({
                            维度: d['维度'],
                            维度取值: d['维度取值'],
                            偏移值: d['偏移值']
                        }));
                        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url; a.download = 'dim_offset_data.json'; a.click();
                    }
                }
            }
        },
        grid: {
            top: 56,
            left: 100,
            right: 56,
            bottom: 24,
            containLabel: false
        },
        xAxis: {
            type: 'value',
            position: 'top',
            min: function(value) {
                // 确保负值区域有足够空间显示柱子
                const minVal = value.min;
                return Math.min(minVal, -30);
            },
            max: function(value) {
                const maxVal = value.max;
                return Math.max(maxVal, 40);
            },
            axisLabel: {
                show: true,
                color: '#64748B',
                fontWeight: 500,
                fontSize: 12,
                formatter: function(v) { return v + ''; }
            },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: {
                show: true,
                lineStyle: {
                    type: 'dashed',
                    color: 'rgba(148, 163, 184, 0.25)',
                    width: 1
                }
            }
        },
        yAxis: {
            type: 'category',
            data: sortedCategories,
            inverse: true, // 大值在上
            axisLabel: {
                show: true,
                color: '#334155',
                fontWeight: 600,
                fontSize: 13,
                margin: 14,
                formatter: function(value) {
                    // 在标签后追加维度标识色点
                    const idx = sortedCategories.indexOf(value);
                    if (idx >= 0) {
                        const dimName = sortedDims[idx];
                        const color = getDimColor(dimName);
                        return `{${dimName}|${value}}`;
                    }
                    return value;
                },
                rich: {}
            },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        // 为每个维度创建 rich text 样式
        series: [{
            type: 'bar',
            data: barData,
            barWidth: 18,
            barGap: '20%',
            markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: {
                    color: '#94A3B8',
                    type: 'dashed',
                    width: 1
                },
                data: [{ xAxis: 0 }],
                label: { show: false }
            }
        }]
    };

    // 动态构建 yAxis rich 样式（为每个维度添加色块标记）
    const richStyles = {};
    orderedDims.forEach(dimName => {
        const color = getDimColor(dimName);
        richStyles[dimName] = {
            backgroundColor: color,
            padding: [2, 6],
            borderRadius: 3,
            color: '#1E293B',
            fontSize: 12,
            fontWeight: 500
        };
    });
    option.yAxis.axisLabel.rich = richStyles;

    myChart.setOption(option, true);
    window.addEventListener('resize', () => myChart.resize());
}

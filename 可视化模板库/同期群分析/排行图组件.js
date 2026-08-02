/**
 * 排行图组件（水平条形图，排名+名称+渐变条形+数值）
 * 数据来源：mock9.json → slot: clv_pareto
 *
 * 设计风格参考：淡彩渐变条形（粉→紫、蓝→青绿交替），毛玻璃卡片外壳
 *
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中查找到的完整节点（含 data / chart_config / x / y / color）
 * @param {string} cardBgUrl - 卡片背景图路径
 * @param {string} titleText - 图表标题
 */
function renderEtherealRankingChart(domId, chartNode, cardBgUrl, titleText = '') {
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

    // 2. 解析数据
    const rawData = (chartNode.data || []).slice(); // 拷贝避免修改原数据
    const rankField = chartNode.x || '排名';
    const valueField = chartNode.y || '价值';

    // 按数值降序排列（确保排行顺序正确）
    rawData.sort((a, b) => (parseFloat(b[valueField]) || 0) - (parseFloat(a[valueField]) || 0));

    const categories = rawData.map(item => item[rankField] || '');
    const values = rawData.map(item => parseFloat(item[valueField]) || 0);

    // ── 渐变色板（参考设计图：粉→紫 / 蓝→青绿 淡彩交替）──────
    // TOP1 → TOP15 淡彩渐变配色：低饱和、仙气柔雾风，相邻排名保持色相区分
    const GRADIENT_COLORS = [
        ['#FECDD3', '#E9D5FF'], // TOP1 粉 → 紫
        ['#BFDBFE', '#BBF7D0'], // TOP2 蓝 → 青绿
        ['#FDE68A', '#FBCFE8'], // TOP3 浅黄 → 粉红
        ['#FDE68A', '#BBF7D0'], // TOP4 浅黄 → 浅绿
        ['#FBCFE8', '#FED7AA'], // TOP5 粉红 → 蜜橙
        ['#BAE6FD', '#DDD6FE'], // TOP6 天蓝 → 淡紫
        ['#FED7AA', '#BBF7D0'], // TOP7 蜜橙 → 浅绿
        ['#DDD6FE', '#93C5FD'], // TOP8 淡紫 → 蓝
        ['#FDA4AF', '#FEF08A'], // TOP9 玫瑰 → 浅黄
        ['#A7F3D0', '#FBCFE8'], // TOP10 薄荷 → 粉红
        ['#FDBA74', '#C7D2FE'], // TOP11 橙 → 靛蓝
        ['#E9D5FF', '#BAE6FD'], // TOP12 薰衣草 → 天蓝
        ['#FECDD3', '#FDE68A'], // TOP13 粉 → 浅黄
        ['#93C5FD', '#FBCFE8'], // TOP14 蓝 → 粉红
        ['#F5D0FE', '#BBF7D0']  // TOP15 丁香 → 浅绿
    ];

    function getGradient(index) {
        const colors = GRADIENT_COLORS[index % GRADIENT_COLORS.length];
        return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: colors[0] },
            { offset: 1, color: colors[1] }
        ]);
    }

    // ── 构建 series data ─────────────────────────────────────
    const barData = values.map((val, idx) => ({
        value: val,
        itemStyle: {
            color: getGradient(idx),
            borderRadius: [20, 20, 20, 20], // 胶囊形：左右两端都圆，与右边形状一致
            opacity: 0.65,
            borderColor: 'rgba(255,255,255,0.6)',
            borderWidth: 1.5,
            shadowBlur: 16,
            shadowColor: 'rgba(0,0,0,0.07)',
            shadowOffsetY: 3
        },
        label: {
            show: true,
            position: 'right',
            formatter: function(p) {
                return formatNumber(p.value);
            },
            fontSize: 13,
            fontWeight: 600,
            color: '#475569',
            offset: [10, 0]
        }
    }));

    // 数值格式化
    function formatNumber(n) {
        if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
        if (n >= 1000) return n.toLocaleString('zh-CN');
        return String(n.toFixed(n % 1 === 0 ? 0 : 1));
    }

    // ── ECharts 初始化与配置 ─────────────────────────────────
    const myChart = echarts.init(container);

    const option = {
        backgroundColor: 'transparent',
        title: {
            text: titleText || chartNode.title || 'TOP 排行',
            left: 'center',
            top: 8,
            textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(255, 255, 255, 0.96)',
            borderColor: '#E2E8F0',
            borderWidth: 1,
            padding: [10, 14],
            textStyle: { color: '#475569', fontWeight: 'bold', fontSize: 13 },
            extraCssText: 'box-shadow: 0 8px 16px -3px rgba(0,0,0,0.12); border-radius: 12px;',
            formatter: function(params) {
                const d = params[0];
                return `<div style="font-weight:700;color:#1E293B;margin-bottom:4px;">${d.name}</div>
                    <div style="color:#64748B;">${valueField}: <b style="color:#1E293B;">${formatNumber(d.value)}</b></div>`;
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
                        const exportData = rawData.map(d => ({ [rankField]: d[rankField], [valueField]: d[valueField] }));
                        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url; a.download = 'ranking_data.json'; a.click();
                    }
                }
            }
        },
        grid: {
            top: 60,
            left: 70,
            right: 120,
            bottom: 30,
            containLabel: false
        },
        xAxis: {
            type: 'value',
            show: false // 隐藏 X 轴，数值通过 label 显示在条形右侧
        },
        yAxis: {
            type: 'category',
            data: categories.reverse(), // TOP1 在最上面
            inverse: false,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                show: true,
                color: '#334155',
                fontWeight: 600,
                fontSize: 14,
                margin: 12,
                formatter: function(name) {
                    // 提取排名数字和名称
                    const match = name.match(/^(TOP\d+)\s*(.*)$/);
                    if (match) {
                        const num = parseInt(match[1].replace('TOP', ''));
                        const label = match[2].trim();
                        return `{num|${num}.} {name|${label}}`;
                    }
                    return name;
                },
                rich: {
                    num: {
                        color: '#64748B',
                        fontWeight: 700,
                        fontSize: 14,
                        width: 28,
                        align: 'right'
                    },
                    name: {
                        color: '#1E293B',
                        fontWeight: 600,
                        fontSize: 14,
                        padding: [0, 0, 0, 6]
                    }
                }
            }
        },
        series: [{
            type: 'bar',
            data: barData.reverse(), // 与 Y 轴 categories 反转对应
            barWidth: '55%',
            barGap: '25%',
            emphasis: {
                itemStyle: {
                    opacity: 0.95,
                    shadowBlur: 18,
                    shadowColor: 'rgba(0,0,0,0.15)'
                }
            },
            animationDelay: function(idx) { return idx * 80; },
            animationEasing: 'elasticOut'
        }],
        animationDuration: 1200,
        animationEasing: 'cubicOut'
    };

    myChart.setOption(option, true);
    window.addEventListener('resize', () => myChart.resize());
}

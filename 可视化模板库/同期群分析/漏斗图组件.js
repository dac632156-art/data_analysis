/**
 * 漏斗图组件（转化漏斗，淡彩渐变漏斗层 + 右侧标签）
 * 数据来源：mock10.json → slot: funnel_core
 */
function renderEtherealFunnelChart(domId, chartNode, cardBgUrl, titleText = '') {
    const container = document.getElementById(domId);
    if (!container) return;

    // 1. 卡片样式接管（与其他组件统一毛玻璃风格）
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
    container.style.fontFamily = '"Microsoft YaHei", "PingFang SC", sans-serif';

    // 2. 解析数据
    const seriesData = (chartNode.option && chartNode.option.series && chartNode.option.series[0] && chartNode.option.series[0].data) || [];
    const totalValue = seriesData.length > 0 ? (seriesData[0].value || 1) : 1;

    // ── 淡彩渐变色板
    const FUNNEL_COLORS = [
        ['#FECDD3', '#FBCFE8'], 
        ['#BBF7D0', '#A7F3D0'], 
        ['#BAE6FD', '#BFDBFE'], 
        ['#DDD6FE', '#E9D5FF'], 
        ['#FECDD3', '#FDE68A']  
    ];

    function getFunnelColor(index) {
        const colors = FUNNEL_COLORS[index % FUNNEL_COLORS.length];
        return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: colors[0] },
            { offset: 1, color: colors[1] }
        ]);
    }

    function formatNumber(val) {
        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
        if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
        return String(val);
    }

    // 3. 构建 ECharts 配置
    const chartDom = document.createElement('div');
    chartDom.style.width = '100%';
    chartDom.style.height = '100%';
    container.appendChild(chartDom);

    const myChart = echarts.init(chartDom, null, {
        renderer: 'canvas',
        devicePixelRatio: window.devicePixelRatio > 1 ? window.devicePixelRatio : 2
    });
    window.__echartsInstances = window.__echartsInstances || [];
    window.__echartsInstances.push(myChart);

    const option = {
        title: {
            text: titleText,
            left: 'center',
            top: 8,
            textStyle: {
                fontSize: 16,
                fontWeight: 'bold', // 标题也加粗一点提升层级
                color: '#334155',
                fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif'
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: function(p) {
                const pct = ((p.value / totalValue) * 100).toFixed(0);
                return `<b>${p.name}</b><br/>数值: ${formatNumber(p.value)}<br/>占比: ${pct}%`;
            },
            backgroundColor: 'rgba(255,255,255,0.92)',
            borderColor: 'rgba(200,210,230,0.6)',
            borderWidth: 1,
            textStyle: { color: '#334155', fontSize: 13 }
        },
        series: [{
            type: 'funnel',
            left: '5%',
            right: '40%',
            top: 56,
            bottom: 24,
            min: 0,
            max: totalValue,
            sort: 'descending',
            minSize: '35%',
            maxSize: '100%',
            gap: 18, 
            label: {
                show: true,
                position: 'inside',
                formatter: '{b}',
                fontSize: 14,
                fontWeight: 'bold', // 强制加粗
                color: '#334155',
                fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif', // 补充备用字体增强兼容性
                textBorderColor: 'transparent',
                textBorderWidth: 0,
                textShadowColor: 'transparent', 
                textShadowBlur: 0
            },
            labelLine: {
                show: false
            },
            itemStyle: {
                borderColor: 'rgba(255,255,255,0.9)',
                borderWidth: 1,
                shadowBlur: 14,
                shadowColor: 'rgba(0,0,0,0.06)',
                shadowOffsetY: 2
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 28,
                    shadowColor: 'rgba(0,0,0,0.12)'
                },
                label: { 
                    fontSize: 15, 
                    fontWeight: 'bold', // Hover 状态保持加粗
                    fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif',
                    textBorderColor: 'transparent',
                    textBorderWidth: 0, 
                    textShadowColor: 'transparent',
                    textShadowBlur: 0
                }
            },
            data: seriesData.map((item, idx) => ({
                name: item.name,
                value: item.value,
                itemStyle: {
                    color: getFunnelColor(idx),
                    opacity: 0.82
                }
            }))
        }]
    };

    myChart.setOption(option);

    // 4. 右侧标签层
    const labelContainer = document.createElement('div');
    labelContainer.style.cssText = `
        position: absolute;
        right: 28px;
        top: 58px;
        display: flex;
        flex-direction: column;
        gap: 0;
        pointer-events: none;
    `;

    seriesData.forEach((item, idx) => {
        const pct = ((item.value / totalValue) * 100).toFixed(0);
        const row = document.createElement('div');
        row.style.cssText = `
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            padding: 5px 0;
            border-left: 1px solid rgba(148,163,184,0.25);
            padding-left: 12px;
        `;
        row.innerHTML = `
            <div style="font-size:12px;font-weight:bold;color:#475569;font-family:'Microsoft YaHei', 'PingFang SC', sans-serif;">${item.name.toUpperCase()}</div>
            <div style="font-size:11px;color:#94A3B8;margin-top:3px;font-family:'Microsoft YaHei', 'PingFang SC', sans-serif;">${pct}% CTR (${formatNumber(item.value)})</div>
        `;
        labelContainer.appendChild(row);
    });

    container.appendChild(labelContainer);

    // 底部时间标注
    const footer = document.createElement('div');
    footer.style.cssText = `
        position: absolute;
        bottom: 14px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 11px;
        color: #94A3B8;
        letter-spacing: 0.5px;
        font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
    `;
    footer.textContent = 'Last 30 Days  |  Monthly Data';
    container.appendChild(footer);

    window.addEventListener('resize', () => myChart.resize());
}
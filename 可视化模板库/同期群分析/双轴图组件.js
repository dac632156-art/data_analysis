/**
 * 通用仙气高级双轴图渲染组件（净GMV vs 净毛利）
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中提取的完整图表节点
 * @param {string} cardBgUrl - 卡片背景路径（预留）
 */
async function renderEtherealDualAxisChart(domId, chartNode, cardBgUrl) {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    // 样式接管（毛玻璃卡片风格）
    chartDom.style.background = 'rgba(255, 255, 255, 0.45)';
    chartDom.style.backdropFilter = 'blur(24px)';
    chartDom.style.webkitBackdropFilter = 'blur(24px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.8)';
    chartDom.style.borderRadius = '24px';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.9)';
    chartDom.style.padding = '30px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.display = 'flex';
    chartDom.style.flexDirection = 'column';
    chartDom.style.gap = '20px';

    const myChart = echarts.init(chartDom);

    try {
        // 智能适配 JSON 中的 data 数组结构（匹配 cohort_c_dual 格式）
        let xAxisData = [];
        let gmvData = [];
        let profitData = [];

        if (chartNode.data && Array.isArray(chartNode.data)) {
            const xField = chartNode.x || '首单月';
            xAxisData = chartNode.data.map(item => item[xField] || '');
            gmvData = chartNode.data.map(item => Number(item['净GMV'] || item.gmv || 0));
            profitData = chartNode.data.map(item => Number(item['净毛利'] || item.profit || 0));
        } else if (chartNode.option) {
            xAxisData = chartNode.option.xAxis?.data || [];
            gmvData = chartNode.option.series?.[0]?.data || [];
            profitData = chartNode.option.series?.[1]?.data || [];
        }

        // 动态注入精美头部与 KPI 结构
        chartDom.innerHTML = `
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0,0,0,0.05); padding-bottom: 15px;">
                <div class="title" style="font-size: 18px; font-weight: 700; color: #1E293B; letter-spacing: 0.5px; text-transform: uppercase;">
                    ${chartNode.title || 'Net GMV & Net Profit'} <span style="color: #94A3B8; font-weight: 500; text-transform: none; margin-left: 8px;">| 净GMV与净毛利对比</span>
                </div>
                <div class="btn-select" style="background: rgba(255, 255, 255, 0.6); border: 1px solid rgba(255, 255, 255, 0.9); padding: 6px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #475569;">
                    Cohort View
                </div>
            </div>

            <div class="kpi-row" style="display: flex; justify-content: space-around; align-items: center; padding: 5px 20px 0;">
                <div class="kpi-item" style="text-align:center; display:flex; flex-direction:column; gap:4px;">
                    <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Total Net GMV</div>
                    <div id="${domId}-gmv" style="font-size:26px; color:#0F172A; font-weight:700;">--</div>
                </div>
                <div class="kpi-item" style="text-align:center; display:flex; flex-direction:column; gap:4px;">
                    <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Total Net Profit</div>
                    <div id="${domId}-profit" style="font-size:26px; color:#0F172A; font-weight:700;">--</div>
                </div>
                <div class="kpi-item" style="text-align:center; display:flex; flex-direction:column; gap:4px;">
                    <div style="font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase;">Avg. Profit Margin</div>
                    <div id="${domId}-margin" style="font-size:26px; color:#0F172A; font-weight:700;">--</div>
                </div>
            </div>

            <div id="${domId}-chart" style="width: 100%; height: 380px;"></div>
        `;

        // 计算并实时填充 KPI 数据
        const totalGMV = gmvData.reduce((a, b) => a + (Number(b) || 0), 0);
        const totalProfit = profitData.reduce((a, b) => a + (Number(b) || 0), 0);
        const avgMargin = totalGMV > 0 ? (totalProfit / totalGMV) * 100 : 0;

        document.getElementById(`${domId}-gmv`).innerText = '¥' + (totalGMV / 1000).toFixed(1) + 'K';
        document.getElementById(`${domId}-profit`).innerText = '¥' + (totalProfit / 1000).toFixed(1) + 'K';
        document.getElementById(`${domId}-margin`).innerText = avgMargin.toFixed(1) + '%';

        // 初始化实际的 ECharts 实例
        const innerChart = echarts.init(document.getElementById(`${domId}-chart`));

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                borderColor: '#E2E8F0',
                borderWidth: 1,
                padding: [12, 16],
                textStyle: { color: '#475569', fontWeight: 'bold' },
                extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px); border-radius: 12px;',
                axisPointer: { type: 'none' },
                formatter: function (params) {
                    let html = `<div style="margin-bottom:8px;color:#64748B;font-size:13px;">${params[0].name}</div>`;
                    params.forEach(item => {
                        let marker = item.marker;
                        if (item.seriesName.includes('Profit') || item.seriesName.includes('净毛利')) {
                            marker = '<span style="display:inline-block;margin-right:6px;border-radius:50%;width:10px;height:10px;box-sizing:border-box;background-color:#fff;border:2px solid #F472B6;"></span>';
                        }
                        let valueStr = Number(item.value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:4px;">
                                    <span style="display:flex;align-items:center;">${marker}${item.seriesName}</span>
                                    <span style="color:#0F172A;font-weight:700;">${valueStr}</span>
                                 </div>`;
                    });
                    return html;
                }
            },
            legend: {
                data: ['Net GMV (净GMV)', 'Net Profit (净毛利)'],
                bottom: 0,
                itemGap: 30,
                textStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 },
                icon: 'circle'
            },
            grid: { top: 30, left: 10, right: 10, bottom: 40, containLabel: true },
            xAxis: {
                type: 'category',
                data: xAxisData,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: { color: '#64748B', fontWeight: 600, fontSize: 12, margin: 16 }
            },
            yAxis: [
                {
                    type: 'value',
                    name: 'NET GMV (¥)',
                    nameTextStyle: { color: '#94A3B8', fontWeight: 600, fontSize: 11, padding: [0, 0, 0, 30] },
                    position: 'left',
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#94A3B8', fontWeight: 600, formatter: (val) => (val === 0 ? '0' : (val / 1000) + 'K') },
                    splitLine: { lineStyle: { type: 'dashed', color: 'rgba(0, 0, 0, 0.05)' } }
                },
                {
                    type: 'value',
                    name: 'NET PROFIT (¥)',
                    nameTextStyle: { color: '#94A3B8', fontWeight: 600, fontSize: 11, padding: [0, 30, 0, 0] },
                    position: 'right',
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#94A3B8', fontWeight: 600, formatter: (val) => (val === 0 ? '0' : (val / 1000) + 'K') },
                    splitLine: { show: false }
                }
            ],
            series: [
                {
                    name: 'Net GMV (净GMV)',
                    type: 'bar',
                    yAxisIndex: 0,
                    data: gmvData,
                    barWidth: 26,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(195, 225, 250, 0.95)' },
                            { offset: 1, color: 'rgba(195, 225, 250, 0.6)' }
                        ]),
                        borderRadius: 14
                    }
                },
                {
                    name: 'Net Profit (净毛利)',
                    type: 'line',
                    yAxisIndex: 1,
                    data: profitData,
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 8,
                    itemStyle: {
                        color: '#ffffff',
                        borderColor: '#F472B6',
                        borderWidth: 2,
                        shadowColor: 'rgba(244, 114, 182, 0.8)',
                        shadowBlur: 6
                    },
                    lineStyle: {
                        color: '#F472B6',
                        width: 3,
                        shadowColor: 'rgba(244, 114, 182, 0.3)',
                        shadowBlur: 10,
                        shadowOffsetY: 6
                    }
                }
            ]
        };

        innerChart.setOption(option);
        window.addEventListener('resize', () => innerChart.resize());

    } catch (err) {
        console.error("双轴图渲染失败:", err);
    }
}
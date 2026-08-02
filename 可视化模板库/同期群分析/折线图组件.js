/**
 * 通用仙气果冻质感折线图组件
 * 兼容扁平 data 数组 (按 group 分组) 或标准 option 结构
 */
async function renderEtherealLineChart(domId, chartNode, cardBgUrl) {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    // 外层卡片样式接管（毛玻璃卡片风格）
    chartDom.style.background = 'rgba(255, 255, 255, 0.4)';
    chartDom.style.backdropFilter = 'blur(20px)';
    chartDom.style.webkitBackdropFilter = 'blur(20px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.8)';
    chartDom.style.borderRadius = '24px';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.9)';
    chartDom.style.padding = '40px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.display = 'flex';
    chartDom.style.flexDirection = 'column';
    chartDom.style.gap = '20px';

    // 内部注入标题与固定高度的图表挂载容器
    chartDom.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="color: #475569; font-size: 20px; font-weight: bold; font-family: sans-serif;">
                ${chartNode.title || 'Retained Users by Channel'}
            </div>
            <div title="下载" style="cursor: pointer; color: #64748B;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            </div>
        </div>
        <div id="${domId}-inner" style="width: 100%; height: 440px;"></div>
    `;

    const innerChart = echarts.init(document.getElementById(`${domId}-inner`));

    try {
        innerChart.clear();

        let xAxisData = [];
        let seriesConfigs = [];
        const customPalette = ['#FCCDDF', '#C8E1F5', '#E2C9F3', '#D7EFE5', '#FCDDC8', '#E8C9CE', '#F9F1C6', '#BAC2F0'];

        // 🚀 核心逻辑：解析你的 data 数组（解决空图表问题）
        if (chartNode.data && Array.isArray(chartNode.data)) {
            const xField = chartNode.x || '统计月'; // 横轴字段
            const yField = chartNode.y || 'value';   // 数值字段
            
            // 提取所有唯一的时间点作为 X 轴
            const xSet = new Set();
            chartNode.data.forEach(item => xSet.add(item[xField]));
            xAxisData = Array.from(xSet).sort(); // 确保时间顺序

            // 按 group 分组数据
            const groupMap = {};
            chartNode.data.forEach(item => {
                const groupName = item.group || '默认组';
                if (!groupMap[groupName]) {
                    groupMap[groupName] = {};
                }
                groupMap[groupName][item[xField]] = Number(item[yField] || 0);
            });

            // 组装成 series
            let colorIndex = 0;
            for (const groupName in groupMap) {
                const color = customPalette[colorIndex % customPalette.length];
                const seriesData = xAxisData.map(xVal => groupMap[groupName][xVal] || 0); // 对齐 X 轴数据
                
                seriesConfigs.push({
                    name: groupName,
                    type: 'line',
                    data: seriesData,
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 10,
                    showSymbol: true,
                    itemStyle: {
                        color: '#ffffff',
                        borderColor: color,
                        borderWidth: 3,
                        shadowColor: color + '80',
                        shadowBlur: 10
                    },
                    lineStyle: {
                        color: color,
                        width: 3,
                        shadowColor: color + '50',
                        shadowBlur: 12,
                        shadowOffsetY: 4
                    }
                });
                colorIndex++;
            }
        } else if (chartNode.option) {
            // 兼容以前的 option 格式
            const rawOption = chartNode.option;
            xAxisData = rawOption.xAxis?.data || [];
            seriesConfigs = (rawOption.series || []).map((s, index) => {
                const color = customPalette[index % customPalette.length];
                return {
                    name: s.name,
                    type: 'line',
                    data: s.data,
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 10,
                    showSymbol: true,
                    itemStyle: {
                        color: '#ffffff',
                        borderColor: color,
                        borderWidth: 3,
                        shadowColor: color + '80',
                        shadowBlur: 10
                    },
                    lineStyle: {
                        color: color,
                        width: 3,
                        shadowColor: color + '50',
                        shadowBlur: 12,
                        shadowOffsetY: 4
                    }
                };
            });
        }

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                borderColor: '#E2E8F0',
                borderWidth: 1,
                padding: [12, 16],
                textStyle: { color: '#475569', fontWeight: 'bold' },
                extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px); border-radius: 12px;'
            },
            legend: {
                show: true,
                bottom: 0,
                icon: 'circle',
                itemWidth: 12,
                itemHeight: 12,
                itemGap: 20,
                textStyle: { color: '#64748B', fontWeight: 600, fontSize: 13 }
            },
            grid: { top: 20, left: 20, right: 20, bottom: 50, containLabel: true },
            xAxis: {
                type: 'category',
                data: xAxisData,
                boundaryGap: false,
                axisLabel: { color: '#94A3B8', fontWeight: 600, fontSize: 13, margin: 16 },
                axisLine: { show: false },
                axisTick: { show: false }
            },
            yAxis: {
                type: 'value',
                axisLabel: { color: '#94A3B8', fontWeight: 600, fontSize: 13 },
                splitLine: { lineStyle: { type: 'dashed', color: 'rgba(0,0,0,0.06)' } },
                axisLine: { show: false },
                axisTick: { show: false }
            },
            series: seriesConfigs
        };

        innerChart.setOption(option, true);
        window.addEventListener('resize', () => innerChart.resize());

    } catch (err) {
        console.error("折线图渲染失败:", err);
    }
}
/**
 * 通用果冻光感柱状图渲染组件（兼容双结构）
 */
async function renderEtherealBarChart(domId, chartNode, cardBgUrl, titleText = '') {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    // 样式接管
    chartDom.style.backgroundImage = `url('${cardBgUrl}')`;
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.background = 'rgba(255, 255, 255, 0.32)';
    chartDom.style.backdropFilter = 'blur(18px)';
    chartDom.style.webkitBackdropFilter = 'blur(18px)';
    chartDom.style.border = '1px solid rgba(255, 255, 255, 0.6)';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)';
    chartDom.style.padding = '30px';
    chartDom.style.boxSizing = 'border-box';

    const myChart = echarts.init(chartDom);
    const customPalette = ['#FCCDDF', '#C8E1F5', '#E2C9F3', '#D7EFE5', '#FCDDC8', '#E8C9CE', '#F9F1C6', '#BAC2F0'];

    try {
        let rawData = [];
        let categories = [];

        // 🚀 核心兼容逻辑：自动判断是 option 结构还是扁平 data 结构
        if (chartNode.option && chartNode.option.series && chartNode.option.xAxis) {
            rawData = chartNode.option.series[0].data;
            categories = chartNode.option.xAxis.data;
        } else if (chartNode.data) {
            // 兼容图二那样的扁平数据结构
            rawData = chartNode.data.map(item => ({
                value: item['平均CLV'] || item.value || 0
            }));
            categories = chartNode.data.map(item => item['维度'] || item.name || '未知');
        }

        if (!rawData || rawData.length === 0) {
            throw new Error("柱状图未能解析到任何有效数据");
        }

        const barWidth = 28;
        const barData = rawData.map((item, index) => {
            const val = typeof item === 'object' ? (item.value !== undefined ? item.value : 0) : item;
            const color = customPalette[index % customPalette.length];
            return {
                value: val,
                name: categories[index],
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: color + 'F0' },
                        { offset: 0.1, color: color + 'E8' },
                        { offset: 1, color: color + '70' }
                    ]),
                    borderRadius: barWidth / 2,
                    borderColor: 'rgba(255, 255, 255, 0.4)',
                    borderWidth: 1,
                    shadowColor: color + '30',
                    shadowBlur: 8,
                    shadowOffsetY: 0
                }
            };
        });

        const option = {
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                borderColor: '#E2E8F0',
                borderWidth: 1,
                padding: [10, 16],
                textStyle: { color: '#475569', fontWeight: 'bold' },
                extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px); border-radius: 12px;',
                formatter: function (params) {
                    const color = customPalette[params.dataIndex % customPalette.length];
                    return `<div style="display:flex; align-items:center; gap:8px;">
                                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:${color};"></span>
                                <span>${params.name} : ${params.value.toFixed(4)}</span>
                            </div>`;
                }
            },
            toolbox: {
                left: 'right',
                right: 20, 
                top: 10, 
                z: 9999,
                orient: 'horizontal',
                itemSize: 16,
                itemGap: 12,
                feature: {
                    saveAsImage: { title: '下载图片' },
                    myExport: {
                        show: true, title: '导出数据',
                        icon: 'path://M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
                        onclick: function() {
                            const blob = new Blob([JSON.stringify(rawData)], {type: 'application/json'});
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url; a.download = 'clv_data.json'; a.click();
                        }
                    }
                }
            },
            xAxis: {
                type: 'category',
                data: categories,
                axisLabel: {
                    show: true,
                    color: '#64748B',
                    fontWeight: 600,
                    fontSize: 13,
                    interval: 0,
                    margin: 12
                },
                axisLine: { show: false },
                axisTick: { show: false }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    show: true,
                    color: '#64748B',
                    fontWeight: 500,
                    fontSize: 13
                },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: {
                    show: true,
                    lineStyle: {
                        type: 'dashed',
                        color: 'rgba(255, 255, 255, 0.45)',
                        width: 1
                    }
                }
            },
            grid: { top: 80, left: 60, right: 40, bottom: 60 },
            series: [{
                type: 'bar',
                data: barData,
                barWidth: barWidth,
                barGap: '30%',
                label: {
                    show: true,
                    position: 'top',
                    color: '#475569',
                    fontWeight: 600,
                    fontSize: 13,
                    distance: 8,
                    formatter: (p) => p.value.toFixed(1)
                }
            }]
        };

        myChart.setOption(option, true);
        window.addEventListener('resize', () => myChart.resize());
    } catch (err) {
        console.error("柱状图渲染失败:", err);
    }
}
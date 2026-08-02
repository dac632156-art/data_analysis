/**
 * 通用仙气雷达图组件（兼具一蓝一粉独立配色与云朵状水彩纹理）
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中提取的完整图表节点
 * @param {string} cardBgUrl - 卡片背景路径
 */
async function renderEtherealRadarChart(domId, chartNode, cardBgUrl = './背景.png') {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    try {
        // 1. 样式接管（毛玻璃卡片风格）
        chartDom.style.position = 'relative';
        chartDom.style.background = `url('${cardBgUrl}') center / cover fixed`;
        chartDom.style.borderRadius = '24px';
        chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.05), 0 0 0 1px rgba(255, 255, 255, 0.8)';
        chartDom.style.padding = '30px';
        chartDom.style.boxSizing = 'border-box';
        chartDom.style.overflow = 'hidden';
        chartDom.style.display = 'flex';
        chartDom.style.flexDirection = 'column';
        chartDom.style.gap = '15px';
        
        chartDom.style.height = '600px';
        chartDom.style.width = '750px';

        // 2. 内部注入标题与固定高度的挂载容器
        chartDom.innerHTML = `
            <div style="font-size: 18px; font-weight: 700; color: #475569; letter-spacing: 0.5px;">
                ${chartNode.title || '各簇特征差异画像'}
            </div>
            <div id="${domId}-inner" style="width: 100%; height: 480px;"></div>
        `;

        const innerDom = document.getElementById(`${domId}-inner`);
        if (!innerDom) throw new Error("内部图表挂载容器创建失败");

        const myChart = echarts.init(innerDom);
        const pastelColors = ['#F1C0E8', '#A3C4F3']; // 粉、蓝独立配色

        // ☁️ 云朵状纯水墨纹理生成函数
        function createPureWatercolorPattern(img, hexColor) {
            const canvas = document.createElement('canvas');
            canvas.width = 150; canvas.height = 150;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, Math.random()*200, Math.random()*200, 300, 300, 0, 0, 150, 150);
            
            const imageData = ctx.getImageData(0, 0, 150, 150);
            const data = imageData.data;
            const hex = hexColor.replace('#', '');
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            
            for (let i = 0; i < data.length; i += 4) {
                const darkness = (255 - data[i]) / 255; 
                let opacity = 0.40 + (darkness * 2.8); 
                if (opacity > 1.0) opacity = 1.0;
                
                data[i]   = Math.round(255 * (1 - opacity) + r * opacity);
                data[i+1] = Math.round(255 * (1 - opacity) + g * opacity);
                data[i+2] = Math.round(255 * (1 - opacity) + b * opacity);
                data[i+3] = 255; 
            }
            ctx.putImageData(imageData, 0, 0);
            return canvas;
        }

        // 异步安全加载水彩纹理底图（bg5.png 或降级 bg.png）
        let patternImg = null;
        try {
            let imgResponse = await fetch('./bg5.png').catch(() => fetch('./bg.png'));
            const blob = await imgResponse.blob();
            patternImg = new Image();
            patternImg.src = URL.createObjectURL(blob);
            await new Promise((resolve, reject) => {
                patternImg.onload = resolve;
                patternImg.onerror = reject;
            });
        } catch (e) {
            console.warn("水彩纹理加载失败，已自动降级", e);
        }

        let option = {};

        if (chartNode.option) {
            option = JSON.parse(JSON.stringify(chartNode.option));
        } else if (chartNode.data && Array.isArray(chartNode.data)) {
            const rawData = chartNode.data;
            const xField = chartNode.x || '簇'; 
            
            const firstRow = rawData[0] || {};
            const indicatorKeys = Object.keys(firstRow).filter(k => k !== xField);
            
            const indicatorMax = {};
            indicatorKeys.forEach(key => {
                let max = 0;
                rawData.forEach(row => {
                    const val = Number(row[key]) || 0;
                    if (val > max) max = val;
                });
                indicatorMax[key] = max > 0 ? max * 1.2 : 100;
            });

            const indicators = indicatorKeys.map(key => ({
                name: key,
                max: indicatorMax[key]
            }));

            // 独立拆分每个簇的 series，并赋予独立的水彩纹理与配色
            const seriesConfigs = rawData.map((row, idx) => {
                const color = pastelColors[idx % pastelColors.length];
                const values = indicatorKeys.map(key => Number(row[key]) || 0);
                
                let areaStyleConfig;
                if (patternImg) {
                    const patternCanvas = createPureWatercolorPattern(patternImg, color);
                    areaStyleConfig = { color: { image: patternCanvas, repeat: 'repeat' }, opacity: 0.85 };
                } else {
                    areaStyleConfig = { color: color, opacity: 0.45 };
                }

                return {
                    name: row[xField],
                    type: 'radar',
                    data: [values],
                    itemStyle: { color: '#ffffff', borderColor: color, borderWidth: 1.5 },
                    lineStyle: { width: 2, color: color },
                    areaStyle: areaStyleConfig,
                    symbol: 'circle',
                    symbolSize: 7
                };
            });

            seriesConfigs.sort((a, b) => (a.name || '').includes('高单价') ? -1 : 1);

            option = {
                radar: { indicator: indicators },
                legend: {
                    show: true,
                    bottom: 0,
                    icon: 'circle',
                    itemWidth: 10,
                    itemHeight: 10,
                    textStyle: { color: '#64748B', fontWeight: 600, fontSize: 12 }
                },
                series: seriesConfigs
            };
        } else {
            throw new Error("未能在节点中找到 option 或 data 数组");
        }
        
        // 工具箱配置
        option.toolbox = {
            show: true,
            left: 'right',
            right: 20, 
            top: 0,
            orient: 'horizontal',
            itemSize: 16,
            itemGap: 12,
            z: 9999,
            feature: {
                saveAsImage: { title: '下载图片' }
            }
        };

        if (option.radar) {
            option.radar.axisName = { color: '#475569', fontWeight: 'bold', fontSize: 13, padding: [3, 3] };
            option.radar.splitArea = { show: false };
            option.radar.splitLine = { lineStyle: { color: ['#F1F5F9', '#E2E8F0'], width: 1.5 } };
            option.radar.axisLine = { lineStyle: { color: '#E2E8F0', type: 'dashed' } };
        }
        
        // 如果是从 JSON 直接读的 option，也加上水彩纹理
        if (chartNode.option && option.series && Array.isArray(option.series)) {
            option.series.sort((a, b) => (a.name || '').includes('高单价') ? -1 : 1);
            option.series.forEach((s, idx) => {
                const color = pastelColors[idx % pastelColors.length];
                s.itemStyle = { color: '#ffffff', borderColor: color, borderWidth: 1.5 };
                s.lineStyle = { width: 2, color: color };
                if (patternImg) {
                    const patternCanvas = createPureWatercolorPattern(patternImg, color);
                    s.areaStyle = { color: { image: patternCanvas, repeat: 'repeat' }, opacity: 0.85 };
                } else {
                    s.areaStyle = { color: color, opacity: 0.45 };
                }
                s.symbol = 'circle';
                s.symbolSize = 7;
            });
        }

        myChart.setOption(option, true);
        window.addEventListener('resize', () => myChart.resize());

    } catch (err) {
        console.error("雷达图渲染失败:", err);
        chartDom.innerHTML = `<div style="color: red; padding: 20px; font-weight: bold; background: rgba(255,255,255,0.9); border-radius: 8px;">❌ 雷达图渲染失败: ${err.message}</div>`;
    }
}
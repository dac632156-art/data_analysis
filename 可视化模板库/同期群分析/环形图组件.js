/**
 * 内部方法：生成纯正水彩纹理 Canvas
 */
function createPureWatercolorPattern(img, hexColor, sliceIndex) {
    const canvas = document.createElement('canvas');
    const width = 850;
    const height = 650;
    canvas.width = width; 
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    const cx = width / 2;
    const cy = height / 2;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate((sliceIndex * 137) * Math.PI / 180); 
    const drawSize = 850;
    ctx.drawImage(img, -drawSize / 2, -drawSize / 2, drawSize, drawSize);
    ctx.restore();

    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;

    const hex = hexColor.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);

    for (let i = 0; i < data.length; i += 4) {
        const brightness = data[i]; 
        const darkness = (255 - brightness) / 255; 

        let opacity = 0.35 + (darkness * 2.2); 
        if (opacity > 1.0) opacity = 1.0;

        data[i]   = Math.round(255 * (1 - opacity) + r * opacity);
        data[i+1] = Math.round(255 * (1 - opacity) + g * opacity);
        data[i+2] = Math.round(255 * (1 - opacity) + b * opacity);
        data[i+3] = 255; 
    }

    ctx.putImageData(imageData, 0, 0);
    return canvas;
}

/**
 * 通用仙气水彩环形图渲染组件
 * @param {string} domId - 容器的 ID
 * @param {Array} chartData - 标准的 ECharts 饼图数据
 * @param {string} cardBgUrl - 卡片外层的高级水彩背景图 (如: './背景.png')
 * @param {string} sliceTextureUrl - 扇区内部的黑白水彩纹理底图 (如: './bg5.png')
 * @param {string} titleText - 图表标题
 */
async function renderEtherealPieChart(domId, chartData, cardBgUrl, sliceTextureUrl, titleText = '') {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    chartDom.style.backgroundImage = `url('${cardBgUrl}')`; 
    chartDom.style.backgroundSize = 'cover';
    chartDom.style.backgroundPosition = 'center';
    chartDom.style.borderRadius = '24px';
    chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.05), inset 0 0 0 1px rgba(255, 255, 255, 0.8)';
    chartDom.style.padding = '20px';
    chartDom.style.boxSizing = 'border-box';
    chartDom.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'; 
    chartDom.style.backdropFilter = 'blur(4px)';

    const myChart = echarts.init(chartDom);
    const defaultPalette = ['#C7E7FB', '#E0C5F0', '#FBC2E8', '#C4EAD1', '#FED3C2', '#F3C0C7', '#F7F1BA', '#B6BBF5'];

    try {
        myChart.showLoading({ text: '渲染水彩纹理中...', color: '#F472B6', maskColor: 'rgba(255,255,255,0.4)' });
        
        const img = new Image();
        img.crossOrigin = "Anonymous";
        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = () => reject(new Error(`扇区纹理图片加载失败: ${sliceTextureUrl}`));
            img.src = sliceTextureUrl; 
        });

        const processedData = chartData.map((item, index) => {
            const hexColor = defaultPalette[index % defaultPalette.length];
            const patternCanvas = createPureWatercolorPattern(img, hexColor, index);
            
            return {
                name: item.name,
                value: item.value,
                itemStyle: {
                    color: { image: patternCanvas, repeat: 'no-repeat' },
                    borderColor: 'rgba(255, 255, 255, 0.8)', 
                    borderWidth: 2 
                }
            };
        });

        const option = {
            backgroundColor: 'transparent',
            title: {
                text: titleText,
                left: 'center',
                top: 10,
                textStyle: { color: '#1E293B', fontSize: 16, fontWeight: 600 }
            },
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                borderColor: '#E2E8F0',
                padding: [12, 16],
                textStyle: { color: '#475569', fontWeight: 'bold' },
                extraCssText: 'box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border-radius: 12px;'
            },
            legend: {
                bottom: 0,
                icon: 'circle',
                itemWidth: 10,
                itemHeight: 10,
                textStyle: { color: '#64748B', fontSize: 11, fontWeight: 600 }
            },
            series: [
                {
                    type: 'pie',
                    // 👇 关键修改 1：缩小环形半径（从 40%-65% 改为 30%-55%），给外围标签留出巨大空间
                    radius: ['30%', '55%'],
                    // 👇 关键修改 2：把圆心严格拉回正中心，避免上下偏移造成挤压
                    center: ['50%', '50%'],
                    // 👇 关键修改 3：开启防重叠策略，ECharts 会自动错开挤在一起的文字
                    avoidLabelOverlap: true,
                    label: {
                        show: true,
                        color: '#475569',
                        fontWeight: 600,
                        fontSize: 10, // 适当调小字体
                        formatter: '{b}\n{d}%'
                    },
                    labelLine: {
                        lineStyle: { color: '#CBD5E1' },
                        smooth: 0.2,
                        length: 6,   // 缩短第一段引导线
                        length2: 10  // 缩短第二段引导线，让标签紧贴图表
                    },
                    data: processedData
                }
            ]
        };

        myChart.hideLoading();
        myChart.setOption(option, true);
        window.addEventListener('resize', () => myChart.resize());

    } catch (error) {
        console.error(error);
        myChart.hideLoading();
        alert(error.message);
    }
}
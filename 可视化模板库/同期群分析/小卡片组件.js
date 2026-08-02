/**
 * 通用单张指标小卡片渲染组件
 * @param {string} domId - 容器 ID
 * @param {Object} metricData - 单个指标的数据对象 { title, value, change, unit }
 */
async function renderMetricCard(domId, metricData) {
    const container = document.getElementById(domId);
    if (!container) return;

    const title = metricData.title || metricData.label || '核心指标';
    const val = metricData.value !== undefined ? metricData.value : '--';
    const change = metricData.change !== undefined ? metricData.change : '+0.0%';
    
    // 涨跌红绿逻辑：包含 '-' 为跌（红），否则为涨（绿）[cite: 2]
    const isPositive = !String(change).includes('-');
    const changeColor = isPositive ? '#10B981' : '#EF4444'; 
    
    // 数值与单位格式化
    let displayVal = val;
    if (!isNaN(val) && val !== '') {
        const num = Number(val);
        if (metricData.unit === 'ratio' || title.toLowerCase().includes('rate') || title.includes('留存')) {
            displayVal = (num * 100).toFixed(1) + '%';
        } else {
            displayVal = num.toLocaleString('en-US', { maximumFractionDigits: 2 });
        }
    }

    let finalChange = String(change).trim();
    if (isPositive && !finalChange.includes('+')) finalChange = '+' + finalChange;
    if (!finalChange.includes('%')) finalChange += '%';

    // 单张卡片 HTML 模板
    container.innerHTML = `
        <div class="metric-card" style="width: 100%; height: 100%; background: #FFFFFF; border-radius: 20px; padding: 24px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.02), 0 0 0 1px rgba(226, 232, 240, 0.6); display: flex; justify-content: space-between; align-items: flex-end; position: relative; box-sizing: border-box;">
            <svg class="sparkle-icon" style="position: absolute; top: 20px; right: 20px; width: 24px; height: 24px;" viewBox="0 0 24 24"><path d="M12 3 L13.5 9.5 L20 11 L13.5 12.5 L12 19 L10.5 12.5 L4 11 L10.5 9.5 Z" fill="#C7D2FE"/><path d="M19 4 L19.5 6 L21.5 6.5 L19.5 7 L19 9 L18.5 7 L16.5 6.5 L18.5 6 Z" fill="#C7D2FE"/></svg>
            <div class="metric-info" style="display: flex; flex-direction: column; gap: 4px; z-index: 2;">
                <span class="metric-title" style="font-size: 15px; color: #475569; font-weight: 600;">${title}</span>
                <span class="metric-value" style="font-size: 32px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px; margin: 4px 0;">${displayVal}</span>
                <span class="metric-change" style="font-size: 14px; font-weight: 700; color: ${changeColor};">${finalChange}</span>
            </div>
            <div class="metric-chart" style="width: 100px; height: 45px; z-index: 1;">
                <svg width="100%" height="100%" viewBox="0 0 100 40" preserveAspectRatio="none">
                    <defs><linearGradient id="grad-card" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#F472B6"/><stop offset="100%" stop-color="#818CF8"/></linearGradient></defs>
                    <path d="M0 35 Q 15 25, 30 30 T 60 20 T 90 10 T 100 5 L 100 40 L 0 40 Z" fill="url(#grad-card)" opacity="0.15"/>
                    <path d="M0 35 Q 15 25, 30 30 T 60 20 T 90 10 T 100 5" fill="none" stroke="url(#grad-card)" stroke-width="2.5" stroke-linecap="round"/>
                </svg>
            </div>
        </div>
    `;
}
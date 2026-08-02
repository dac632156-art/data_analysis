function smartMapData(rawData) {
    if (!Array.isArray(rawData) || rawData.length === 0) return [];
    const firstItem = rawData[0];
    const keys = Object.keys(firstItem);
    if ('name' in firstItem && 'value' in firstItem) return rawData;

    const nameCandidates = ['name', '分层', 'category', 'label', 'key', 'dimension', '维度', '首单月'];
    const valueCandidates = ['value', '人数', 'count', 'amount', 'score', '数值', 'val', 'Metric'];

    const nameKey = keys.find(k => nameCandidates.includes(k.toLowerCase()) || nameCandidates.includes(k)) || 
                    keys.find(k => typeof firstItem[k] === 'string'); 
    const valueKey = keys.find(k => valueCandidates.includes(k.toLowerCase()) || valueCandidates.includes(k)) || 
                     keys.find(k => typeof firstItem[k] === 'number'); 

    return rawData.map(item => ({
        name: nameKey ? item[nameKey] : '未知',
        value: valueKey ? item[valueKey] : 0,
        ...item 
    }));
}

async function fetchChartData(jsonPath, targetSlot) {
    const response = await fetch(jsonPath);
    const result = await response.json();
    
    let chartNode = null;

    if (targetSlot.startsWith('card_')) {
        if (result.packages) {
            const pkg = result.packages.find(p => p.id === 'cohort' || p.analysis_type === 'cohort');
            if (pkg) {
                let allKpis = [];
                if (Array.isArray(pkg.kpis)) allKpis.push(...pkg.kpis);
                if (Array.isArray(pkg.rendered_kpis)) allKpis.push(...pkg.rendered_kpis);
                if (pkg.summary_cards && Array.isArray(pkg.summary_cards.cards)) allKpis.push(...pkg.summary_cards.cards);
                ['business_metrics', 'derived_metrics'].forEach(key => {
                    if (pkg[key]) Object.values(pkg[key]).forEach(v => { if (v && typeof v === 'object') allKpis.push(v); });
                });

                let targetKeyword = targetSlot.replace('card_', '');
                chartNode = allKpis.find(kpi => {
                    const k = String(kpi.key || kpi.name || '').toLowerCase();
                    const l = String(kpi.label || kpi.title || '').toLowerCase();
                    return k.includes(targetKeyword) || l.includes(targetKeyword);
                }) || allKpis[0];
            }
        }
    }

    if (!chartNode) {
        function deepSearch(obj) {
            if (!obj || typeof obj !== 'object' || chartNode) return;
            if (obj.slot === targetSlot || obj.id === targetSlot) {
                chartNode = obj;
                return;
            }
            for (let key in obj) {
                if (Object.prototype.hasOwnProperty.call(obj, key)) deepSearch(obj[key]);
            }
        }
        deepSearch(result);
    }

    if (!chartNode) {
        throw new Error(`未能在 JSON 中找到对应的数据 [${targetSlot}]`);
    }

    if (targetSlot.startsWith('card_')) {
        return { chartNode, data: null, title: '' };
    }

    const rawData = chartNode.data || (chartNode.option && chartNode.option.series && chartNode.option.series[0].data);
    const titleText = chartNode.title || (chartNode.option && chartNode.option.text) || '';

    return {
        chartNode,
        data: smartMapData(rawData || []),
        title: titleText
    };
}

// 统一注册表：确保这里的函数名和各组件文件里定义的一模一样
const CHART_REGISTRY = {
    'rfm_pie': 'renderEtherealPieChart',
    'cohort_retention': 'renderEtherealRetentionMatrix',
    'clv_a_流量来源': 'renderEtherealBarChart',
    'card_arpu': 'renderMetricCard',
    'card_revenue': 'renderMetricCard',
    'card_retention': 'renderMetricCard',
    'dual_axis_profit': 'renderEtherealDualAxisChart',
    'cohort_a_流量来源': 'renderEtherealLineChart',
    'cohort_a_商品类目': 'renderEtherealLineChart',
    'cluster_radar': 'renderEtherealRadarChart',
    'rfm_table': 'renderEtherealTable', // 👈 注册表格组件
    'hbar__attr_dim_offset': 'renderEtherealDimOffsetChart', // 👈 注册维度偏移图组件
    'bubble_matrix__retention_priority': 'renderEtherealBubbleChart' // 👈 注册气泡矩阵图组件
};

const CHART_SIZES = {
    'rfm_pie': { width: '550px', height: '500px' },
    'cohort_retention': { width: '1280px', height: '680px' },
    'clv_a_流量来源': { width: '850px', height: '600px' },
    'card_arpu': { width: '380px', height: '130px' },
    'card_revenue': { width: '380px', height: '130px' },
    'card_retention': { width: '380px', height: '130px' },
    'dual_axis_profit': { width: '950px', height: '600px' },
    'cohort_a_流量来源': { width: '900px', height: '600px' },
    'cohort_a_商品类目': { width: '900px', height: '600px' },
    'cluster_radar': { width: '750px', height: '600px' },
    'rfm_table': { width: '1000px', height: 'auto' }, // 👈 设置表格默认尺寸
    'hbar__attr_dim_offset': { width: '900px', height: '720px' }, // 👈 维度偏移图默认尺寸
    'bubble_matrix__retention_priority': { width: '860px', height: '640px' } // 👈 气泡矩阵图默认尺寸
};

async function renderChartBySlot(domId, jsonPath, targetSlot, extraConfig = {}) {
    try {
        // 1. 基础布局托管
        document.body.style.margin = '0';
        document.body.style.padding = '40px';
        document.body.style.minHeight = '100vh';
        document.body.style.display = 'flex';
        document.body.style.flexDirection = 'column';
        document.body.style.alignItems = 'center';
        document.body.style.gap = '20px';
        document.body.style.boxSizing = 'border-box';

        // 🚀 2. 动态背景开关：只有在配置文件（extraConfig）中传了 bgUrl 时才应用背景
        if (extraConfig.bgUrl) {
            document.body.style.background = `url('${extraConfig.bgUrl}') center / cover fixed no-repeat`;
        } else {
            document.body.style.background = '#F8FAFC'; // 默认纯色底，不冲突
        }

        const chartDom = document.getElementById(domId);
        if (!chartDom) throw new Error(`未找到 ID 为 [${domId}] 的 DOM 容器`);

        const defaultSize = CHART_SIZES[targetSlot] || { width: '600px', height: '500px' };
        chartDom.style.width = extraConfig.width || defaultSize.width;
        chartDom.style.height = extraConfig.height || defaultSize.height;
        chartDom.style.boxSizing = 'border-box';

        const { chartNode, data, title } = await fetchChartData(jsonPath, targetSlot);

        const funcName = CHART_REGISTRY[targetSlot];
        const renderFunc = funcName ? window[funcName] : null;

        if (!renderFunc || typeof renderFunc !== 'function') {
            throw new Error(`未找到 slot [${targetSlot}] 对应的渲染函数 (${funcName})`);
        }

        // 3. 分发渲染
        if (targetSlot === 'rfm_pie') {
            await renderFunc(domId, data, extraConfig.bgUrl || './背景.png', extraConfig.textureUrl || './bg5.png', title);
        } else if (targetSlot === 'cohort_retention') {
            await renderFunc(domId, data, extraConfig.bgUrl || './背景.png', title);
        } else if (targetSlot === 'clv_a_流量来源') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png', title);
        } else if (targetSlot.startsWith('card_') || targetSlot === 'cohort_c_dual') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'cohort_a_流量来源') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'cohort_a_流量来源' || targetSlot === 'cohort_a_商品类目') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'cluster_radar') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'rfm_table') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'hbar__attr_dim_offset') {
            // 支持通过 extraConfig.filter 传入维度筛选条件
            if (extraConfig.filter) {
                chartNode._filter = extraConfig.filter;
            }
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }
          else if (targetSlot === 'bubble_matrix__retention_priority') {
            await renderFunc(domId, chartNode, extraConfig.bgUrl || './背景.png');
        }

    } catch (error) {
        console.error("渲染失败:", error);
        document.getElementById(domId).innerHTML = `<div style="color: red; padding: 20px; font-weight: bold; background: rgba(255,255,255,0.8); border-radius: 8px;">❌ 对接失败: ${error.message}</div>`;
    }
}
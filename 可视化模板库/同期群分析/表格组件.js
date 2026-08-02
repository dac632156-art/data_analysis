/**
 * 通用仙气毛玻璃表格组件（终极自愈版：彻底无视 utils.js 传参错误）
 * @param {string} domId - 容器 ID
 * @param {Object} chartNode - 从 JSON 中提取的图表节点
 * @param {string} cardBgUrl - 卡片背景路径
 */
async function renderEtherealTable(domId, chartNode, cardBgUrl = './背景.png') {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    try {
        let effectiveNode = chartNode;

        // 🚀 终极自愈引擎：如果传进来的参数缺失 columns（比如被 utils.js 误传成了纯 data 数组）
        // 组件直接抛弃外部传参，自主拦截并抓取 mock7.json
        if (!effectiveNode || !effectiveNode.columns || !effectiveNode.rows) {
            console.warn("⚠️ 接收到的参数不完整，表格组件启动自主探测 mock7.json...");
            try {
                const response = await fetch('./mock7.json');
                const fullJson = await response.json();
                
                // 深度追踪正确的 rfm_table 节点
                function deepFindTable(obj) {
                    if (!obj || typeof obj !== 'object') return null;
                    if (obj.slot === 'rfm_table') return obj;
                    for (let key in obj) {
                        const found = deepFindTable(obj[key]);
                        if (found) return found;
                    }
                    return null;
                }
                
                const foundNode = deepFindTable(fullJson);
                if (foundNode) {
                    effectiveNode = foundNode;
                }
            } catch (e) {
                console.error("自主抓取失败:", e);
            }
        }

        // 1. 样式接管（毛玻璃卡片风格）
        chartDom.style.position = 'relative';
        chartDom.style.background = `url('${cardBgUrl}') center / cover fixed`;
        chartDom.style.borderRadius = '24px';
        chartDom.style.boxShadow = '0 20px 40px -10px rgba(99, 102, 241, 0.05), 0 0 0 1px rgba(255, 255, 255, 0.8)';
        chartDom.style.padding = '40px';
        chartDom.style.boxSizing = 'border-box';
        chartDom.style.overflow = 'hidden';
        chartDom.style.display = 'flex';
        chartDom.style.flexDirection = 'column';
        chartDom.style.gap = '30px';
        chartDom.style.width = '1000px';

        const titleText = effectiveNode.title || '数据汇总表';
        const columns = effectiveNode.columns || [];
        const rawRows = effectiveNode.rows || [];

        // 防御性校验：如果还是找不到列，直接抛错
        if (columns.length === 0) {
            throw new Error("无法获取 columns (列头) 数据，请检查 mock7.json 是否包含该字段");
        }

        // 8色高级粉彩胶囊调色板
        const colorPalette = {
            "高价值核心客户": { bg: "#C8E1F5", text: "#1E3A8A" }, 
            "潜力高价值客户": { bg: "#D7EFE5", text: "#064E3B" }, 
            "沉睡高价值客户": { bg: "#E2C9F3", text: "#4C1D95" }, 
            "流失预警高价值客户": { bg: "#FCCDDF", text: "#831843" }, 
            "稳定普通客户": { bg: "#FCDDC8", text: "#7C2D12" }, 
            "潜力普通客户": { bg: "#F9F1C6", text: "#713F12" }, 
            "沉睡普通客户": { bg: "#BAC2F0", text: "#312E81" }, 
            "流失预警普通客户": { bg: "#E8C9CE", text: "#881337" },
            
            // 兼容旧名称
            "重要价值": { bg: "#C8E1F5", text: "#1E3A8A" }, 
            "重要保持": { bg: "#E2C9F3", text: "#4C1D95" }, 
            "重要发展": { bg: "#FCCDDF", text: "#831843" }, 
            "重要挽留": { bg: "#D7EFE5", text: "#064E3B" }, 
            "一般价值": { bg: "#FCDDC8", text: "#7C2D12" }, 
            "一般保持": { bg: "#F9F1C6", text: "#713F12" }, 
            "一般发展": { bg: "#BAC2F0", text: "#312E81" }, 
            "一般挽留": { bg: "#E8C9CE", text: "#881337" }  
        };
        const defaultBadge = { bg: "#E2C9F3", text: "#4C1D95" };

        const theadHtml = columns.map((col, index) => {
            const alignClass = index === 0 ? 'class="segment-header"' : '';
            return `<th ${alignClass}>${col}</th>`;
        }).join('');

        // 2. 内部注入 HTML
        chartDom.innerHTML = `
            <style>
                .ethereal-table-wrap { width: 100%; border-collapse: collapse; text-align: center; }
                .ethereal-table-wrap th {
                    padding: 0 15px 20px 15px;
                    font-weight: 600; color: #1E293B; font-size: 15px;
                    border-bottom: 2px solid rgba(0, 0, 0, 0.08);
                }
                .ethereal-table-wrap th.segment-header { text-align: left; }
                .ethereal-table-wrap td {
                    padding: 20px 15px; color: #475569; font-size: 14px; font-weight: 600;
                    border-bottom: 1px dashed rgba(0, 0, 0, 0.06);
                }
                .ethereal-table-wrap td.segment-col { text-align: left; }
                .ethereal-table-wrap tr:last-child td { border-bottom: none; }
                .ethereal-table-wrap td:not(:first-child):not(:last-child), 
                .ethereal-table-wrap th:not(:first-child):not(:last-child) {
                    border-right: 1px dashed rgba(0, 0, 0, 0.04);
                }
                .badge-pill {
                    display: inline-block; padding: 6px 16px; border-radius: 20px;
                    font-size: 13px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.02);
                }
            </style>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 24px; font-weight: 600; color: #1E293B; letter-spacing: 0.5px;">
                    ${titleText}
                </div>
            </div>
            <table class="ethereal-table-wrap">
                <thead><tr>${theadHtml}</tr></thead>
                <tbody id="${domId}-tbody"></tbody>
            </table>
        `;

        const tbody = document.getElementById(`${domId}-tbody`);

        // 3. 稳健的数据遍历映射
        rawRows.forEach(rowObj => {
            const tr = document.createElement('tr');
            let trHtml = '';

            columns.forEach((colName, index) => {
                let rawCell = (rowObj && typeof rowObj === 'object') ? rowObj[colName] : null;

                // 拆包可能存在的 { value: ... } 结构
                let val = rawCell;
                if (rawCell && typeof rawCell === 'object' && 'value' in rawCell) {
                    val = rawCell.value;
                }

                if (index === 0) {
                    const textVal = val ?? '';
                    const colors = colorPalette[textVal] || defaultBadge;
                    trHtml += `
                        <td class="segment-col">
                            <span class="badge-pill" style="background-color: ${colors.bg}; color: ${colors.text};">
                                ${textVal}
                            </span>
                        </td>
                    `;
                } else {
                    let formatted = val ?? '';
                    if (typeof val === 'number') {
                        formatted = Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2);
                    }
                    trHtml += `<td>${formatted}</td>`;
                }
            });

            tr.innerHTML = trHtml;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("表格渲染失败:", err);
        chartDom.innerHTML = `<div style="color: red; padding: 20px; font-weight: bold; background: rgba(255,255,255,0.9); border-radius: 8px;">❌ 表格渲染失败: ${err.message}</div>`;
    }
}
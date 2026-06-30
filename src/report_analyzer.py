"""
报告分析引擎 ─ 五阶段分析流水线
阶段1：字段识别 → 阶段2：图表规划 → 阶段3：统计分析
阶段4-5 由 AI Agent 完成（洞察生成 + 报告撰写）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


# ============================================================
# 阶段一：字段识别
# ============================================================

# 时间字段关键词
TIME_KEYWORDS = [
    '日期', '时间', '月份', '年月', '年份', '年', '月', '季度', '周次', '周',
    'date', 'time', 'month', 'year', 'yearmonth', 'quarter', 'week',
    'day', 'hour', 'minute',
]

# 分类维度关键词
DIMENSION_KEYWORDS = [
    '地区', '省份', '省', '城市', '市', '区', '县', '区域',
    '产品类别', '产品名称', '产品', '品类', '类目',
    '渠道', '来源', '终端', '网点', '门店',
    '客户类型', '客户', '用户', '会员等级',
    '部门', '团队', '负责人', '销售',
    '品牌', '型号', '规格',
    '性别', '年龄', '学历', '职业',
    'province', 'city', 'region', 'district', 'area',
    'category', 'product', 'channel', 'source',
    'customer', 'client', 'user', 'member',
    'department', 'team', 'brand', 'model',
    'gender', 'age', 'education',
]

# 数值指标关键词
METRIC_KEYWORDS = [
    '销售额', '销量', '利润', '成本', '毛利', '毛利率',
    '订单量', '订单数', '客单价', '转化率', '复购率',
    '访问量', '用户数', '注册量', '活跃用户', '留存率',
    '库存量', '库存', '周转率',
    '成交金额', '交易额', '退款金额', '退货率',
    '人数', '金额', '数量', '占比', '比例', '率',
    'sales', 'revenue', 'profit', 'cost', 'margin',
    'orders', 'quantity', 'amount', 'count',
    'visitors', 'users', 'registrations',
    'inventory', 'stock', 'rate', 'ratio',
    'value', 'volume', 'total', 'sum',
    '平均值', '总数', '汇总', '合计',
]


def identify_fields(df: pd.DataFrame) -> Dict[str, Any]:
    """阶段1：字段识别 ─ 将列分为时间维度、数值指标、分类维度"""
    # 处理重复列名：df[重复列名] 会返回 DataFrame 而非 Series，导致 .dtype 报错
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    columns = list(df.columns)
    dtypes = {c: str(df[c].dtype) for c in columns}

    time_col = None
    metrics: List[str] = []
    dimensions: List[str] = []
    other: List[str] = []

    for col in columns:
        col_lower = col.lower().strip()
        col_stripped = col.strip()

        # 1) 检查时间字段
        if time_col is None:
            if any(kw in col_lower for kw in TIME_KEYWORDS):
                time_col = col_stripped
                continue
        # 2) 数值类型检查（兼容 pandas >= 2.0 的 StringDtype）
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        if is_numeric:
            if any(kw in col_lower for kw in METRIC_KEYWORDS):
                metrics.append(col_stripped)
            else:
                # 数值列但无明确指标名 ─ 看其含义
                metrics.append(col_stripped)
        # 3) 分类维度
        elif any(kw in col_lower for kw in DIMENSION_KEYWORDS):
            dimensions.append(col_stripped)
        elif pd.api.types.is_string_dtype(df[col]) or df[col].dtype == 'object':
            # 字符串类型，检查唯一值占比
            nunique = df[col].nunique()
            if nunique < max(20, len(df) * 0.3):
                dimensions.append(col_stripped)
            else:
                other.append(col_stripped)
        else:
            other.append(col_stripped)

    result: Dict[str, Any] = {
        "time_dimension": time_col,
        "metrics": metrics,
        "dimensions": dimensions,
        "other": other,
        "dtypes": dtypes,
    }
    return result


# ============================================================
# 阶段二：图表规划
# ============================================================

# ---- 图表和表格推荐规则（8 条核心规则） ----
# 规则 1: 趋势/走势类 → 折线图（看整体走向）
# 规则 2: 同比/环比类 → 折线图 + 排序表格（图看趋势，表看具体增减%）
# 规则 3: 对比/排名类 → 柱状图 + 排序表格（图看高低，表看精确数值）
# 规则 4: 占比/比例类 → 饼图 + 汇总表格（图看比例，表看各分类具体值）
# 规则 5: 地区分布类 → 3D 地图 + 汇总表格（图看全国分布，表看各省数据）
# 规则 6: 交叉分析类 → 堆叠柱状图 + 交叉表格（图看大致，表看交叉明细）
# 规则 7: 相关性类 → 散点图 + 相关系数表格
# 规则 8: 分布类 → 直方图（纯图即可）

GEO_KEYWORDS = ["省", "市", "区", "县", "地区", "区域", "省份", "城市", "province", "city", "region"]


def _is_geo_dimension(dim: str) -> bool:
    """判断维度是否为地区/地理类"""
    return any(kw in dim.lower() for kw in GEO_KEYWORDS)


def plan_charts(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """阶段2：图表规划 ─ 两阶段生成：先保底（报告固定章节必须有的图），再自由发挥"""
    time_col = fields["time_dimension"]
    metrics = fields["metrics"]
    dimensions = fields["dimensions"]

    # ================================================================
    # 阶段 A：保底图表 ─ 为报告固定章节（trend/TOP/structure）生成图
    # 这三个章节不论数据怎么变都必须有图，顺序固定：0=趋势, 1=结构, 2=TOP
    # ================================================================
    core_charts: List[Dict[str, Any]] = []
    # 用 dict 防止保底图与后续自由图重复
    core_titles: set = set()

    # A1: trend section → 折线图（数据必须有时间列+数值指标才生成）
    if time_col and metrics:
        core_charts.append({
            "type": "line",
            "title": f"{metrics[0]}趋势分析",
            "x": time_col,
            "y": metrics[0],
            "table_type": None,
            "analysis_type": "trend",
            "dimension": time_col,
            "metric": metrics[0],
            "reason": "报告固定章节·趋势分析 → 折线图",
            "section": "trend",
        })
        core_titles.add(f"{metrics[0]}趋势分析")

    # A2: structure section → 饼图/3D地图
    if dimensions and metrics:
        d = dimensions[0]
        m = metrics[0]
        if _is_geo_dimension(d):
            core_charts.append({
                "type": "map_3d",
                "title": f"全国{d}{m}分布",
                "x": d,
                "y": m,
                "table_type": "summary",
                "analysis_type": "geography",
                "dimension": d,
                "metric": m,
                "reason": "报告固定章节·结构分析 → 3D地图",
                "section": "structure",
            })
            core_titles.add(f"全国{d}{m}分布")
        else:
            core_charts.append({
                "type": "pie",
                "title": f"各{d}{m}占比分布",
                "x": d,
                "y": m,
                "table_type": "summary",
                "analysis_type": "composition",
                "dimension": d,
                "metric": m,
                "reason": "报告固定章节·结构分析 → 饼图",
                "section": "structure",
            })
            core_titles.add(f"各{d}{m}占比分布")

    # A3: top section → 柱状图
    if dimensions and metrics:
        d = dimensions[0]
        m = metrics[0] if len(metrics) == 1 else metrics[1] if len(metrics) >= 2 else metrics[0]
        title = f"各{d}{m}排名"
        if title not in core_titles:
            core_charts.append({
                "type": "bar",
                "title": title,
                "x": d,
                "y": m,
                "table_type": "sort",
                "analysis_type": "ranking",
                "dimension": d,
                "metric": m,
                "reason": "报告固定章节·TOP分析 → 柱状图",
                "section": "top",
            })
            core_titles.add(title)

    # ================================================================
    # 阶段 B：自由图表 ─ 根据数据特点，按 8 条规则自由发挥
    # ================================================================
    free_charts: List[Dict[str, Any]] = []

    # ---- 规则 1: 趋势/走势类 → 折线图（补充更多指标）----
    if time_col and metrics and len(metrics) >= 2:
        for m in metrics[1:3]:
            title = f"{m}趋势分析"
            if title not in core_titles:
                free_charts.append({
                    "type": "line",
                    "title": title,
                    "x": time_col,
                    "y": m,
                    "table_type": None,
                    "analysis_type": "trend",
                    "dimension": time_col,
                    "metric": m,
                    "reason": "规则1·趋势/走势类 → 折线图",
                })
                core_titles.add(title)

    # ---- 规则 3: 对比/排名类 → 柱状图 + 排序表格 ----
    if dimensions and metrics:
        for d in dimensions[:2]:
            for m in metrics[:2]:
                title = f"各{d}{m}排名"
                if title not in core_titles and not _is_geo_dimension(d):
                    free_charts.append({
                        "type": "bar",
                        "title": title,
                        "x": d,
                        "y": m,
                        "table_type": "sort",
                        "analysis_type": "ranking",
                        "dimension": d,
                        "metric": m,
                        "reason": "规则3·对比/排名类 → 柱状图 + 排序表格",
                    })
                    core_titles.add(title)

    # ---- 规则 4: 占比/比例类 → 饼图 + 汇总表格 ----
    if dimensions and metrics:
        for d in dimensions[:2]:
            if not _is_geo_dimension(d):
                for m in metrics[:2]:
                    title = f"各{d}{m}占比分布"
                    if title not in core_titles:
                        free_charts.append({
                            "type": "pie",
                            "title": title,
                            "x": d,
                            "y": m,
                            "table_type": "summary",
                            "analysis_type": "composition",
                            "dimension": d,
                            "metric": m,
                            "reason": "规则4·占比/比例类 → 饼图 + 汇总表格",
                        })
                        core_titles.add(title)

    # ---- 规则 5: 地区分布类 → 3D 地图 + 汇总表格 ----
    if dimensions and metrics:
        for d in dimensions[:2]:
            if _is_geo_dimension(d):
                for m in metrics[:2]:
                    title = f"全国{d}{m}分布"
                    if title not in core_titles:
                        free_charts.append({
                            "type": "map_3d",
                            "title": title,
                            "x": d,
                            "y": m,
                            "table_type": "summary",
                            "analysis_type": "geography",
                            "dimension": d,
                            "metric": m,
                            "reason": "规则5·地区分布类 → 3D 地图 + 汇总表格",
                        })
                        core_titles.add(title)

    # ---- 规则 6: 交叉分析类 → 堆叠柱状图 + 交叉表格 ----
    if len(dimensions) >= 2 and metrics:
        d1, d2 = dimensions[0], dimensions[1]
        if not _is_geo_dimension(d1) and not _is_geo_dimension(d2):
            title = f"{d1}×{d2} {metrics[0]}交叉分析"
            if title not in core_titles:
                free_charts.append({
                    "type": "stacked_bar",
                    "title": title,
                    "x": d1,
                    "y": metrics[0],
                    "color": d2,
                    "table_type": "cross",
                    "analysis_type": "comparison",
                    "dimension": f"{d1}×{d2}",
                    "metric": metrics[0],
                    "reason": "规则6·交叉分析类 → 堆叠柱状图 + 交叉表格",
                })
                core_titles.add(title)

    # ---- 规则 7: 相关性类 → 散点图 + 相关系数表格 ----
    if len(metrics) >= 2:
        for i in range(min(len(metrics), 3)):
            for j in range(i + 1, min(len(metrics), 4)):
                title = f"{metrics[i]} vs {metrics[j]} 相关性分析"
                if title not in core_titles:
                    free_charts.append({
                        "type": "scatter",
                        "title": title,
                        "x": metrics[i],
                        "y": metrics[j],
                        "table_type": "correlation",
                        "analysis_type": "correlation",
                        "dimension": metrics[i],
                        "metric": metrics[j],
                        "reason": "规则7·相关性类 → 散点图 + 相关系数表格",
                    })
                    core_titles.add(title)

    # ---- 规则 8: 分布类 → 直方图 ----
    for m in metrics[:3]:
        title = f"{m}分布分析"
        if title not in core_titles:
            free_charts.append({
                "type": "histogram",
                "title": title,
                "x": m,
                "table_type": None,
                "analysis_type": "distribution",
                "dimension": m,
                "metric": m,
                "reason": "规则8·分布类 → 直方图",
            })
            core_titles.add(title)

    # ---- 规则 2: 同比/环比类 → 表格追加 ----
    if time_col and metrics:
        for m in metrics[:3]:
            title = f"{m}同环比分析表"
            if title not in core_titles:
                free_charts.append({
                    "type": "table",
                    "title": title,
                    "x": time_col,
                    "y": m,
                    "table_type": "sort",
                    "analysis_type": "trend",
                    "dimension": time_col,
                    "metric": m,
                    "reason": "规则2·同比/环比类 → 排序表格（图看趋势，表看具体增减%）",
                })
                core_titles.add(title)

    # ---- TopN 补充：横向条形图 + 排序表格 ----
    if dimensions and metrics:
        for d in dimensions[:2]:
            if not _is_geo_dimension(d):
                for m in metrics[:2]:
                    title = f"{d} Top10 - {m}"
                    if title not in core_titles:
                        free_charts.append({
                            "type": "horizontal_bar",
                            "title": title,
                            "x": d,
                            "y": m,
                            "table_type": "sort",
                            "top": 10,
                            "analysis_type": "ranking",
                            "dimension": d,
                            "metric": m,
                            "reason": "规则3扩展·横向条形图 + 排序表格",
                        })
                        core_titles.add(title)

    # ---- 合并 + 去重 + 截断 ----
    # 图表类型优先级（数字越小越优先保留）
    _CHART_PRIORITY: Dict[str, int] = {
        "horizontal_bar": 1, "bar": 2, "pie": 3, "treemap": 4,
        "radar": 5, "sunburst": 6, "scatter": 7, "histogram": 8,
        "line": 9, "area": 10, "stacked_bar": 11, "map_3d": 12,
        "heatmap": 13, "bubble": 14, "box": 15, "waterfall": 16,
        "wordcloud": 17, "funnel": 18,
    }

    # 去重：同 (analysis_type, dimension, metric) 只保留优先级最高的
    all_charts = core_charts + free_charts
    deduped: List[Dict[str, Any]] = []
    seen_keys: Dict[str, float] = {}  # key -> priority (lower = better)

    for chart in all_charts:
        at = chart.get("analysis_type", "")
        dim = chart.get("dimension", "")
        met = chart.get("metric", "")
        key = f"{at}|{dim}|{met}"
        priority = _CHART_PRIORITY.get(chart.get("type", ""), 99)

        if key not in seen_keys or priority < seen_keys[key]:
            if key in seen_keys:
                # 替换掉之前低优先级的图表
                deduped = [c for c in deduped if f"{c.get('analysis_type','')}|{c.get('dimension','')}|{c.get('metric','')}" != key]
            seen_keys[key] = priority
            deduped.append(chart)

    return deduped[:10]


# ============================================================
# 阶段三：统计分析
# ============================================================

def _safe_num_series(df: pd.DataFrame, col: str) -> pd.Series:
    """安全地把一列转为数值"""
    return pd.to_numeric(df[col], errors='coerce').dropna()


def compute_basic_stats(df: pd.DataFrame, metrics: List[str]) -> Dict[str, Any]:
    """基础统计：总值、均值、最大值、最小值、标准差、中位数"""
    stats = {}
    for col in metrics:
        s = _safe_num_series(df, col)
        if len(s) == 0:
            continue
        stats[col] = {
            "total": round(s.sum(), 2),
            "mean": round(s.mean(), 2),
            "median": round(s.median(), 2),
            "max": round(s.max(), 2),
            "min": round(s.min(), 2),
            "std": round(s.std(), 2),
            "count": len(s),
        }
    return stats


def compute_trend_analysis(df: pd.DataFrame, time_col: Optional[str], metrics: List[str]) -> Dict[str, Any]:
    """趋势分析：增长率、下降率、波动率、连续涨跌次数"""
    trend: Dict[str, Any] = {}
    if not time_col or not metrics:
        return trend

    for col in metrics[:3]:
        s = _safe_num_series(df, col)
        if len(s) < 2:
            continue

        # 按时间排序后计算
        try:
            df_sorted = df.sort_values(time_col).copy()
            vals = pd.to_numeric(df_sorted[col], errors='coerce').dropna().values
        except Exception:
            vals = s.values

        if len(vals) < 2:
            continue

        first_val = float(vals[0])
        last_val = float(vals[-1])
        max_val = float(np.max(vals))
        min_val = float(np.min(vals))

        # 整体增长率
        if first_val != 0:
            growth_rate = round((last_val - first_val) / abs(first_val) * 100, 2)
        else:
            growth_rate = None

        # 波动率（变异系数）
        cv = round(float(np.std(vals)) / max(float(np.mean(vals)), 0.0001) * 100, 2)

        # 最大增长率/下降率
        pct_changes = []
        for i in range(1, len(vals)):
            if vals[i-1] != 0:
                pct_changes.append((vals[i] - vals[i-1]) / abs(vals[i-1]) * 100)
        max_growth = round(max(pct_changes), 2) if pct_changes else 0
        max_decline = round(min(pct_changes), 2) if pct_changes else 0

        # 连续增长/下降次数
        consecutive_up = 0
        consecutive_down = 0
        cur_up = 0
        cur_down = 0
        for i in range(1, len(vals)):
            if vals[i] > vals[i-1]:
                cur_up += 1
                cur_down = 0
            elif vals[i] < vals[i-1]:
                cur_down += 1
                cur_up = 0
            consecutive_up = max(consecutive_up, cur_up)
            consecutive_down = max(consecutive_down, cur_down)

        trend[col] = {
            "period_count": len(vals),
            "first_value": round(first_val, 2),
            "last_value": round(last_val, 2),
            "max_value": round(max_val, 2),
            "min_value": round(min_val, 2),
            "overall_growth_rate": growth_rate,
            "volatility_cv": cv,  # 变异系数
            "max_single_growth": max_growth,
            "max_single_decline": max_decline,
            "consecutive_up": consecutive_up,
            "consecutive_down": consecutive_down,
            "direction": "上升" if (growth_rate or 0) > 0 else "下降" if (growth_rate or 0) < 0 else "持平",
        }

    return trend


def compute_top_analysis(df: pd.DataFrame, dimensions: List[str], metrics: List[str]) -> Dict[str, Any]:
    """Top/Bottom 分析"""
    top_data: Dict[str, Any] = {}
    if not dimensions or not metrics:
        return top_data

    for dim in dimensions[:2]:
        for metric in metrics[:2]:
            try:
                grouped = df.groupby(dim)[metric].sum().sort_values(ascending=False)
                top_data[f"{dim}_{metric}"] = {
                    "top5": grouped.head(5).to_dict(),
                    "bottom5": grouped.tail(5).to_dict(),
                    "total_categories": len(grouped),
                    "top3_concentration": round(
                        grouped.head(3).sum() / max(grouped.sum(), 0.0001) * 100, 1
                    ) if grouped.sum() > 0 else 0,
                    "max_category": grouped.index[0] if len(grouped) > 0 else "",
                    "max_value": round(grouped.iloc[0], 2) if len(grouped) > 0 else 0,
                    "min_category": grouped.index[-1] if len(grouped) > 0 else "",
                    "min_value": round(grouped.iloc[-1], 2) if len(grouped) > 0 else 0,
                }
            except Exception:
                continue

    return top_data


def compute_anomaly_analysis(df: pd.DataFrame, metrics: List[str], dimensions: List[str]) -> List[Dict[str, Any]]:
    """异常分析：Z-score 离群点、突增突降、占比异常"""
    anomalies: List[Dict[str, Any]] = []
    if not metrics:
        return anomalies

    for col in metrics[:3]:
        s = _safe_num_series(df, col)
        if len(s) < 5:
            continue

        mean_val = s.mean()
        std_val = s.std()
        if std_val == 0:
            continue

        # Z-score 异常值
        z_scores = (s - mean_val) / std_val
        z_abs = z_scores.abs()
        outlier_mask = z_abs > 2.0
        if outlier_mask.sum() > 0:
            outlier_indices = z_abs[outlier_mask].nlargest(3)
            anomalies.append({
                "type": "离群点",
                "metric": col,
                "rule": "Z-score 绝对值 > 2.0",
                "details": {
                    f"第{idx}行": {
                        "value": round(float(s.iloc[idx]), 2),
                        "z_score": round(float(z_scores.iloc[idx]), 2)
                    }
                    for idx in outlier_indices.index
                },
            })

        # 突增突降（IQR 方法）
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr
        lower = q1 - 1.5 * iqr
        spike_mask = (s > upper) | (s < lower)
        if spike_mask.sum() > 0:
            anomalies.append({
                "type": "IQR异常",
                "metric": col,
                "rule": f"超出 [{round(lower, 2)}, {round(upper, 2)}] 范围",
                "count": int(spike_mask.sum()),
                "total": len(s),
                "anomaly_rate": round(float(spike_mask.sum()) / len(s) * 100, 2),
            })

    # 占比异常（检查各维度是否有个别类别占比过高）
    if dimensions and metrics:
        for dim in dimensions[:1]:
            for metric in metrics[:1]:
                try:
                    grouped = df.groupby(dim)[metric].sum()
                    total = grouped.sum()
                    if total > 0:
                        shares = grouped / total
                        high_share = shares[shares > 0.5]
                        if len(high_share) > 0:
                            anomalies.append({
                                "type": "占比异常",
                                "dimension": dim,
                                "metric": metric,
                                "warning": f"{high_share.index[0]} 占比 {round(float(high_share.iloc[0]) * 100, 1)}%，存在过高集中风险",
                            })
                except Exception:
                    continue

    return anomalies[:8]


def compute_structure_analysis(df: pd.DataFrame, dimensions: List[str], metrics: List[str]) -> Dict[str, Any]:
    """结构分析：各维度分布、占比、集中度"""
    structure: Dict[str, Any] = {}
    if not dimensions or not metrics:
        return structure

    for dim in dimensions[:2]:
        for metric in metrics[:2]:
            try:
                grouped = df.groupby(dim)[metric].sum().sort_values(ascending=False)
                total = grouped.sum()
                structure[f"{dim}_{metric}"] = {
                    "distribution": {
                        str(k): {
                            "value": round(float(v), 2),
                            "share": round(float(v) / max(total, 0.0001) * 100, 1),
                        }
                        for k, v in grouped.head(8).items()
                    },
                    "category_count": len(grouped),
                    "top3_share": round(float(grouped.head(3).sum()) / max(total, 0.0001) * 100, 1),
                }
            except Exception:
                continue

    return structure


def compute_yoy_mom(
    df: pd.DataFrame,
    time_col: Optional[str],
    metrics: List[str],
    saved_charts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """同环比分析 ─ 优先使用已保存的表格数据"""
    yoy_mom: Dict[str, Any] = {"has_yoy": False, "details": []}

    # 优先从已保存图表中提取同环比数据
    if saved_charts:
        for chart in saved_charts:
            td = chart.get("table_data")
            if td and chart.get("chart_type") == "table":
                rows = td.get("rows", [])
                if rows:
                    yoy_mom["has_yoy"] = True
                    yoy_mom["details"].append({
                        "title": chart.get("title", "同环比分析"),
                        "value_column": td.get("value_column", ""),
                        "current_year": td.get("current_year", ""),
                        "previous_year": td.get("previous_year"),
                        "row_count": len(rows),
                        "has_yoy": td.get("has_yoy", False),
                    })

    # 如果没有已保存的同环比数据，尝试计算
    if not yoy_mom["has_yoy"] and time_col and metrics:
        try:
            s = _safe_num_series(df, metrics[0])
            if len(s) >= 3:
                yoy_mom["computed"] = {
                    "metric": metrics[0],
                    "total": round(s.sum(), 2),
                    "mean": round(s.mean(), 2),
                    "note": "数据量不足以计算完整同环比，仅提供基础统计",
                }
        except Exception:
            pass

    return yoy_mom


def get_data_overview(df: pd.DataFrame) -> Dict[str, Any]:
    """生成数据概览"""
    total_rows = len(df)
    total_cols = len(df.columns)
    missing_total = int(df.isnull().sum().sum())
    missing_rate = round(missing_total / max(total_rows * total_cols, 1) * 100, 2)
    duplicate_count = int(df.duplicated().sum())
    memory_mb = round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)

    return {
        "total_rows": total_rows,
        "total_cols": total_cols,
        "column_names": list(df.columns),
        "missing_total": missing_total,
        "missing_rate": missing_rate,
        "duplicate_rows": duplicate_count,
        "memory_mb": memory_mb,
        "numeric_columns": len(df.select_dtypes(include=['number']).columns),
        "categorical_columns": len(df.select_dtypes(include=['object']).columns),
    }


# ============================================================
# 统一分析入口
# ============================================================

def _to_native(val: Any) -> Any:
    """递归把 numpy 类型转成 Python 原生类型，确保 JSON 可序列化"""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, dict):
        return {str(k): _to_native(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_native(v) for v in val]
    return val


def run_full_analysis(
    df: pd.DataFrame,
    saved_charts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """执行完整的三阶段分析，返回结构化结果供 AI 使用"""
    # 处理重复列名：避免后续 df[col] 返回 DataFrame 导致 .dtype / .mean() 等报错
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]

    # 阶段1：字段识别
    fields = identify_fields(df)

    # 阶段2：图表规划
    planned_charts = plan_charts(fields)

    # 阶段3：统计分析
    overview = _to_native(get_data_overview(df))
    basic_stats = _to_native(compute_basic_stats(df, fields["metrics"]))
    trend = _to_native(compute_trend_analysis(df, fields["time_dimension"], fields["metrics"]))
    top_analysis = _to_native(compute_top_analysis(df, fields["dimensions"], fields["metrics"]))
    structure = _to_native(compute_structure_analysis(df, fields["dimensions"], fields["metrics"]))
    anomalies = _to_native(compute_anomaly_analysis(df, fields["metrics"], fields["dimensions"]))
    yoy_mom = _to_native(compute_yoy_mom(df, fields["time_dimension"], fields["metrics"], saved_charts))

    return {
        "phase_1_fields": fields,
        "phase_2_charts": planned_charts,
        "phase_3_stats": {
            "overview": overview,
            "basic_stats": basic_stats,
            "trend_analysis": trend,
            "yoy_mom": yoy_mom,
            "top_analysis": top_analysis,
            "structure_analysis": structure,
            "anomaly_analysis": anomalies,
        },
    }

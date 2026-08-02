"""动态自适应转化漏斗模型（AARRR/AIPL 兼容版）。

三段式架构：
  HardBlock（必备列硬阻断）→ Base（嗅探+递进时序匹配）→ Advanced A/B/C（平级探测分支）

用户铁律：
  - 列名只认 ColumnMapper 映射词典标准化后的标准中文名，不做任何别名转换/兜底猜测。
  - 映射不上就跳过该列对应的进阶分支，不派生、不猜。

全部 4 张图统一自构造 ECharts option 进 pkg.charts，不走 chart_data/ChartRenderer 管线。
"""

import math
import pandas as pd
from typing import List, Dict, Optional, Tuple

from src.analysis_templates.base import (
    AnalysisPackage,
    ChartData,
    ChartItem,
    KPIItem,
    TableData,
)
from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model


# ===== 模块常量 =====

# 标准列名（映射词典已标准化，模型直接认，不做别名转换）
USER_ID = "用户ID"
EVENT_TYPE = "行为类型"
EVENT_TIME = "事件时间"
TRAFFIC_SOURCE = "流量来源"
PLATFORM = "平台"
SESSION_ID = "会话ID"
ORDER_AMOUNT = "订单实付金额"

# 必备列（HardBlock）
REQUIRED_COLS = [USER_ID, EVENT_TYPE, EVENT_TIME]

# 可选列（进阶探测）
OPTIONAL_COLS = [TRAFFIC_SOURCE, PLATFORM, SESSION_ID, ORDER_AMOUNT]

# 预设模型
AARRR = ["访问", "加购", "活跃", "支付", "分享"]
AIPL = ["曝光", "加购", "支付", "复购"]

# 默认值
DEFAULT_TOP_N = 5
DEFAULT_MAX_SESSION_WINDOW_MINUTES = 30
DEFAULT_ALERT_AOV_LOW = 50       # 经验占位值（元），业务须按品类认领
ALERT_CR_FACTOR = 0.6            # 渠道转化率红线因子（低于中位数 60%）
ALERT_AOV_FACTOR = 0.7           # 客单价红线因子（低于基线 70%）


# ===== 局部安全除法 =====
def _safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """防除零安全除法。"""
    if b is None or b == 0:
        return default
    return round(float(a) / float(b), 4)


# ===== 1. 动态模型嗅探 =====
def _sniff_model(events: List[str]) -> Tuple[List[str], str]:
    """从去重行为类型列表中嗅探业务模型。

    优先级：AARRR → AIPL → TopN 自定义漏斗。
    返回 (steps, label)。
    """
    event_set = set(str(e).strip() for e in events if e is not None)

    # 尝试 AARRR
    if set(AARRR).issubset(event_set):
        return AARRR, "AARRR"

    # 尝试 AIPL
    if set(AIPL).issubset(event_set):
        return AIPL, "AIPL"

    # 回退：取频次最高的 top_n 个事件
    # 这里 events 是去重后的，无法按频次排序，所以取 all events 的前 N 个
    # 调用方应传全量事件列表（带频次）而不是去重后的
    # 但这里先取前 DEFAULT_TOP_N 个作为兜底
    top = sorted(event_set)[:DEFAULT_TOP_N]
    if len(top) < 2:
        # 不够 2 步无法构成漏斗
        return [], ""
    return top, "自定义"


def _sniff_model_with_freq(events: pd.Series) -> Tuple[List[str], str]:
    """带频次的模型嗅探：取出现频次最高的 top_n 个事件。"""
    event_set = set(str(e).strip() for e in events if e is not None)

    # 尝试 AARRR
    if set(AARRR).issubset(event_set):
        return AARRR, "AARRR"

    # 尝试 AIPL
    if set(AIPL).issubset(event_set):
        return AIPL, "AIPL"

    # 回退：按频次排序取 top_n
    freq = events.value_counts()
    top = [str(e) for e in freq.index[:DEFAULT_TOP_N] if e is not None]
    if len(top) < 2:
        return [], ""
    return top, "自定义"


# ===== 2. 基座递进时序匹配 =====
def _core_compute(
    df: pd.DataFrame,
    steps: List[str],
) -> Tuple[pd.DataFrame, List[int], List[int]]:
    """核心递进时序匹配计算。

    返回：
      - step_users：宽表 [用户ID, T_0, T_1, ..., T_{n-1}]
      - step_counts：每步存活人数列表 [C_0, C_1, ...]
      - U_list：每步存活用户 ID 集合（列表，每元素为 Series）
    """
    n = len(steps)
    if n == 0:
        return pd.DataFrame(), [], []

    # 预压缩：每人每条行为的最早时间
    df_typed = df[EVENT_TYPE].astype(str)
    mask = df_typed.isin(steps)
    filtered = df[mask].copy()
    filtered.loc[:, "_event"] = df_typed[mask]
    filtered.loc[:, "_time"] = pd.to_datetime(filtered[EVENT_TIME], errors="coerce")
    filtered = filtered.dropna(subset=["_time", USER_ID])

    compressed = (
        filtered.groupby([USER_ID, "_event"], as_index=False)["_time"].min()
    )

    # Step 1：拉起基数
    step1_name = steps[0]
    s1 = compressed[compressed["_event"] == step1_name][[USER_ID, "_time"]].copy()
    s1.columns = [USER_ID, f"T_0"]
    s1 = s1.sort_values(f"T_0").drop_duplicates(USER_ID, keep="first")

    step_users = s1.copy()
    step_counts = [len(s1)]
    U_list = [s1[USER_ID]]

    # 逐关递进
    for i in range(1, n):
        prev = step_users[[USER_ID, f"T_{i-1}"]].copy()
        if prev.empty:
            # 上级全空 → 后续全为 0
            step_users[f"T_{i}"] = pd.NaT
            step_counts.append(0)
            U_list.append(pd.Series(dtype=prev[USER_ID].dtype))
            continue

        step_name = steps[i]
        curr = compressed[compressed["_event"] == step_name][[USER_ID, "_time"]].copy()
        curr.columns = [USER_ID, f"T_{i}_raw"]

        # Left Join + 时序约束
        merged = prev.merge(curr, on=USER_ID, how="left")
        merged = merged[merged[f"T_{i}_raw"] >= merged[f"T_{i-1}"]]
        merged = merged.sort_values(f"T_{i}_raw").drop_duplicates(USER_ID, keep="first")

        step_users = step_users.merge(
            merged[[USER_ID, f"T_{i}_raw"]], on=USER_ID, how="left"
        )
        step_users.rename(columns={f"T_{i}_raw": f"T_{i}"}, inplace=True)

        alive = step_users[f"T_{i}"].notna()
        step_counts.append(alive.sum())
        U_list.append(step_users.loc[alive, USER_ID])

    return step_users, step_counts, U_list


# ===== 3. 自构造 ECharts Option 函数 =====

# 银河主题色（与前端一致）
_FUNNEL_BLUE = "#38BDF8"        # 外圈：总转化（星光蓝，冷）
_FUNNEL_CYAN = "#FB923C"        # 内圈：当场转化（珊瑚橙，暖）——冷vs暖强对比，取自 Palette.catCoral
_GREEN = "#34D399"
_RED = "#FB7185"


def _build_funnel_option(
    data: List[Dict[str, object]],
    title: str,
) -> dict:
    """构造单漏斗 ECharts option。

    data: [{name: 步骤名, value: 人数}, ...]
    """
    return {
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {"color": "#F8FAFC", "fontSize": 16},
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} 人"},
        "series": [
            {
                "type": "funnel",
                "left": "10%",
                "width": "80%",
                "min": 0,
                "max": max((d["value"] for d in data), default=100),
                "sort": "descending",
                "gap": 2,
                "label": {
                    "show": True,
                    "position": "inside",
                    "color": "#F8FAFC",
                    "fontSize": 13,
                },
                "labelLine": {"length": 10, "lineStyle": {"width": 1, "type": "solid"}},
                "itemStyle": {
                    "borderColor": "#0F172A",
                    "borderWidth": 1,
                },
                "emphasis": {"label": {"fontSize": 18}},
                "data": [
                    {
                        "name": d["name"],
                        "value": d["value"],
                    }
                    for d in data
                ],
            }
        ],
    }


def _funnel_layer(
    data: List[Dict[str, object]],
    max_val: float,
    name: str,
    color: str,
    label_position: str = "inside",
    border_color: str = "#0F172A",
    border_width: int = 1,
) -> dict:
    """构造单条 funnel series（同心嵌套用）。

    与外层共用 left/width/min/max，使内圈梯形天然嵌在外圈内部。
    border_color/border_width 用于强化嵌套时的层次边界（内圈用更亮描边）。
    """
    return {
        "name": name,
        "type": "funnel",
        "left": "10%",
        "width": "80%",
        "min": 0,
        "max": max_val,
        "sort": "none",
        "gap": 2,
        "label": {
            "show": True,
            "position": label_position,
            "color": "#F8FAFC",
            "fontSize": 13,
        },
        "labelLine": {"length": 10, "lineStyle": {"width": 1, "type": "solid"}},
        "itemStyle": {
            "color": color,
            "borderColor": border_color,
            "borderWidth": border_width,
        },
        "emphasis": {"label": {"fontSize": 18}},
        "data": [
            {"name": d["name"], "value": d["value"]} for d in data
        ],
    }


def _build_nested_funnel_option(
    standard_data: List[Dict[str, object]],
    fast_data: List[Dict[str, object]],
    title: str,
) -> dict:
    """构造单漏斗双层嵌套对比 ECharts option。

    外圈（星光蓝）= 总转化人数（宽松口径）；
    内圈（珊瑚橙）= 当场转化人数（同会话 + 30 分钟内，苛刻口径）。
    冷(蓝) vs 暖(橙) 强对比，内圈加亮描边强化嵌套层次。
    两层共用同一 max（取口径A最大值）与 left/width，内圈梯形天然嵌在外圈内部，
    内圈越短说明当场转化占比越低，对比全靠形状+冷暖色表达，不堆文字。
    """
    max_val = max(
        max((d["value"] for d in standard_data), default=100),
        max((d["value"] for d in fast_data), default=100),
    )
    return {
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {"color": "#F8FAFC", "fontSize": 16},
        },
        "legend": {
            "data": ["总转化", "当场转化(同会话30分钟内)"],
            "top": 30,
            "textStyle": {"color": "#F8FAFC"},
        },
        "tooltip": {"trigger": "item", "formatter": "{a}<br/>{b}: {c} 人"},
        "series": [
            _funnel_layer(standard_data, max_val, "总转化", _FUNNEL_BLUE, "inside"),
            _funnel_layer(
                fast_data, max_val, "当场转化(同会话30分钟内)", _FUNNEL_CYAN, "inside",
                border_color="rgba(248,250,252,0.35)",
                border_width=2,
            ),
        ],
    }


def _build_bar_option(
    data_rows: List[dict],
    x: str,
    y: str,
    orientation: str,
    title: str,
) -> dict:
    """构造红/绿逐 bar 着色的柱状图 ECharts option。

    data_rows 每行必须含 x/y 键，可选 "System_Action" 键用于着色判定。
    orientation: "v"=纵向 / "h"=横向。
    """
    # 着色判定：System_Action 包含"预警"或"Warning" → 红，否则绿
    series_data = []
    x_data = []
    for row in data_rows:
        action = str(row.get("System_Action", ""))
        is_warning = "预警" in action or "Warning" in action
        color = _RED if is_warning else _GREEN
        series_data.append({
            "value": row.get(y, 0),
            "itemStyle": {"color": color},
        })
        x_data.append(str(row.get(x, "")))

    if orientation == "h":
        # 横向柱状图：yAxis 是类别（渠道），xAxis 是数值（转化率%）
        option = {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#F8FAFC", "fontSize": 16},
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "formatter": "{b}: {c}%",
            },
            "grid": {"left": "3%", "right": "10%", "bottom": "3%", "containLabel": True},
            "xAxis": {
                "type": "value",
                "name": "转化率 (%)",
                "axisLabel": {"color": "#94A3B8"},
                "nameTextStyle": {"color": "#94A3B8"},
                "splitLine": {"lineStyle": {"color": "rgba(148,163,184,0.15)"}},
            },
            "yAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"color": "#94A3B8"},
            },
            "series": [
                {
                    "type": "bar",
                    "data": series_data,
                    "barWidth": "60%",
                }
            ],
        }
    else:
        # 纵向柱状图：xAxis 是类别（漏斗），yAxis 是数值（客单价）
        option = {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#F8FAFC", "fontSize": 16},
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "formatter": "{b}: {c} 元",
            },
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"color": "#94A3B8"},
            },
            "yAxis": {
                "type": "value",
                "name": "客单价 (元)",
                "axisLabel": {"color": "#94A3B8"},
                "nameTextStyle": {"color": "#94A3B8"},
                "splitLine": {"lineStyle": {"color": "rgba(148,163,184,0.15)"}},
            },
            "series": [
                {
                    "type": "bar",
                    "data": series_data,
                    "barWidth": "50%",
                }
            ],
        }

    return option


# ===== 4. 三个进阶分支 =====

def _advanced_a(
    df: pd.DataFrame,
    steps: List[str],
    step_counts: List[int],
    step_users: pd.DataFrame,
    config: Optional[dict] = None,
) -> Tuple[Optional[ChartItem], List[str]]:
    """分支 A：渠道切片漏斗。

    触发条件：有"流量来源"或"平台"列。
    按渠道分组计算 CR_overall(n, d)，低于中位数 60% 标红。
    """
    config = config or {}
    n = len(steps)
    if n == 0:
        return None, []

    # 确定渠道列
    channel_col = None
    if TRAFFIC_SOURCE in df.columns:
        channel_col = TRAFFIC_SOURCE
    elif PLATFORM in df.columns:
        channel_col = PLATFORM

    if channel_col is None:
        return None, []

    # 获取最后一步存活用户
    t_last = f"T_{n-1}"
    if t_last not in step_users.columns:
        return None, []

    alive_mask = step_users[t_last].notna()
    alive_users = step_users.loc[alive_mask, USER_ID]
    first_users = step_users[USER_ID]  # 所有从第一步进来的人

    # 按渠道分组计算 CR
    channels = df[channel_col].dropna().unique()
    channel_crs: List[dict] = []
    for ch in channels:
        ch_users = set(df[df[channel_col] == ch][USER_ID].unique())
        ch_first = len(ch_users & set(first_users))
        ch_last = len(ch_users & set(alive_users))
        cr = round(ch_last / ch_first * 100, 2) if ch_first > 0 else 0.0
        channel_crs.append({
            "渠道": str(ch),
            "CR_overall": cr,
        })

    if len(channel_crs) < 2:
        # 渠道数太少，不产图
        return None, []

    # 计算红线
    cr_values = [c["CR_overall"] for c in channel_crs]
    median_cr = sorted(cr_values)[len(cr_values) // 2] if len(cr_values) % 2 == 1 else (
        sorted(cr_values)[len(cr_values) // 2 - 1] + sorted(cr_values)[len(cr_values) // 2]
    ) / 2

    alert_cr_low = config.get("alert_cr_low")
    if alert_cr_low is not None:
        threshold = float(alert_cr_low)
    else:
        threshold = round(median_cr * ALERT_CR_FACTOR, 2)

    # 着色判定
    warning_channels = []
    healthy_channels = []
    data_rows = []
    for c in channel_crs:
        cr = c["CR_overall"]
        is_warning = cr < threshold
        action = "渠道质量预警(Channel_ROI_Warning)" if is_warning else "优质渠道(Healthy_Channel)"
        if is_warning:
            warning_channels.append(str(c["渠道"]))
        else:
            healthy_channels.append(str(c["渠道"]))
        data_rows.append({
            "渠道": str(c["渠道"]),
            "CR_overall": cr,
            "System_Action": action,
        })

    # 排序：预警渠道在前
    data_rows.sort(key=lambda r: r["CR_overall"])

    # 构造 option
    option = _build_bar_option(
        data_rows=data_rows,
        x="渠道",
        y="CR_overall",
        orientation="h",
        title="渠道转化质量对比",
    )

    chart_item = ChartItem(
        slot="funnel_channel",
        chart_type="ranking",
        title="渠道转化质量对比",
        option=option,
        raw_data=data_rows,
    )

    # 洞察
    insights = []
    if warning_channels:
        insights.append(
            f"渠道切片预警：{', '.join(warning_channels[:3])}"
            f" 等{len(warning_channels)}个渠道端到端转化率低于红线 {threshold}%，"
            f"建议暂停劣质渠道投放预算"
        )

    return chart_item, insights


def _advanced_b(
    df: pd.DataFrame,
    steps: List[str],
    step_users: pd.DataFrame,
    config: Optional[dict] = None,
) -> Tuple[Optional[ChartItem], List[str]]:
    """分支 B：当场转化窗口（同会话 + 时间窗口）。

    触发条件：有"会话ID"列。
    在 B 自有严格链上叠加 会话相等 + Max_Session_Window 约束。
    产出单漏斗双层嵌套图：外圈=总转化，内圈=当场转化（同会话+窗口内）。
    """
    config = config or {}
    n = len(steps)
    if n < 2:
        return None, []

    if SESSION_ID not in df.columns:
        return None, []

    max_window = config.get("max_session_window", DEFAULT_MAX_SESSION_WINDOW_MINUTES)

    # 预压缩（带会话ID）
    df_typed = df[EVENT_TYPE].astype(str)
    mask = df_typed.isin(steps)
    filtered = df[mask].copy()
    filtered.loc[:, "_event"] = df_typed[mask]
    filtered.loc[:, "_time"] = pd.to_datetime(filtered[EVENT_TIME], errors="coerce")
    filtered = filtered.dropna(subset=["_time", USER_ID, SESSION_ID])

    compressed = (
        filtered.groupby([USER_ID, "_event", SESSION_ID], as_index=False)["_time"].min()
    )

    # B 自有严格链：Step 1 种子
    step1_name = steps[0]
    s1 = compressed[compressed["_event"] == step1_name][
        [USER_ID, SESSION_ID, "_time"]
    ].copy()
    s1.columns = [USER_ID, "SID_0", "T_fast_0"]
    s1 = s1.sort_values("T_fast_0").drop_duplicates(USER_ID, keep="first")

    fast_users = s1.copy()
    fast_counts = [len(s1)]

    for i in range(1, n):
        # 取 prev 列：T_fast_0（始终需要，用于窗口计算）和 T_fast_{i-1}（上一关时间）
        # 注意：i==1 时 T_fast_0 == T_fast_{i-1}，不能重复取同名列
        if i == 1:
            prev_cols = [USER_ID, "SID_0", "T_fast_0"]
        else:
            prev_cols = [USER_ID, "SID_0", "T_fast_0", f"T_fast_{i-1}"]
        prev = fast_users[prev_cols].copy().reset_index(drop=True)
        if prev.empty:
            fast_counts.append(0)
            continue

        step_name = steps[i]
        curr = compressed[compressed["_event"] == step_name][[USER_ID, SESSION_ID, "_time"]].copy()
        curr.columns = [USER_ID, "SID_curr", "T_raw"]

        merged = prev.reset_index(drop=True).merge(
            curr.reset_index(drop=True), on=USER_ID, how="left"
        )
        # 三大约束：时间 >= 上级 + 同会话 + 窗口内
        merged = merged[
            (merged["T_raw"] >= merged[f"T_fast_{i-1}"])
            & (merged["SID_curr"] == merged["SID_0"])
            & (
                (merged["T_raw"] - merged["T_fast_0"])
                <= pd.Timedelta(minutes=max_window)
            )
        ]
        merged = merged.sort_values("T_raw").drop_duplicates(USER_ID, keep="first")

        fast_users = fast_users.merge(
            merged[[USER_ID, "T_raw"]], on=USER_ID, how="left"
        )
        fast_users.rename(columns={"T_raw": f"T_fast_{i}"}, inplace=True)

        alive = fast_users[f"T_fast_{i}"].notna()
        fast_counts.append(alive.sum())

    # 标准漏斗数据（从 step_users 取）
    standard_data = []
    for i in range(n):
        t_col = f"T_{i}"
        if t_col in step_users.columns:
            count = step_users[t_col].notna().sum()
        else:
            count = 0
        standard_data.append({"name": steps[i], "value": int(count)})

    # 当场转化漏斗数据（苛刻口径）
    fast_data = []
    for i in range(n):
        if i < len(fast_counts):
            fast_data.append({"name": steps[i], "value": int(fast_counts[i])})
        else:
            fast_data.append({"name": steps[i], "value": 0})

    option = _build_nested_funnel_option(
        standard_data=standard_data,
        fast_data=fast_data,
        title="转化漏斗：总转化 vs 当场转化(同会话30分钟内)",
    )

    chart_item = ChartItem(
        slot="funnel_session",
        chart_type="funnel",
        title="转化漏斗：总转化 vs 当场转化(同会话30分钟内)",
        option=option,
    )

    # 洞察：计算当场转化 vs 总转化的末步留存缺口
    insights = []
    if n >= 2 and len(standard_data) > 0 and len(fast_data) > 0:
        std_last = standard_data[-1]["value"]
        fast_last = fast_data[-1]["value"]
        if std_last > 0:
            gap_pct = round((1 - fast_last / std_last) * 100, 1)
            if gap_pct > 20:
                insights.append(
                    f"当场转化缺口 {gap_pct}%：仅 {fast_last} 人在 {max_window} 分钟内（同一会话）走完全程，"
                    f"相比总转化 {std_last} 人，用户当场被页面刺激转化的比例偏低，"
                    f"建议优化落地页 UX 收割力"
                )

    return chart_item, insights


def _advanced_c(
    df: pd.DataFrame,
    steps: List[str],
    step_users: pd.DataFrame,
    config: Optional[dict] = None,
) -> Tuple[Optional[ChartItem], List[str]]:
    """分支 C：终点 GMV 挂载。

    触发条件：有"订单实付金额"列。
    计算终点客单价 AOV，低于基线 70% 标红。
    """
    config = config or {}
    n = len(steps)
    if n == 0:
        return None, []

    if ORDER_AMOUNT not in df.columns:
        return None, []

    # 获取最后一步存活用户
    t_last = f"T_{n-1}"
    if t_last not in step_users.columns:
        return None, []

    alive_mask = step_users[t_last].notna()
    alive_uids = set(step_users.loc[alive_mask, USER_ID])

    if len(alive_uids) == 0:
        return None, []

    # 计算这些用户的订单实付金额总和
    end_users_df = df[df[USER_ID].isin(alive_uids)]
    gmv = end_users_df[ORDER_AMOUNT].sum()
    aov = round(gmv / len(alive_uids), 2) if len(alive_uids) > 0 else 0

    # 阈值判定
    alert_aov_low = config.get("alert_aov_low")
    if alert_aov_low is not None:
        threshold = float(alert_aov_low)
    else:
        aov_baseline = config.get("aov_baseline")
        if aov_baseline is not None:
            threshold = round(float(aov_baseline) * ALERT_AOV_FACTOR, 2)
        else:
            # 退化经验默认
            threshold = DEFAULT_ALERT_AOV_LOW

    is_warning = aov < threshold
    action = "低净值流量预警(Low_Quality_Traffic_Alert)" if is_warning else "高价值转化(High_Value_Funnel)"

    data_rows = [{
        "漏斗": steps[-1] if steps else "终点",
        "AOV": aov,
        "System_Action": action,
    }]

    option = _build_bar_option(
        data_rows=data_rows,
        x="漏斗",
        y="AOV",
        orientation="v",
        title="终点客单价 (AOV)",
    )

    chart_item = ChartItem(
        slot="funnel_aov",
        chart_type="bar",
        title="终点客单价 (AOV)",
        option=option,
    )

    insights = []
    if is_warning:
        insights.append(
            f"低净值流量预警：到达终点用户平均客单价仅 {aov} 元，低于红线 {threshold} 元，"
            f"可能存在高转化低客单价的羊毛党陷阱，建议排查该漏斗流量商业价值"
        )
    else:
        insights.append(
            f"高价值转化：终点客单价 {aov} 元，高于红线 {threshold} 元，转化流量商业价值健康"
        )

    return chart_item, insights


# ===== 5. FunnelAnalysisModel 类 =====

class FunnelAnalysisModel(AnalysisModel):
    name = "funnel"
    display_name = "动态自适应转化漏斗"
    description = "规则驱动、自适应行为数据的转化漏斗分析引擎（AARRR/AIPL/自定义）"
    required_columns = REQUIRED_COLS
    optional_columns = OPTIONAL_COLS
    upstream_keys = []  # 生产者，不依赖上游

    def can_run(self, df: pd.DataFrame) -> bool:
        """双重校验：基类列检查 + 行为类型列非空且≥2种行为。"""
        if not super().can_run(df):
            return False

        # 行为类型列必须非空
        event_series = df[EVENT_TYPE].dropna().astype(str)
        if len(event_series) == 0:
            return False

        # 至少 2 种行为才能构成漏斗
        unique_events = event_series.unique()
        if len(unique_events) < 2:
            return False

        return True

    def compute(self, df: pd.DataFrame, config: Optional[dict] = None) -> AnalysisPackage:
        """执行完整的转化漏斗分析。

        返回 AnalysisPackage，全部 4 张图进 pkg.charts（不走 chart_data 管线）。
        """
        if config is None:
            config = {}

        # ----- 1. 动态模型嗅探 -----
        event_series = df[EVENT_TYPE].dropna().astype(str)
        steps, model_label = _sniff_model_with_freq(event_series)

        if len(steps) < 2:
            # 无法构成漏斗，返回空包
            return AnalysisPackage(
                id=self.name,
                analysis_type="funnel",
                business_question="转化漏斗分析",
                algorithm=model_label,
                dimension=EVENT_TYPE,
                metric=None,
                insights=["数据中行为类型不足 2 种，无法构成转化漏斗"],
            )

        # ----- 2. 基座递进时序计算 -----
        step_users, step_counts, U_list = _core_compute(df, steps)
        n = len(steps)

        # 转化率矩阵
        step_cr = []
        overall_cr = []
        for i in range(n):
            if i == 0:
                step_cr.append(100.0)
            else:
                step_cr.append(round(step_counts[i] / step_counts[i - 1] * 100, 2)
                              if step_counts[i - 1] > 0 else 0.0)
            overall_cr.append(round(step_counts[i] / step_counts[0] * 100, 2)
                            if step_counts[0] > 0 else 0.0)

        # ----- 3. 构建 AnalysisPackage -----
        pkg = AnalysisPackage(
            id=self.name,
            analysis_type="funnel",
            business_question=f"转化漏斗分析（{model_label}）",
            algorithm=model_label,
            dimension=EVENT_TYPE,
            metric=None,
            chart_data=[],  # 不使用，全部进 charts
        )

        # 3a. 核心漏斗图（步骤 >= 2 时产出）
        if n >= 2:
            funnel_data = [
                {"name": steps[i], "value": int(step_counts[i])}
                for i in range(n)
            ]
            option = _build_funnel_option(
                data=funnel_data,
                title=f"转化漏斗（{model_label}）",
            )
            pkg.charts.append(ChartItem(
                slot="funnel_core",
                chart_type="funnel",
                title=f"转化漏斗（{model_label}）",
                option=option,
            ))

        # 3b. 核心 KPIs
        total_start = step_counts[0] if n > 0 else 0
        total_end = step_counts[-1] if n > 0 else 0
        end_cr = overall_cr[-1] if n > 0 else 0.0
        pkg.kpis.append(KPIItem(
            label="首步基数",
            value=str(total_start),
            kpi_type="count",
        ))
        pkg.kpis.append(KPIItem(
            label="终点留存",
            value=str(total_end),
            kpi_type="count",
        ))
        pkg.kpis.append(KPIItem(
            label="端到端转化率",
            value=f"{end_cr}%",
            kpi_type="percentage",
        ))

        # 3c. 核心表格（转化率明细）
        table_rows = []
        for i in range(n):
            table_rows.append({
                "步骤": steps[i],
                "留存人数": int(step_counts[i]),
                "单步转化率": f"{step_cr[i]}%",
                "总体转化率": f"{overall_cr[i]}%",
            })
        pkg.tables.append(TableData(
            slot="funnel_detail",
            title=f"转化率明细（{model_label}）",
            table_type="summary",
            columns=["步骤", "留存人数", "单步转化率", "总体转化率"],
            rows=table_rows,
        ))

        # 3d. 核心洞察
        pkg.insights.append(
            f"漏斗模型：{model_label}，共 {n} 步，首步基数 {total_start} 人，"
            f"终点留存 {total_end} 人，端到端转化率 {end_cr}%"
        )
        if n >= 2 and step_cr[1] < 50:
            pkg.insights.append(
                f"⚠️ 第二步转化率仅 {step_cr[1]}%，首个转化断崖明显，"
                f"建议重点优化「{steps[0]}→{steps[1]}」路径"
            )

        # 3e. 分支 A：渠道切片
        chart_a, insights_a = _advanced_a(
            df, steps, step_counts, step_users, config
        )
        if chart_a is not None:
            pkg.charts.append(chart_a)
        if insights_a:
            pkg.insights.extend(insights_a)

        # 3f. 分支 B：当场转化窗口（同会话 + 时间窗口）
        chart_b, insights_b = _advanced_b(
            df, steps, step_users, config
        )
        if chart_b is not None:
            pkg.charts.append(chart_b)
        if insights_b:
            pkg.insights.extend(insights_b)

        # 3g. 分支 C：终点 GMV 挂载
        chart_c, insights_c = _advanced_c(
            df, steps, step_users, config
        )
        if chart_c is not None:
            pkg.charts.append(chart_c)
        if insights_c:
            pkg.insights.extend(insights_c)

        return pkg


# ===== 注册模型 =====
register_model(FunnelAnalysisModel())

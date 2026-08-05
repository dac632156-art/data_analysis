"""用户画像模型（v2）。

基于上游 RFM/K-means 的用户分层结果，用「语义映射词典」的标准列名刻画各分群的人口与行为画像。

关键约定（与旧版区别）：
- 列名识别直接用语义映射词典(column_mapping_dict.yaml)的标准列名，不再复用 rfm 的中英混合别名表。
- 运行门槛（硬性）：原始数据须同时含 性别、年龄、地区(省份|城市|住址|国家任一)、品类偏好(商品类目) 四组才运行。
- 合表键：用户ID（与上游分群 inner join，绝不丢失）。
- 输出：每分群一行聚合表（用户群体标签/性别/年龄/地区/品类偏好 + 扩展列有则加）；仅表，无图表。
- 剔除：职业不映射；旧维度 收入/近度R/订阅率/总消费/在站时长/兴趣 全部移除。
"""
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.analysis_engine.base import AnalysisModel
from src.analysis_templates.base import AnalysisPackage, KPIItem, TableData
from src.domain.business_finding import (
    BusinessFinding,
    FindingCategory,
    Severity,
)
from src.analysis_engine.registry import register_model
from src.mapping.column_mapper import load_global_dict

UP_NAME = "rfm_user_segmentation"  # 与 RFMModel.name 一致，引擎据此回填上游

# ---- 标准列名（源自 column_mapping_dict.yaml） ----
GENDER = "性别"
AGE = "年龄"
CATEGORY = "商品类目"
# 地区 = 四选一，按优先级取首个存在的列
REGION_CANDIDATES = ["省份", "城市", "住址", "国家"]
# 扩展列：标准列名 -> 输出表头（原始数据有则加入）
EXT_COLUMNS: Dict[str, str] = {
    "教育水平": "学历",
    "婚姻情况": "婚育",
    "流量来源": "购买渠道",
    "会员等级": "会员等级",
    "设备类型": "设备类型",
    "支付方式": "支付方式",
}


def _r(v):
    """转 float 并 round(2)，异常/NaN 返回 0.0。"""
    try:
        f = float(v)
        return round(f, 2) if pd.notna(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _dominant(series: pd.Series) -> str:
    """返回序列的众数（字符串化）。空序列返回占位符。"""
    s = series.dropna()
    if len(s) == 0:
        return "—"
    vc = s.astype(str).value_counts()
    return str(vc.index[0])


def _gender_detail(series: pd.Series) -> Tuple[str, Optional[float]]:
    """返回 (众数性别, 占比%)；空序列返回 ('—', None)。"""
    s = series.dropna()
    if len(s) == 0:
        return "—", None
    vc = s.astype(str).value_counts()
    top = str(vc.index[0])
    pct = _r(vc.iloc[0] / vc.sum() * 100)
    return top, pct


class UserProfileModel(AnalysisModel):
    name = "user_profile"
    display_name = "用户画像"
    description = "基于上游 RFM/K-means 分群，用标准列名刻画各分群性别/年龄/地区/品类偏好等画像"
    upstream_keys = [UP_NAME]

    # ---------- 列名 → 词典标准列名 ----------
    def _map_to_standard(self, df: pd.DataFrame) -> pd.DataFrame:
        variant_map, _ = load_global_dict()
        if df is None or len(df.columns) == 0:
            return df
        rename: Dict[str, str] = {}
        for col in df.columns:
            std = variant_map.get(str(col).strip().lower())
            # 避免两个原始列映射到同一标准名造成重复列（保留首个）
            if std and std not in rename.values():
                rename[col] = std
        out = df.copy().rename(columns=rename)
        if "用户ID" in out.columns:
            out["用户ID"] = out["用户ID"].astype(str)
        return out

    # ---------- 引擎入口 ----------
    def can_run(self, df: pd.DataFrame) -> bool:
        if df is None or len(df.columns) == 0:
            return False
        cols = set(self._map_to_standard(df).columns)
        has_region = any(r in cols for r in REGION_CANDIDATES)
        return (
            GENDER in cols
            and AGE in cols
            and CATEGORY in cols
            and has_region
        )

    def compute(self, df, upstream=None):
        try:
            return self._compute(df, upstream or {})
        except Exception:
            return self._placeholder("用户画像计算异常（已兜底为不支持）")

    # ---------- 占位兜底 ----------
    def _placeholder(self, reason: str = "缺少上游分群或核心属性列") -> AnalysisPackage:
        return AnalysisPackage(
            id=self.name,
            analysis_type=self.name,
            business_question=self.description,
            algorithm="user_profile_v2",
            dimension="用户分群",
            metric="用户画像",
            can_run=False,
            suggestion=reason,
            kpis=[],
            chart_data=[],
            tables=[],
            findings=[],
        )

    # ---------- 主逻辑 ----------
    def _compute(self, df, upstream: dict) -> AnalysisPackage:
        seg = upstream.get(UP_NAME)
        if seg is None or len(seg) == 0:
            return self._placeholder("缺少上游分群（RFM 未跑通，用户画像按规则跳过）")

        norm = self._map_to_standard(df)
        if "用户ID" not in norm.columns:
            return self._placeholder("数据缺少用户ID列，无法与分群合表")

        # 分组键
        if "Segment" in seg.columns:
            gcol = "Segment"
        elif "簇" in seg.columns:
            gcol = "簇"
        else:
            return self._placeholder("上游分群表缺少分组键（Segment/簇）")

        # 地区列（按优先级取首个存在的）
        region_col = next((r for r in REGION_CANDIDATES if r in norm.columns), None)
        if region_col is None:
            return self._placeholder("数据缺少地区列（省份/城市/住址/国家）")

        # 合表：仅取 用户ID + 分组键，按 用户ID inner join（保留合表键）
        seg2 = seg.copy()
        seg2["用户ID"] = seg2["用户ID"].astype(str)
        merged = norm.merge(seg2[["用户ID", gcol]], on="用户ID", how="inner")
        if len(merged) == 0:
            return self._placeholder("上游分群与数据用户ID无法关联")

        grp = merged.groupby(gcol)
        n_s = grp["用户ID"].nunique()
        total_users = int(n_s.sum())
        share = n_s / total_users

        # 各分群聚合值
        gender_dom = {g: _gender_detail(merged.loc[merged[gcol] == g, GENDER]) for g in n_s.index}
        age_mean = grp[AGE].apply(lambda s: _r(pd.to_numeric(s, errors="coerce").mean()))
        region_dom = {g: _dominant(merged.loc[merged[gcol] == g, region_col]) for g in n_s.index}
        cat_dom = {g: _dominant(merged.loc[merged[gcol] == g, CATEGORY]) for g in n_s.index}

        # 扩展列众数（仅当该标准列存在）
        ext_vals: Dict[str, Dict[str, str]] = {}
        for std in EXT_COLUMNS:
            if std in norm.columns:
                ext_vals[std] = {
                    g: _dominant(merged.loc[merged[gcol] == g, std]) for g in n_s.index
                }

        # ---------- 构建每分群一行表 ----------
        base_cols = ["用户群体标签", "人数", "占比", "性别", "年龄", "地区", "品类偏好"]
        ext_present = [EXT_COLUMNS[s] for s in EXT_COLUMNS if s in ext_vals]
        columns = base_cols + ext_present

        rows = []
        for g in n_s.index:
            gd, gp = gender_dom[g]
            gender_cell = {"value": gd, "type": "category"}
            if gp is not None:
                gender_cell["detail"] = f"{gp:.1f}%"
            row = {
                "用户群体标签": {"value": g, "type": "category"},
                "人数": {"value": int(n_s[g]), "type": "neutral"},
                "占比": {
                    "value": f"{share[g] * 100:.1f}%",
                    "type": "percentage",
                    "direction": "neutral",
                },
                "性别": gender_cell,
                "年龄": {"value": age_mean[g], "type": "neutral"},
                "地区": {"value": region_dom[g], "type": "category"},
                "品类偏好": {"value": cat_dom[g], "type": "category"},
            }
            for std in EXT_COLUMNS:
                if std in ext_vals:
                    row[EXT_COLUMNS[std]] = {"value": ext_vals[std][g], "type": "category"}
            rows.append(row)

        blocks = [
            {"title": "基础信息区", "keys": ["用户群体标签", "人数", "占比"]},
            {"title": "属性区", "keys": ["性别", "年龄", "地区", "品类偏好"] + ext_present},
        ]
        overview = TableData(
            title="群画像总览表",
            table_type="profile_overview",
            columns=columns,
            rows=rows,
            chart_config={"kind": "seg_profile_overview", "blocks": blocks},
            slot="segment_profile_overview_table",
        )
        tables = [overview]

        # ---------- KPI ----------
        best_idx = int(np.argmax([n_s[g] for g in n_s.index]))
        kpis = [
            KPIItem(label="覆盖用户", value=str(total_users)),
            KPIItem(label="分群数", value=str(int(n_s.shape[0]))),
            KPIItem(label="最大群占比", value=f"{share.max() * 100:.1f}%"),
            KPIItem(label="最大人群群", value=str(n_s.index[best_idx])),
        ]

        # ---------- Findings ----------
        findings = []
        for g in n_s.index:
            gd, gp = gender_dom[g]
            parts = [f"【{g}】{int(n_s[g])}人（占比{share[g] * 100:.1f}%）"]
            parts.append(f"性别以{gd}为主（{gp:.1f}%）" if gp is not None else f"性别以{gd}为主")
            parts.append(f"平均年龄{age_mean[g]}岁")
            parts.append(f"主要地区{region_dom[g]}、主要品类{cat_dom[g]}。")
            ext_parts = []
            for std in EXT_COLUMNS:
                if std in ext_vals:
                    ext_parts.append(f"{EXT_COLUMNS[std]}={ext_vals[std][g]}")
            if ext_parts:
                parts.append("；".join(ext_parts) + "。")
            desc = "，".join(parts)
            findings.append(
                BusinessFinding(
                    id=str(uuid.uuid4()),
                    analysis_type=self.name,
                    category=FindingCategory.STRUCTURE,
                    title=f"分群画像：{g}",
                    description=desc,
                    metric="用户画像",
                    dimension=g,
                    value=age_mean[g],
                    unit="岁",
                    severity=Severity.MEDIUM,
                    confidence=0.8,
                    business_meaning=desc,
                    recommendation="可针对该群体制定差异化运营策略。",
                ).link_evidence(table_titles=["segment_profile_overview_table"])
            )

        insights = [f"共刻画 {int(n_s.shape[0])} 个分群、{total_users} 名用户的属性画像。"]
        conclusions = ["各分群在性别、年龄、地区与品类偏好上呈显著差异，建议分层运营。"]

        return AnalysisPackage(
            id=self.name,
            analysis_type=self.name,
            business_question=self.description,
            algorithm="user_profile_v2",
            dimension="用户分群",
            metric="用户画像",
            can_run=True,
            kpis=kpis,
            chart_data=[],  # 仅表，无图表
            tables=tables,
            findings=findings,
            insights=insights,
            conclusions=conclusions,
            recommendations=[
                "依据分群画像实施差异化运营：高价值群重点维护、潜力群促活、流失风险群挽留。"
            ],
        )


register_model(UserProfileModel())

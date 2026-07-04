"""
地理空间分析模板 —— 区域数据的地图可视化

V2：使用 TemplateMeta + TemplateRuntime，拆分 build_*() 方法
生成 ECharts 地图配置，供前端 GLMapView 组件渲染
"""

import pandas as pd
from src.analysis_templates.base import (
    AnalysisTemplate, TemplateMeta, TemplateRuntime,
    KPIItem, TableData, ChartData,
)


class GeoAnalysis(AnalysisTemplate):
    meta = TemplateMeta(
        analysis_type="geo_analysis",
        display_name="地理空间分析",
        version="2.0",
        description="分析数据在地理空间上的分布特征，生成中国地图可视化",
    )

    runtime = TemplateRuntime(
        REQUIRED_SCHEMA={
            "dimension_type": "category",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        FALLBACK="ranking_analysis",
    )

    _cache: dict = {}

    def can_run(self, df: pd.DataFrame) -> bool:
        if not self._has_category_column(df):
            return False
        if len(self._get_numeric_columns(df)) < 1:
            return False
        if len(df) < self.runtime.MIN_ROWS:
            return False
        geo_keywords = ["省份", "省", "城市", "市", "地区", "区域", "地理", "geo", "city", "province"]
        cols = df.columns.tolist()
        has_geo_col = any(any(kw in str(c).lower() for kw in geo_keywords) for c in cols)
        return has_geo_col

    def _find_geo_column(self, df: pd.DataFrame) -> str:
        province_keywords = ["省份", "省", "province"]
        city_keywords = ["城市", "市", "city"]
        region_keywords = ["地区", "区域", "地理", "geo", "region"]
        
        cols = df.columns.tolist()
        
        for c in cols:
            if any(kw in str(c).lower() for kw in province_keywords):
                return str(c)
        
        for c in cols:
            if any(kw in str(c).lower() for kw in city_keywords):
                return str(c)
        
        for c in cols:
            if any(kw in str(c).lower() for kw in region_keywords):
                return str(c)
        
        return self.classifier.get_category_columns(df)[0] if self.classifier.get_category_columns(df) else ""

    def _compute(self, df, dimension, metric):
        geo_col = self._find_geo_column(df)
        if not geo_col:
            geo_col = dimension or self.classifier.get_category_columns(df)[0]
        
        df_copy = df.copy()
        df_copy['_norm_province'] = df_copy[geo_col].astype(str).apply(self._normalize_province)
        
        grouped = df_copy.groupby('_norm_province')[metric].sum().reset_index()
        grouped.columns = [geo_col, metric]
        grouped_sorted = grouped.sort_values(metric, ascending=False)
        
        map_data = []
        for _, row in grouped_sorted.iterrows():
            province = str(row[geo_col])
            map_data.append({'name': province, 'value': float(row[metric])})
        
        self._cache["grouped"] = grouped_sorted
        self._cache["geo_col"] = geo_col
        self._cache["metric"] = metric
        self._cache["map_data"] = map_data
        self._cache["total"] = grouped[metric].sum()
        self._cache["coverage"] = len(grouped)
        return grouped_sorted

    def _normalize_province(self, province: str) -> str:
        mappings = {
            '北京': '北京市', '上海': '上海市', '天津': '天津市', '重庆': '重庆市',
            '内蒙古': '内蒙古自治区', '广西': '广西壮族自治区', '西藏': '西藏自治区',
            '宁夏': '宁夏回族自治区', '新疆': '新疆维吾尔自治区',
            '香港': '香港特别行政区', '澳门': '澳门特别行政区',
            '广东': '广东省', '浙江': '浙江省', '江苏': '江苏省',
            '山东': '山东省', '河南': '河南省', '四川': '四川省',
            '湖北': '湖北省', '湖南': '湖南省', '河北': '河北省',
            '安徽': '安徽省', '福建': '福建省', '江西': '江西省',
            '辽宁': '辽宁省', '陕西': '陕西省', '黑龙江': '黑龙江省',
            '山西': '山西省', '云南': '云南省', '贵州': '贵州省',
            '吉林': '吉林省', '甘肃': '甘肃省', '海南': '海南省',
            '台湾': '台湾省', '青海': '青海省',
            '深圳': '广东省', '广州': '广东省', '东莞': '广东省', '佛山': '广东省',
            '杭州': '浙江省', '宁波': '浙江省', '温州': '浙江省',
            '南京': '江苏省', '苏州': '江苏省', '无锡': '江苏省',
            '成都': '四川省', '武汉': '湖北省', '西安': '陕西省',
            '郑州': '河南省', '青岛': '山东省', '济南': '山东省',
            '长沙': '湖南省', '合肥': '安徽省', '福州': '福建省',
            '厦门': '福建省', '南昌': '江西省', '大连': '辽宁省',
            '沈阳': '辽宁省', '长春': '吉林省', '哈尔滨': '黑龙江省',
            '石家庄': '河北省', '太原': '山西省', '南宁': '广西壮族自治区',
            '昆明': '云南省', '贵阳': '贵州省', '兰州': '甘肃省',
            '呼和浩特': '内蒙古自治区', '乌鲁木齐': '新疆维吾尔自治区',
            '拉萨': '西藏自治区', '银川': '宁夏回族自治区',
            '海口': '海南省', '台北': '台湾省', '高雄': '台湾省',
        }
        return mappings.get(province, province)

    def build_kpis(self, df, dimension, metric, algorithm):
        metric = metric or self._get_numeric_columns(df)[0]
        self._compute(df, dimension, metric)

        grouped = self._cache["grouped"]
        if len(grouped) == 0:
            return [KPIItem(label="无数据", value="0", change="", kpi_type="sum")]

        geo_col = self._cache["geo_col"]
        top1_val = grouped.iloc[0][metric]
        top1_name = grouped.iloc[0][geo_col]
        coverage = self._cache["coverage"]

        return [
            KPIItem(label=f"TOP区域: {top1_name}", value=f"{top1_val:,.2f}", change="", kpi_type="sum"),
            KPIItem(label="覆盖区域数", value=str(coverage), change="", kpi_type="count"),
        ]

    def build_tables(self, df, dimension, metric, algorithm):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        geo_col = self._cache["geo_col"]
        metric = self._cache["metric"]

        rows = [[str(row[geo_col]), round(row[metric], 2)] for _, row in grouped.iterrows()]
        return [TableData(
            title=f"{geo_col}分布",
            table_type="summary",
            columns=[str(geo_col), metric],
            rows=rows,
        )]

    def build_charts(self, df, dimension, metric, algorithm):
        map_data = self._cache.get("map_data")
        if not map_data:
            return []
        geo_col = self._cache["geo_col"]
        metric = self._cache["metric"]

        return [ChartData(
            slot="geo", chart_type="gl_map",
            title=f"{geo_col}{metric}地理分布",
            x=geo_col, y=metric,
            data=map_data,
        )]

    def build_insights(self, df, dimension, metric, algorithm, kpis, chart_data):
        grouped = self._cache.get("grouped")
        if grouped is None:
            return []
        geo_col = self._cache["geo_col"]
        metric = self._cache["metric"]

        top1 = grouped.iloc[0]
        bottom1 = grouped.iloc[-1]
        avg_val = grouped[metric].mean()
        return [
            f"「{top1[geo_col]}」的{metric}最高，达到{top1[metric]:,.2f}",
            f"「{bottom1[geo_col]}」的{metric}最低，仅{bottom1[metric]:,.2f}",
            f"平均每个{geo_col}的{metric}为{avg_val:,.2f}",
        ]

    def build_conclusion(self, df, dimension, metric, algorithm, insights):
        return insights[:1]

    def execute(self, df, dimension, metric, algorithm=None):
        metric = metric or self._get_numeric_columns(df)[0]
        dimension = dimension or self._find_geo_column(df)
        self._cache = {}
        self._compute(df, dimension, metric)
        return super().execute(df, dimension, metric, algorithm)

import pandas as pd
import numpy as np
from src.analysis_engine.package_render import render_package
import json

# 模拟用户画像真实数据：8 个分群，columns 包含所有列，
# 但 row 缺 "近度(R)" 和 "总消费" 两列（对应条件分支未命中）
pkg = {
    "id": "user_profile",
    "analysis_type": "user_profile",
    "tables": [{
        "title": "群画像总览表",
        "table_type": "profile_overview",
        "columns": ["分群", "人数", "占比", "消费力(M)", "近度(R)", "总消费"],
        "rows": [
            {"分群": {"value": "群0", "type": "category"},
             "人数": {"value": 2034, "type": "neutral"},
             "占比": {"value": "12.5%", "type": "percentage"},
             "消费力(M)": {"value": 4500, "type": "number"}},
            {"分群": {"value": "群1", "type": "category"},
             "人数": {"value": 2100, "type": "neutral"},
             "占比": {"value": "12.9%", "type": "percentage"},
             "消费力(M)": {"value": 4700, "type": "number"},
             "近度(R)": {"value": 7, "type": "neutral"}},
            {"分群": {"value": "群2", "type": "category"},
             "人数": {"value": 1900, "type": "neutral"},
             "占比": {"value": "11.7%", "type": "percentage"}},
        ],
        "chart_config": {
            "kind": "seg_profile_overview",
            "blocks": [
                {"title": "基础信息区", "keys": ["分群", "人数", "占比"]},
                {"title": "上游画像区", "keys": ["消费力(M)", "近度(R)"]},
                {"title": "核心属性区", "keys": ["总消费"]},
                {"title": "扩展属性区", "keys": []},
            ],
        }
    }]
}

out = render_package(pkg)
print(json.dumps(out['rendered_tables'][0]['rows'], ensure_ascii=False, indent=2))
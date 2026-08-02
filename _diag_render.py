import pandas as pd
import numpy as np
from dataclasses import asdict

np.random.seed(42)

# 构造一份已经"造好"的分析包 dict（模拟 cohort 那样的成品）
pkg = {
    "id": "user_profile",
    "analysis_type": "user_profile",
    "can_run": True,
    "tables": [
        {
            "title": "群画像总览表",
            "table_type": "profile_overview",
            "columns": ["分群", "人数", "占比", "消费力(M)", "近度(R)", "总消费"],
            "rows": [
                {"分群": {"value": "群0", "type": "category"},
                 "人数": {"value": 2034, "type": "neutral"},
                 "占比": {"value": "12.5%", "type": "percentage"},
                 "消费力(M)": {"value": 4500, "type": "number"},
                 "近度(R)": {"value": 5, "type": "neutral"},
                 "总消费": {"value": 12345, "type": "number"}},
                {"分群": {"value": "群1", "type": "category"},
                 "人数": {"value": 2100, "type": "neutral"},
                 "占比": {"value": "12.9%", "type": "percentage"}},
            ],
            "chart_config": {
                "kind": "seg_profile_overview",
                "blocks": [
                    {"title": "基础信息区", "keys": ["分群", "人数", "占比"]},
                    {"title": "上游画像区", "keys": ["消费力(M)", "近度(R)"]},
                    {"title": "核心属性区", "keys": ["总消费"]},
                    {"title": "扩展属性区", "keys": []},
                ],
            },
        }
    ],
}

# 走 render_package
from src.analysis_engine.package_render import render_package
out = render_package(pkg)

import json
print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
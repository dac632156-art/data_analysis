"""Bug3 修复验证：合表前跨表协同映射（A+B）。

不依赖真实 LLM：用 unittest.mock 拦截 openai.OpenAI，
喂入固定的 JSON 返回，验证：
1. coordinate_map_component 对跨表同名「金额」区分为 销售金额/退款金额；
2. build_analysis_units 在合表前完成重命名，宽表列名干净、无 _x/_y 脏后缀；
3. 无 llm_cfg 时退化为 pandas _x/_y（旧行为不变，零回归）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from unittest.mock import patch, MagicMock

from src.mapping.column_mapper import coordinate_map_component
from src.merge.dataset_merger import build_analysis_units


def _fake_llm_response(content: str):
    """构造一个 openai.OpenAI 客户端的替身，返回指定 content。"""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def _make_tables():
    df_a = pd.DataFrame({
        "订单号": ["A1", "A2"],
        "金额": [100, 200],
        "日期": ["2024-01-01", "2024-01-02"],
    })
    df_b = pd.DataFrame({
        "订单号": ["A1", "A2"],
        "金额": [10, 20],
        "日期": ["2024-03-01", "2024-03-02"],
    })
    tables = [("did_a", df_a), ("did_b", df_b)]
    file_names = {"did_a": "销售明细表", "did_b": "退款记录表"}
    join_cols = ["订单号"]
    return tables, file_names, join_cols


def test_coordinate_disambiguates_same_column():
    tables, file_names, join_cols = _make_tables()
    # LLM 返回：表0 金额→销售金额；表1 金额→退款金额；日期/关联键保持
    fake_json = (
        '{"0": {"金额": "销售金额", "日期": "日期"},'
        ' "1": {"金额": "退款金额", "日期": "日期"}}'
    )
    with patch("openai.OpenAI", return_value=_fake_llm_response(fake_json)):
        remap = coordinate_map_component(
            tables, join_cols, file_names, {"api_key": "x"})

    assert remap["did_a"]["金额"] == "销售金额"
    assert remap["did_b"]["金额"] == "退款金额"
    # 关联键列不应被重命名
    assert "订单号" not in remap.get("did_a", {})
    assert "订单号" not in remap.get("did_b", {})


def test_build_analysis_units_renames_before_merge_no_suffix():
    tables, file_names, join_cols = _make_tables()
    fake_json = (
        '{"0": {"金额": "销售金额", "日期": "日期"},'
        ' "1": {"金额": "退款金额", "日期": "日期"}}'
    )
    with patch("openai.OpenAI", return_value=_fake_llm_response(fake_json)):
        units = build_analysis_units(tables, file_names, {"api_key": "x"})

    merged = [u for u in units if u.kind == "merged"]
    assert merged, "应当产出一个合并单元"
    cols = list(merged[0].df.columns)
    # 跨表同名「金额」已被消歧为不同标准名
    assert "销售金额" in cols
    assert "退款金额" in cols
    # 不应再出现金额_x / 金额_y 脏后缀
    assert "金额_x" not in cols
    assert "金额_y" not in cols


def test_build_analysis_units_no_llm_keeps_suffix_fallback():
    """无 llm_cfg 时退化为 pandas _x/_y（旧行为不变，零回归）。"""
    tables, file_names, _ = _make_tables()
    units = build_analysis_units(tables, file_names, None)

    merged = [u for u in units if u.kind == "merged"]
    assert merged, "应当产出一个合并单元"
    cols = list(merged[0].df.columns)
    # 旧行为：同名非键列被加脏后缀
    assert "金额_x" in cols
    assert "金额_y" in cols

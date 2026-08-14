"""
表级列名映射引擎。

流水线（严格按需求顺序）：
  STEP1  词典精确匹配：列名命中 YAML 词典变体即映射为标准字段（无歧义直接过）。
  STEP1.5 词典相似匹配（阈值 70%，仅中文列名）：精确未命中时，仅当列名含中文，
          才与词典变体做相似匹配——变体⊂列名（或列名⊂变体）视为 1.0 直接命中；
          否则 difflib.SequenceMatcher ratio ≥ 0.7 才命中。例：词典 成交金额:[金额]
          可把「金额数据」映射为「成交金额」。英文列名跳过本步，仅走 STEP1 精确匹配，
          避免短英文（如 usr_id）被误命中。
  STEP2  指纹 fp = sha256(sorted(归一化列))，忽略列序。
  STEP3  指纹精确命中 DB → 仅补充「当前仍未映射列」。
  STEP4  包含度 = |新表列 ∩ 历史列| / |新表列|，最大值 ≥ 0.8 → 仅补充未映射列。
  STEP5  相似度 = Jaccard(|交|/|并|)，最大值 > 0.7 → 仅补充未映射列。
  STEP6  多候选达阈值：取最高分；并列时比对各候选对「未映射列」的映射子集是否一致，
          一致则用、不一致交 LLM。
  STEP7  全未命中 → 仅把仍未映射列交 LLM 对齐兜底（先复用现有标准字段，否则自定义）。
  STEP8  映射完成后把「指纹→映射关系」落库 SQLite，供同结构表复用。

所有历史 mapping 应用都「只补充当前未映射列」，绝不覆盖 STEP1/1.5 已做好的词典映射。
"""
import os
import re
import json
import sqlite3
import hashlib
import difflib
import logging
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd
import yaml

_logger = logging.getLogger("column_mapper")

_MAPPING_DIR = os.path.dirname(os.path.abspath(__file__))
_DICT_PATH = os.path.join(_MAPPING_DIR, "column_mapping_dict.yaml")
_DB_PATH = os.path.join(_MAPPING_DIR, "mapping.db")

# 阈值（与需求一致）
DICT_SIM_THRESHOLD = 0.7     # 词典相似匹配阈值
INCLUDE_THRESHOLD = 0.8       # 包含度阈值
SIMILARITY_THRESHOLD = 0.7    # 指纹相似度（Jaccard）阈值

# 线程安全
_db_lock = threading.Lock()
# 词典缓存（startup 加载一次；v1 不回写字典故只读安全）
_dict_cache: Dict[str, object] = {"variant_map": None, "standard_fields": None}


# ===== 工具 =====

def _norm(s: object) -> str:
    """列名归一化：去空格 + 小写。"""
    return str(s).strip().lower()


# 中文（CJK）字符判定正则：用于决定是否启用 STEP1.5 模糊匹配度搜索
_CJK_RE = re.compile(r'[\u4e00-\u9fff]')


def _is_chinese(s: object) -> bool:
    """列名是否含中文字符。

    含中文的列名启用 STEP1.5 模糊匹配度搜索（中文变体丰富，模糊匹配价值高）；
    纯英文/数字/符号列名判定为英文，仅走 STEP1 精确匹配，避免短英文名被误命中。
    """
    return bool(_CJK_RE.search(_norm(s)))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def compute_fingerprint(columns: List[str]) -> str:
    """基于列名集合（忽略顺序）计算指纹哈希。"""
    norm = sorted(_norm(c) for c in (columns or []))
    return hashlib.sha256("|".join(norm).encode("utf-8")).hexdigest()


# ===== 词典 =====

def load_global_dict() -> Tuple[Dict[str, str], List[str]]:
    """加载 YAML 无歧义词典，返回 (variant_norm -> 标准字段, 全部标准字段清单)。

    结果缓存；同变体对应多个标准字段时后者覆盖并告警（用户已删除歧义列，正常不触发）。
    """
    if _dict_cache["variant_map"] is not None:
        return _dict_cache["variant_map"], _dict_cache["standard_fields"]

    variant_map: Dict[str, str] = {}
    standard_fields: List[str] = []
    if os.path.exists(_DICT_PATH):
        try:
            with open(_DICT_PATH, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            mappings = data.get("mappings", {}) or {}
            for std, variants in mappings.items():
                standard_fields.append(std)
                for v in (variants or []):
                    vk = _norm(v)
                    if not vk:
                        continue
                    if vk in variant_map and variant_map[vk] != std:
                        _logger.warning(
                            "映射词典冲突：变体 %r 同时指向 %r 与 %r，采用后者",
                            v, variant_map[vk], std,
                        )
                    variant_map[vk] = std
        except Exception as e:  # 解析失败降级为无词典
            _logger.warning("加载映射词典失败，降级为无词典模式：%s", e)
    else:
        _logger.warning("映射词典不存在：%s，降级为无词典模式", _DICT_PATH)

    _dict_cache["variant_map"] = variant_map
    _dict_cache["standard_fields"] = standard_fields
    return variant_map, standard_fields


# ===== 相似度 =====

def similarity_match(col: str, variant: str) -> float:
    """列名与词典变体的相似度（供 STEP1.5 阈值判定）。

    命中策略（宁漏勿误，避免误映射）：
      - 列名与变体精确相等 → 1.0（高置信）；
      - 变体⊂列名 且 去掉变体后剩余部分不含中文字符（变体占主体，仅带符号/
        英文/数字后缀，如「城市_1」）→ 1.0（高置信）；
      - 变体被更长中文词内嵌（如「退款金额」∈「退款金额备注」的剩余「备注」
        含中文）→ 低置信，返回 0.0，避免把修饰列误判为原字段；
      - 其余走 difflib.SequenceMatcher 计算相似度（低置信，交给阈值/LLM 兜底）。
    不再使用「列名⊂变体」的反向包含——否则短列名会被长变体吞掉
    （如「金额」被「退款金额」误映射）。
    """
    col_n = _norm(col)
    var_n = _norm(variant)
    if not col_n or not var_n:
        return 0.0
    if var_n == col_n:
        return 1.0
    if var_n in col_n:
        rest = col_n.replace(var_n, "", 1)
        if not _CJK_RE.search(rest):
            return 1.0
        # 变体被更长中文词内嵌：低置信，不命中该变体
        return 0.0
    return difflib.SequenceMatcher(None, col_n, var_n).ratio()


# ===== 指纹库（SQLite） =====

def _ensure_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS fingerprint_mapping (
            fingerprint_id TEXT PRIMARY KEY,
            mapping_json TEXT,
            columns_json TEXT,
            created_at TEXT
        )"""
    )
    conn.commit()
    return conn


def _query_history(exclude_fp: Optional[str] = None) -> List[Dict]:
    """返回全部历史指纹记录（排除 exclude_fp），每条 {fp, mapping, columns}。"""
    try:
        conn = _ensure_db()
        rows = conn.execute(
            "SELECT fingerprint_id, mapping_json, columns_json FROM fingerprint_mapping"
        ).fetchall()
        conn.close()
        out = []
        for fp, mj, cj in rows:
            if exclude_fp and fp == exclude_fp:
                continue
            try:
                out.append({
                    "fp": fp,
                    "mapping": json.loads(mj),
                    "columns": json.loads(cj),
                })
            except Exception:
                continue
        return out
    except Exception as e:
        _logger.warning("查询指纹库失败：%s", e)
        return []


def persist_mapping(fp: str, columns: List[str], mapping: Dict[str, str]) -> None:
    """把「指纹 → 映射关系」写入 SQLite（重复指纹覆盖）。"""
    with _db_lock:
        try:
            conn = _ensure_db()
            conn.execute(
                "INSERT OR REPLACE INTO fingerprint_mapping VALUES (?,?,?,?)",
                (
                    fp,
                    json.dumps(mapping, ensure_ascii=False),
                    json.dumps(columns, ensure_ascii=False),
                    _now(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            _logger.warning("落库指纹映射失败：%s", e)


# ===== 历史候选评分（STEP4/5/6） =====

def _score_history(columns: List[str], new_unmapped: List[str],
                   hist: List[Dict]) -> List[Dict]:
    """对每条历史记录计算 包含度 / Jaccard 相似度，并提取其能覆盖的未映射列映射。

    仅返回达到阈值（包含度 ≥ 0.8 或相似度 > 0.7）的候选。
    """
    new_set = set(columns)
    if not new_set:
        return []
    new_unmapped_set = set(new_unmapped)
    cands = []
    for rec in hist:
        hcols = set(rec.get("columns", []))
        inter = new_set & hcols
        union = new_set | hcols
        include = len(inter) / len(new_set)
        jaccard = len(inter) / len(union) if union else 0.0
        # 该候选能为哪些「当前未映射列」提供映射
        known = {c: rec["mapping"][c] for c in new_unmapped_set
                 if c in rec.get("mapping", {})}
        if include >= INCLUDE_THRESHOLD or jaccard > SIMILARITY_THRESHOLD:
            cands.append({
                "fp": rec["fp"],
                "include": include,
                "jaccard": jaccard,
                "known": known,
            })
    return cands


# ===== LLM 对齐兜底（STEP7） =====

def _extract_json(text: str) -> str:
    """兼容别名：旧调用方仍可用，内部转调鲁棒版。"""
    return _robust_extract_json(text)


def _robust_extract_json(text: str, max_preview: int = 2000) -> str:
    """从 LLM 文本中鲁棒提取 JSON 片段。

    兼容场景：
    - ```json / ``` 代码块包裹
    - 前后带解释文字（找首个 { / [ 到末个 } / ]）
    - 被截断的 JSON（尽力补闭合括号、去尾部逗号、去 // 注释）
    - 纯对象 {...} 或纯数组 [...]

    解析失败抛出 ValueError，message 含原文前 max_preview 字符便于定位。
    """
    if not text or not isinstance(text, str):
        raise ValueError("响应为空，未找到 JSON")

    raw = text.strip()

    # 1) 先尝试直接解析原文（最常见：纯 JSON 无包裹）
    try:
        json.loads(raw)
        return raw
    except (json.JSONDecodeError, ValueError):
        pass

    # 2) 去 ``` 代码块包裹（支持 ```json / ```）
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
        try:
            json.loads(raw)
            return raw
        except (json.JSONDecodeError, ValueError):
            pass

    # 3) 提取首个对象 / 数组子串
    first_obj = raw.find("{")
    last_obj = raw.rfind("}")
    first_arr = raw.find("[")
    last_arr = raw.rfind("]")

    candidates = []
    has_obj = first_obj != -1 and (last_obj > first_obj or last_obj == -1)
    if has_obj:
        # 截断场景（末尾无 }）：从首个 { 取到串尾，交给 repair 补闭合
        end = last_obj + 1 if last_obj != -1 else len(raw)
        candidates.append(raw[first_obj:end])
    has_arr = first_arr != -1 and (last_arr > first_arr or last_arr == -1)
    if has_arr:
        end = last_arr + 1 if last_arr != -1 else len(raw)
        candidates.append(raw[first_arr:end])

    last_err = None
    for cand in candidates:
        # 3a) 尝试直接解析子串
        try:
            json.loads(cand)
            return cand
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
        # 3b) 截断修复：去 // 与 # 注释、去尾部逗号、补闭合括号
        fixed = _repair_truncated_json(cand)
        try:
            json.loads(fixed)
            return fixed
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e

    preview = (text or "")[:max_preview].replace("\n", "\\n")
    raise ValueError(
        f"响应中未找到可用 JSON（末次错误：{last_err}）；响应原文前 {max_preview} 字符：{preview}"
    )


def _repair_truncated_json(s: str) -> str:
    """尽力修复被截断/带噪声的 JSON 字符串。"""
    # 去 // 与 # 行内/行尾注释（仅处理简单情形，避免误伤字符串内 #）
    cleaned_lines = []
    for line in s.split("\n"):
        # 去掉行尾注释（# 或 //），但保留字符串内的
        stripped = _strip_line_comment(line)
        cleaned_lines.append(stripped)
    body = "\n".join(cleaned_lines).strip()

    # 先补闭合括号：统计未闭合的 { 与 [
    stack = []
    in_str = False
    esc = False
    for ch in body:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    # 逆序补闭合
    close_map = {"{": "}", "[": "]"}
    for open_ch in reversed(stack):
        body += close_map[open_ch]

    # 后去尾部逗号（含串尾逗号 / }, ] 前逗号，需先剥掉字符串内可能的逗号干扰）
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    # 处理补括号后出现在最末的裸逗号（如 "...\"d\",}" 已变 "d",}" 被上条覆盖；
    # 但 "d", 结尾且无括号的情况上面补括号后已变成 "d",}，再被覆盖）
    body = body.strip()
    if body.endswith(","):
        body = body[:-1]

    return body


def _strip_line_comment(line: str) -> str:
    """去掉一行中的 // 或 # 注释，但不破坏字符串字面量内的 #。"""
    in_str = False
    esc = False
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if esc:
            out.append(ch)
            esc = False
            i += 1
            continue
        if ch == "\\":
            out.append(ch)
            esc = True
            i += 1
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            i += 1
            continue
        if not in_str:
            if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            if ch == "#":
                break
        out.append(ch)
        i += 1
    return "".join(out)


def _call_llm_json(system_prompt: str, user_prompt: str,
                  llm_cfg: Dict, max_tokens: int = 2048,
                  max_retries: int = 1) -> str:
    """调用 LLM 并返回「已解析前的原始 content 文本」（由调用方决定如何解析）。

    健壮性：
    - 失败（网络/超时/接口异常）自动重试 max_retries 次（默认 1，共 2 次）。
    - client 自身 max_retries=0，重试由本函数手动循环控制。
    - 返回的是 LLM 文本原文，便于上层在解析失败时把原文打进日志。

    仍失败则上抛最后一次异常，由调用方降级。
    """
    import openai

    api_key = llm_cfg.get("api_key")
    base_url = llm_cfg.get("base_url") or "https://api.deepseek.com"
    model = llm_cfg.get("model") or "deepseek-chat"

    client = openai.OpenAI(api_key=api_key, base_url=base_url,
                           timeout=120.0, max_retries=0)

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=max_tokens,
                timeout=120,
            )
            content = resp.choices[0].message.content
            if content is None:
                raise ValueError("LLM 返回空 content")
            return content.strip()
        except Exception as e:  # 网络/超时/接口/空内容，均重试
            last_err = e
            _logger.warning("[_call_llm_json] 第 %d 次调用失败：%s", attempt + 1, e)
    raise last_err


def llm_fallback(unmapped: List[str], sample: object,
                 llm_cfg: Dict, standard_fields: List[str],
                 file_name: Optional[str] = None) -> Dict[str, str]:
    """LLM 对齐兜底：优先复用现有标准字段，否则才自定义新标准名。

    返回 {原始列: 标准字段}。异常上抛由调用方捕获降级。
    file_name：可选，喂给 LLM 帮助推断业务语义（方案 B）。
    """
    sample_str = json.dumps(sample, ensure_ascii=False)[:1500]
    fields_str = "、".join(standard_fields) if standard_fields else "（暂无已有标准字段）"

    fname_line = (
        f"当前数据表文件名为：{file_name}，请结合表名推断业务语义。\n"
        if file_name else ""
    )
    prompt = (
        "你是一个数据列名语义映射助手。\n"
        f"{fname_line}"
        f"现有数据表有以下无法自动识别的列：{unmapped}。\n"
        f"可选样本数据（前几行）：{sample_str}\n"
        f"系统中已有的标准字段清单（请优先判断这些待映射列是否能归入其中某一类；"
        f"若语义一致请直接复用，不要新造）：\n{fields_str}\n\n"
        "要求：\n"
        "1. 对每个待映射列，先判断它是否对应已有标准字段之一（含义/语义一致即可），"
        "若是，输出该标准字段名；\n"
        "2. 仅当所有已有标准字段都不合适时，才自定义一个新的中文语义字段名"
        "（避免与已有字段同义重复，如已有「成交金额」就不要造「成交额」）；\n"
        "3. 只输出 JSON，格式：{\"原始列名\": \"标准字段名\", ...}，不要输出任何解释文字。"
    )
    content = ""
    try:
        content = _call_llm_json(
            "你是列名映射助手，只输出 JSON。",
            prompt,
            llm_cfg,
            max_tokens=2048,
            max_retries=1,
        )
        parsed = json.loads(_robust_extract_json(content))
    except Exception as e:
        # 上抛，由调用方（map_dataset_columns）捕获后降级为原列名透传
        _logger.warning("[llm_fallback] JSON 解析失败，原文前 2000 字符：%s",
                        content[:2000])
        raise
    return {str(k): str(v) for k, v in parsed.items() if str(k) in unmapped}


def coordinate_map_component(
    tables: List[Tuple[str, pd.DataFrame]],
    join_cols: List[str],
    file_names: Dict[str, str],
    llm_cfg: dict,
) -> Dict[str, Dict[str, str]]:
    """跨表协同映射（方案 A+B）：把同一待合表组的全部列一次性送 LLM 全局消歧。

    入参 tables: [(dataset_id, df), ...]（同一连通分量内的表）。
    join_cols: 该分量内的关联键列名（已归一化判定为键），不参与重命名。
    file_names: {did: 文件名}，喂给 LLM 推断业务语义（方案 B）。

    返回 {did: {原始列名: 标准名}}，仅含非关联键列的跨表消歧重命名。
    异常上抛由调用方捕获降级（退化回 pandas _x/_y）。
    """
    variant_map, standard_fields = load_global_dict()
    join_norms = {_norm(c) for c in (join_cols or [])}

    # 构造每表描述（跳过关联键列，避免 LLM 重命名它们）
    blocks = []
    for i, (did, df) in enumerate(tables):
        cols = [str(c) for c in df.columns if _norm(c) not in join_norms]
        sample_cols: Dict[str, object] = {}
        for c in cols[:8]:
            try:
                sample_cols[str(c)] = df[c].head(3).tolist()
            except Exception:
                pass
        fname = (file_names or {}).get(did, did)
        blocks.append(
            f"表{i} [文件名: {fname}]:\n"
            f"  列: {'、'.join(cols)}\n"
            f"  样本(部分): {json.dumps(sample_cols, ensure_ascii=False)[:800]}"
        )
    tables_desc = "\n".join(blocks)
    fields_str = "、".join(standard_fields) if standard_fields else "（暂无已有标准字段）"

    prompt = (
        "你是一个数据列名语义映射助手。下面有多张待合并的数据表，每张标注了序号、"
        "文件名、列名与样本。\n"
        f"{tables_desc}\n\n"
        "要求：\n"
        "1. 关联键列（用于合并的键，如订单号、编号等）不要重命名，保持原名。\n"
        "2. 同一原始列名若出现在多张表中（跨表同名）：为避免合并时列名冲突"
        "（pandas 会自动加 _x/_y 脏后缀），请一律区分为不同标准名——"
        "结合各自表名/业务含义命名（如 销售金额 / 退款金额）；"
        "即使语义确为同义但来自不同表，也请用表来源区分"
        "（如 A表金额 / B表金额），切勿保持完全相同。\n"
        "3. 仅当标准字段清单中没有合适名称时才自定义新的中文语义字段名，"
        "避免与已有字段同义重复（如已有「成交金额」就不要造「成交额」）。\n"
        "4. 只输出 JSON，格式：{\"0\": {\"原始列名\": \"标准字段名\", ...}, "
        "\"1\": {...}, ...}，键为纯数字序号（与上方“表0/表1”的序号对应，"
        "即 0、1、...），不要输出任何解释文字。\n"
        f"标准字段清单（可优先复用）：\n{fields_str}\n"
    )
    content = ""
    try:
        content = _call_llm_json(
            "你是列名映射助手，只输出 JSON。",
            prompt,
            llm_cfg,
            max_tokens=2048,
            max_retries=1,
        )
        parsed = json.loads(_robust_extract_json(content))
    except Exception as e:
        # 上抛，由调用方（dataset_merger）捕获后降级为保留原列名
        _logger.warning("[coordinate_map_component] JSON 解析失败，原文前 2000 字符：%s",
                        content[:2000])
        raise
    result: Dict[str, Dict[str, str]] = {}
    for i, (did, _df) in enumerate(tables):
        mp = parsed.get(str(i))
        if not isinstance(mp, dict):
            continue
        cleaned = {
            str(k): str(v) for k, v in mp.items()
            if _norm(str(k)) not in join_norms
        }
        if cleaned:
            result[did] = cleaned
    return result


# ===== 主入口 =====

def map_dataset_columns(session_id, dataset_id, df: pd.DataFrame,
                        llm_cfg: Optional[Dict] = None,
                        file_name: Optional[str] = None) -> pd.DataFrame:
    """对单张表运行列名映射流水线，返回重命名后的 df。

    dataset_id 仅用于日志/后续扩展，指纹计算只基于 columns，故次路径（analysis/run）
    传 None 也无影响。llm_cfg 形如 {"api_key":..., "base_url":..., "model":...}，
    缺 api_key 时 LLM 兜底降级为「原列名透传」，不阻断分析。
    """
    if df is None or len(df.columns) == 0:
        return df

    variant_map, standard_fields = load_global_dict()
    columns = list(df.columns)
    mapping: Dict[str, str] = {}

    # ---- STEP1 精确匹配 ----
    for col in columns:
        target = variant_map.get(_norm(col))
        if target:
            mapping[col] = target

    # ---- STEP1.5 相似匹配（阈值 70%，仅中文列名） ----
    for col in [c for c in columns if c not in mapping]:
        # 英文列名仅依赖 STEP1 精确匹配，跳过模糊匹配度搜索，避免短英文名被误命中
        if not _is_chinese(col):
            continue
        best_score = 0.0
        best_std: Optional[str] = None
        conflict = False
        for variant, std in variant_map.items():
            s = similarity_match(col, variant)
            if s >= DICT_SIM_THRESHOLD:
                if best_std is None or s > best_score:
                    best_score = s
                    best_std = std
                    conflict = False
                elif s == best_score and best_std != std:
                    conflict = True
        if best_std is not None and best_score >= DICT_SIM_THRESHOLD and not conflict:
            mapping[col] = best_std

    # ---- STEP2 指纹 ----
    new_unmapped = [c for c in columns if c not in mapping]
    fp = compute_fingerprint(columns)

    # ---- STEP3 指纹精确命中 ----
    applied = False
    hist = _query_history()
    exact = next((r for r in hist if r["fp"] == fp), None)
    if exact is not None:
        for col in new_unmapped:
            if col in exact["mapping"]:
                mapping[col] = exact["mapping"][col]
        applied = True

    # ---- STEP4/5/6 包含度 / 相似度 / 多候选裁决 ----
    if not applied:
        cands = _score_history(columns, new_unmapped, hist)
        if cands:
            # 排序：包含度优先，其次 Jaccard
            cands.sort(key=lambda c: (c["include"], c["jaccard"]), reverse=True)
            top = cands[0]
            tied = [c for c in cands
                    if c["include"] == top["include"] and c["jaccard"] == top["jaccard"]]
            if len(tied) == 1:
                for c, s in top["known"].items():
                    mapping[c] = s
                applied = True
            else:
                # 并列：比对各候选对未映射列的映射子集是否完全一致
                ref = tied[0]["known"]
                if all(c["known"] == ref for c in tied):
                    for c, s in ref.items():
                        mapping[c] = s
                    applied = True
                # 不一致 → 留待 STEP7 交 LLM

    # ---- STEP7 LLM 对齐兜底（仅仍未映射列） ----
    still_unmapped = [c for c in columns if c not in mapping]
    if still_unmapped:
        if llm_cfg and llm_cfg.get("api_key"):
            try:
                llm_map = llm_fallback(
                    still_unmapped,
                    df[still_unmapped].head(5).to_dict("records"),
                    llm_cfg, standard_fields,
                    file_name=file_name,
                )
                for c, s in llm_map.items():
                    if c in columns:
                        mapping[c] = s
            except Exception as e:
                # 收紧降级：不再用可能错误的「已有映射」，未映射列保留原列名透传。
                # LLM 原文已由 llm_fallback 内部 warning 打印（前 2000 字符）。
                _logger.warning(
                    "LLM 映射兜底失败，未映射列保留原列名透传（不再使用旧映射）：%s；未映射列=%s",
                    e, still_unmapped,
                )
        else:
            _logger.info("无 LLM 配置，未映射列保留原列名：%s", still_unmapped)

    # ---- STEP8 落库（指纹 → 完整映射） ----
    full_map = {c: mapping[c] for c in columns if c in mapping}
    if full_map:
        try:
            persist_mapping(fp, columns, full_map)
        except Exception as e:
            _logger.warning("落库失败（不影响本次分析）：%s", e)

    if not mapping:
        return df

    # ---- 重命名（标准名冲突加后缀去重） ----
    used: set = set()
    final_rename: Dict[str, str] = {}
    for raw, std in mapping.items():
        if std in used:
            i = 2
            cand = f"{std}_{i}"
            while cand in used:
                i += 1
                cand = f"{std}_{i}"
            final_rename[raw] = cand
            used.add(cand)
        else:
            final_rename[raw] = std
            used.add(std)

    _logger.info(
        "列名映射完成 session=%s dataset=%s 映射=%s",
        session_id, dataset_id, final_rename,
    )
    return df.rename(columns=final_rename)

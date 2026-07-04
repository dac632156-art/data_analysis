"""
Analysis Library Registry —— YAML 加载、查询、管理

核心职责：
1. 加载 analysis_library/ 目录下所有 .yaml 文件
2. 提供 lookup(analysis_goal) 查询——中文目标 → AnalysisIntent
3. 提供 get_by_intent(intent) 精确查询
4. 提供 list_intents() 列出所有已注册分析类型

查询策略：
- 遍历所有 YAML 的 keywords 列表，匹配 analysis_goal 中的关键词
- 多个命中时按 priority 降序返回最高分
- 无命中返回 None（由 Planner 处理 fallback）
"""

import os
import yaml
from typing import List, Optional, Dict
from src.analysis_library.analysis_intent import AnalysisIntent


class AnalysisLibrary:
    """YAML 驱动的分析知识库"""

    def __init__(self, yaml_dir: str = None):
        if yaml_dir is None:
            # 默认路径：相对于此文件所在目录
            yaml_dir = os.path.dirname(os.path.abspath(__file__))
        self.yaml_dir = yaml_dir
        self.intents: List[AnalysisIntent] = []
        self._intent_map: Dict[str, AnalysisIntent] = {}
        self._load_all()

    def _load_all(self):
        """加载目录下所有 .yaml 文件"""
        if not os.path.isdir(self.yaml_dir):
            return

        yaml_files = sorted([
            f for f in os.listdir(self.yaml_dir)
            if f.endswith(".yaml") or f.endswith(".yml")
        ])

        for filename in yaml_files:
            filepath = os.path.join(self.yaml_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "intent" in data:
                    intent = AnalysisIntent.from_dict(data)
                    self.intents.append(intent)
                    self._intent_map[intent.intent] = intent
            except Exception as e:
                # 单个 YAML 加载失败不影响其他
                print(f"[AnalysisLibrary] 跳过 {filename}: {e}")

        # 按 priority 降序排列
        self.intents.sort(key=lambda x: x.priority, reverse=True)

    def lookup(self, analysis_goal: str) -> Optional[AnalysisIntent]:
        """中文分析目标 → AnalysisIntent

        策略：遍历所有 intent 的 keywords，匹配 analysis_goal 中含有的关键词。
        多个 intent 命中时，返回 priority 最高的。
        无命中返回 None。
        """
        if not analysis_goal:
            return None

        goal_lower = analysis_goal.lower()
        best_match: Optional[AnalysisIntent] = None
        best_priority = -1

        for intent in self.intents:
            for keyword in intent.keywords:
                if keyword.lower() in goal_lower:
                    if intent.priority > best_priority:
                        best_match = intent
                        best_priority = intent.priority
                    break  # 一个 intent 匹配一次即可

        return best_match

    def get_by_intent(self, intent: str) -> Optional[AnalysisIntent]:
        """按 intent 标识精确获取"""
        return self._intent_map.get(intent)

    def list_intents(self) -> List[str]:
        """列出所有已注册的 intent 标识"""
        return [i.intent for i in self.intents]

    def get_all(self) -> List[AnalysisIntent]:
        """获取所有已注册的 AnalysisIntent（按 priority 降序）"""
        return list(self.intents)

    def reload(self):
        """重新加载所有 YAML（开发调试用）"""
        self.intents.clear()
        self._intent_map.clear()
        self._load_all()

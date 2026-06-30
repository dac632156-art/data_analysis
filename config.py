"""
配置文件 - 数据分析智能体
用户需要输入自己的 DeepSeek API Key 才能使用 AI 功能
"""

# DeepSeek API 配置
DEEPSEEK_API_URL = "https://api.deepseek.com"

# 默认模型
DEFAULT_MODEL = "deepseek-chat"

# 应用配置
APP_TITLE = "DataMind AI - 数据分析智能体"
APP_ICON = "📊"

# 文件上传配置
MAX_FILE_SIZE_MB = 200
SUPPORTED_FORMATS = ["csv", "xlsx", "xls", "json", "db", "sqlite"]

# 图表配色（清新浅绿渐变方案）
CHART_COLORS = ["#9FD8C8", "#5CB8A2", "#5A7C74", "#94B0A9", "#C7E6DF", "#2A4A43"]

# AI 配置
AI_TEMPERATURE = 0.3
AI_MAX_TOKENS = 2048

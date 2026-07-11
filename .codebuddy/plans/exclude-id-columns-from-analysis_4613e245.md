---
name: exclude-id-columns-from-analysis
overview: 在 ColumnClassifier 中添加 ID/编码关键词过滤，防止"客户编码"等标识列被误分类为数值指标，从而被 AI 和 Planner 选作分析目标。
todos:
  - id: add-id-keywords
    content: 在 column_classifier.py 中新增 ID_KEYWORDS 常量（模块级）和 _is_id_column() 私有方法
    status: completed
  - id: fix-get-numeric
    content: 修改 get_numeric_columns() 在数值类型判断前调用 _is_id_column() 跳过 ID 列
    status: completed
    dependencies:
      - add-id-keywords
  - id: fix-classify-all
    content: 修改 classify_all() 步骤2 在数值判断前增加 ID 列检查，ID 列归入 other
    status: completed
    dependencies:
      - add-id-keywords
  - id: verify
    content: 编写验证脚本确认"客户编码""订单号"等 ID 列被正确排除，正常数值列不受影响
    status: completed
    dependencies:
      - fix-get-numeric
      - fix-classify-all
---


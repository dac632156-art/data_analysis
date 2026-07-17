---
name: 抖音宣传方案_DataMind_AI
overview: 为已上线的 DataMind AI 数据分析智能体产出一套可直接用于抖音宣发与产品验证的内容素材包（账号定位、短视频脚本、钩子标题库、话题标签、引流话术、反馈收集闭环），以单个 Markdown 文档交付。
todos:
  - id: account-bio
    content: 撰写账号人设与主页 Bio、置顶评论话术，写入宣传方案文档
    status: completed
  - id: video-scripts
    content: 基于真实能力写 5-6 条短视频分镜脚本（口播/字幕/时长/BGM）
    status: completed
    dependencies:
      - account-bio
  - id: hook-tags
    content: 整理爆款标题钩子库与话题标签组合，覆盖各脚本角度
    status: completed
    dependencies:
      - video-scripts
  - id: funnel-feedback
    content: 设计引流转化话术与产品验证反馈闭环（收集/量化方法）
    status: completed
    dependencies:
      - account-bio
  - id: assemble-doc
    content: 汇编首月发布节奏建议，整合生成 抖音宣传方案_DataMind_AI.md
    status: completed
    dependencies:
      - video-scripts
      - hook-tags
      - funnel-feedback
---

## 用户需求

为已上线的 **DataMind AI 数据分析智能体** 制作抖音宣传内容，帮助在抖音传播并引导真实用户体验、收集反馈，完成产品验证。本次范围仅限内容创作，**不涉及部署上线、源码修改、应用内反馈入口、对外介绍页**（部署与 DeepSeek Key 问题用户已自行解决）。

## 产品概述

DataMind AI 是面向非技术人员的 AI 驱动数据分析 Web 平台：上传 Excel/CSV → 自动清洗 → AI 洞察 → ECharts 图表/可视化大屏 → 一键导出 HTML 报告。核心卖点为"不会代码也能做数据分析""上传表格秒出大屏与可发报告"。目标人群含业务运营/销售、产品经理、管理者、数据分析初学者。仓库根目录 `业务数据.csv` 可作为录屏演示素材。

## 核心交付（抖音宣传内容）

- 抖音账号定位与主页 Bio（人设、简介、置顶评论引导体验）
- 5-6 条短视频完整脚本（分镜 / 口播 / 字幕 / 时长 / BGM 建议）
- 爆款标题钩子库 + 话题标签组合
- 引流与转化话术（置顶评论、引导体验公开网址，网址用占位符）
- 产品验证闭环设计（如何收集、量化用户反馈）
- 首月发布节奏建议

交付物为单个 Markdown 文档：**抖音宣传方案_DataMind_AI.md**（置于仓库根目录），文案须基于真实产品能力、不夸大、口语化、强钩子。
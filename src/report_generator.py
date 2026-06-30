"""
HTML 报告生成模块 - 使用 Jinja2 模板渲染分析报告
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import base64
import io

def generate_html_report(df: pd.DataFrame, 
                         title: str = "数据分析报告",
                         insights: Optional[str] = None,
                         cleaning_history: Optional[list] = None) -> str:
    """生成 HTML 分析报告"""
    
    # 数据概览
    data_overview = {
        "行数": f"{len(df):,}",
        "列数": len(df.columns),
        "内存占用": f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB",
        "缺失值总数": int(df.isnull().sum().sum()),
        "重复行数": int(df.duplicated().sum()),
    }
    
    # 列信息表格（HTML）
    col_info = get_column_info_html(df)
    
    # 描述性统计表格（HTML）
    numeric_df = df.select_dtypes(include=['number'])
    stats_html = ""
    if len(numeric_df.columns) > 0:
        stats = numeric_df.describe().T
        stats_html = stats.to_html(classes="table", border=0)
    
    # 时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 构建 HTML
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: #1A0F0A;
            color: #F5E6D3;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #2D1F18;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        h1 {{
            color: #E8833A;
            border-bottom: 2px solid #E8833A;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 28px;
        }}
        h2 {{
            color: #F4A261;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 22px;
        }}
        .meta {{
            color: #B0BEC5;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .overview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .overview-card {{
            background: #1A0F0A;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #E8833A;
        }}
        .overview-card h3 {{
            color: #B0BEC5;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .overview-card p {{
            color: #F5E6D3;
            font-size: 24px;
            font-weight: bold;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background: #1A0F0A;
            border-radius: 8px;
            overflow: hidden;
        }}
        .table th {{
            background: #E8833A;
            color: white;
            padding: 12px;
            text-align: left;
            font-size: 14px;
        }}
        .table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #2D1F18;
            font-size: 13px;
        }}
        .table tr:hover {{
            background: #2D1F18;
        }}
        .insights {{
            background: #1A0F0A;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #F4A261;
            margin: 20px 0;
            white-space: pre-wrap;
        }}
        .footer {{
            text-align: center;
            color: #78909C;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #2D1F18;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="meta">生成时间：{timestamp} | 由 DataMind AI 自动生成</div>
        
        <h2>数据概览</h2>
        <div class="overview-grid">
            <div class="overview-card">
                <h3>总记录数</h3>
                <p>{data_overview['行数']}</p>
            </div>
            <div class="overview-card">
                <h3>字段数</h3>
                <p>{data_overview['列数']}</p>
            </div>
            <div class="overview-card">
                <h3>缺失值</h3>
                <p>{data_overview['缺失值总数']}</p>
            </div>
            <div class="overview-card">
                <h3>重复行</h3>
                <p>{data_overview['重复行数']}</p>
            </div>
        </div>
        
        {f'<h2>AI 数据洞察</h2><div class="insights">{insights}</div>' if insights else ''}
        
        <h2>字段详情</h2>
        {col_info}
        
        {f'<h2>描述性统计</h2>{stats_html}' if stats_html else ''}
        
        <div class="footer">
            Powered by DataMind AI | 数据分析智能体
        </div>
    </div>
</body>
</html>
"""
    return html

def get_column_info_html(df: pd.DataFrame) -> str:
    """生成列信息的 HTML 表格"""
    # 处理重复列名：df[重复列名] 会返回 DataFrame 导致 .dtype 报错
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    rows = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        missing = df[col].isnull().sum()
        missing_pct = f"{df[col].isnull().mean()*100:.1f}%"
        unique = df[col].nunique()
        sample = str(df[col].dropna().iloc[0]) if len(df[col].dropna()) > 0 else "N/A"
        if len(sample) > 30:
            sample = sample[:30] + "..."
        
        rows.append(f"""
        <tr>
            <td>{col}</td>
            <td>{dtype}</td>
            <td>{missing}</td>
            <td>{missing_pct}</td>
            <td>{unique}</td>
            <td>{sample}</td>
        </tr>
        """)
    
    return f"""
    <table class="table">
        <thead>
            <tr>
                <th>列名</th>
                <th>数据类型</th>
                <th>缺失值</th>
                <th>缺失率</th>
                <th>唯一值</th>
                <th>示例值</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """

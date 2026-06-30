"""测试 gl_map 图表生成"""
import sys
sys.path.insert(0, '.')
import pandas as pd
from src.echart_generator import create_chart

# 用项目中的 CSV 数据测试
df = pd.read_csv('业务数据.csv')
print("CSV columns:", df.columns.tolist())
print("CSV shape:", df.shape)
print("First 3 rows:")
print(df.head(3))

# 尝试生成 gl_map
try:
    result = create_chart(df, 'gl_map', x='省份', y='销售额')
    print("\n=== Series types ===")
    for s in result.get('series', []):
        t = s.get('type', 'unknown')
        dc = len(s.get('data', [])) if s.get('data') else 0
        print(f"  type={t}, data_count={dc}")
    
    print("\n=== Has geo3D ===", 'geo3D' in result)
    print("=== Has visualMap ===", 'visualMap' in result)
    
    map3d_series = [s for s in result.get('series', []) if s.get('type') == 'map3D']
    bar3d_series = [s for s in result.get('series', []) if s.get('type') == 'bar3D']
    print(f"\nmap3D series count: {len(map3d_series)}")
    print(f"bar3D series count: {len(bar3d_series)}")
    
    if map3d_series:
        data = map3d_series[0].get('data', [])
        print(f"map3D data items: {len(data)}")
        if data:
            print(f"  first: {data[0]}")
            print(f"  last: {data[-1]}")
    
    if bar3d_series:
        data = bar3d_series[0].get('data', [])
        print(f"bar3D data items: {len(data)}")
        if data:
            print(f"  first: {data[0]}")
except Exception as e:
    print(f"\n!!! Error: {e}")
    import traceback
    traceback.print_exc()

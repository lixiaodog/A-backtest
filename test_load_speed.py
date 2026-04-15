import time
import pandas as pd

print("测试数据加载速度...")

start = time.time()
df = pd.read_csv('c:/work/backtrader/data/300766_daily.csv', index_col='datetime', parse_dates=True)
print(f'读取 CSV 耗时: {time.time() - start:.3f}秒')
print(f'数据行数: {len(df)}')

start = time.time()
df.sort_index(inplace=True)
print(f'排序耗时: {time.time() - start:.3f}秒')

start = time.time()
cache_start = df.index.min()
cache_end = df.index.max()
print(f'获取 min/max 耗时: {time.time() - start:.3f}秒')

start = time.time()
start_dt = pd.to_datetime('20250101')
end_dt = pd.to_datetime('20260401')
filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]
print(f'过滤耗时: {time.time() - start:.3f}秒')
print(f'过滤后行数: {len(filtered)}')

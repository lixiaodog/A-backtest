import tushare as ts
import pandas as pd

# 获取完整数据
df = ts.get_k_data('300766', '2019-01-01', '2026-12-31')
print(f'获取到 {len(df)} 条数据')
print(f'日期范围: {df.date.min()} ~ {df.date.max()}')

# 处理格式
df.rename(columns={'date': 'datetime', 'open': 'open', 'close': 'close', 'high': 'high', 'low': 'low', 'volume': 'volume'}, inplace=True)
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)
df.sort_index(inplace=True)
df.index.name = 'datetime'

# 保存到缓存
df.to_csv('c:/work/backtrader/data/300766_daily.csv')
print('已保存到缓存')
print(df.head())
print('...')
print(df.tail())

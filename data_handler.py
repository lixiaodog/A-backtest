import tushare as ts
import pandas as pd
from datetime import datetime, timezone, timedelta
from backtrader.feeds import PandasData
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

class AStockData(PandasData):
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
    )

def get_cache_path(stock_code: str, period: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f'{stock_code}_{period}.csv')

def load_from_cache(stock_code: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    cache_path = get_cache_path(stock_code, period)
    if not os.path.exists(cache_path):
        return None

    try:
        df = pd.read_csv(cache_path, index_col='datetime', parse_dates=True)
        df.sort_index(inplace=True)

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # 检查缓存数据是否覆盖请求的日期范围
        cache_start = df.index.min()
        cache_end = df.index.max()
        
        if cache_start > start_dt or cache_end < end_dt:
            print(f'Cache data range [{cache_start.date()} ~ {cache_end.date()}] does not cover requested range [{start_dt.date()} ~ {end_dt.date()}], fetching new data')
            return None
        
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        print(f'Loaded {len(df)} rows from cache for {stock_code}_{period}')
        return df
    except Exception as e:
        print(f'Load from cache failed: {e}')
        return None

def save_to_cache(df: pd.DataFrame, stock_code: str, period: str):
    cache_path = get_cache_path(stock_code, period)
    df_local = df.copy()
    if df_local.index.tzinfo is not None:
        df_local.index = df_local.index.tz_localize(None)
    df_local.to_csv(cache_path)

def get_astock_hist_data(stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
    cached_df = load_from_cache(stock_code, period, start_date, end_date)
    if cached_df is not None and len(cached_df) > 0:
        print(f'Loaded {len(cached_df)} rows from cache for {stock_code}_{period}')
        return cached_df

    tushare_code = f'{stock_code}'
    start_str = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}'
    end_str = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}'
    
    # 将 period 转换为 tushare 的 ktype
    period_to_ktype = {
        'daily': 'D',
        'weekly': 'W',
        'monthly': 'M',
        '1min': '1',
        '5min': '5',
        '15min': '15',
        '30min': '30',
        '60min': '60',
    }
    ktype = period_to_ktype.get(period, 'D')
    
    df = ts.get_k_data(code=tushare_code, start=start_str, end=end_str, ktype=ktype)

    if df is None or len(df) == 0:
        raise Exception(f'获取数据失败: {stock_code}')

    df.rename(columns={
        'date': 'datetime',
        'open': 'open',
        'close': 'close',
        'high': 'high',
        'low': 'low',
        'volume': 'volume'
    }, inplace=True)

    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    save_to_cache(df, stock_code, period)

    return df[['open', 'high', 'low', 'close', 'volume']]

def load_csv_data(filepath: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    if 'date' in df.columns:
        df.rename(columns={'date': 'datetime'}, inplace=True)
    elif '日期' in df.columns:
        df.rename(columns={'日期': 'datetime'}, inplace=True)

    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)

    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df.index >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df.index <= end_dt]

    return df[['open', 'high', 'low', 'close', 'volume']]

def get_astock_info(stock_code: str) -> dict:
    try:
        df = ak.stock_individual_info_em(symbol=stock_code)
        info = dict(zip(df['item'], df['value']))
        return info
    except Exception as e:
        print(f"获取股票信息失败: {e}")
        return {}

if __name__ == "__main__":
    df = get_astock_hist_data("600519", "20230101", "20231231")
    print(f"数据形状: {df.shape}")
    print(df.tail())

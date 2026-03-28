import akshare as ak
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
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
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

    period_map = {
        'daily': 'daily',
        'weekly': 'weekly',
        'monthly': 'monthly',
    }

    minute_periods = {'1min': '1', '5min': '5', '15min': '15', '30min': '30', '60min': '60'}

    if period in minute_periods:
        df = ak.stock_zh_a_hist_min_em(
            symbol=stock_code,
            period=minute_periods[period],
            adjust="qfq"
        )
        df.rename(columns={
            '时间': 'datetime',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }, inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize('Asia/Shanghai')
        df.set_index('datetime', inplace=True)
        df.sort_index(inplace=True)
        save_to_cache(df, stock_code, period)
        start_dt = pd.to_datetime(start_date).tz_localize('Asia/Shanghai')
        end_dt = pd.to_datetime(end_date).tz_localize('Asia/Shanghai')
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        return df[['open', 'high', 'low', 'close', 'volume']]

    ak_period = period_map.get(period, 'daily')
    df = ak.stock_zh_a_hist(symbol=stock_code, period=ak_period,
                            start_date=start_date, end_date=end_date, adjust="qfq")

    df.rename(columns={
        '日期': 'datetime',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume'
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

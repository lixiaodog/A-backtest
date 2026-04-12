import pandas as pd
from datetime import datetime, timezone, timedelta
from backtrader.feeds import PandasData
import os

from providers import DataProviderManager

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

_data_provider_manager = None

def get_data_provider_manager() -> DataProviderManager:
    """获取数据提供者管理器（单例）"""
    global _data_provider_manager
    if _data_provider_manager is None:
        _data_provider_manager = DataProviderManager(priority=['local'])
    return _data_provider_manager

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

def save_to_cache(df: pd.DataFrame, stock_code: str, period: str):
    cache_path = get_cache_path(stock_code, period)
    df_local = df.copy()
    if df_local.index.tzinfo is not None:
        df_local.index = df_local.index.tz_localize(None)
    df_local.index.name = 'datetime'
    df_local.to_csv(cache_path)

def get_astock_hist_data(stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
    """获取A股历史数据，优先使用本地缓存"""
    manager = get_data_provider_manager()
    df = manager.get_hist_data(stock_code, start_date, end_date, period)

    if df is not None and len(df) > 0:
        return df[['open', 'high', 'low', 'close', 'volume']]

    raise Exception(f'获取数据失败: {stock_code}')

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
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=stock_code)
        info = dict(zip(df['item'], df['value']))
        return info
    except Exception as e:
        print(f"获取股票信息失败: {e}")
        return {}

if __name__ == "__main__":
    df = get_astock_hist_data("300766", "20250101", "20260401")
    print(f"数据形状: {df.shape}")
    print(df.tail())

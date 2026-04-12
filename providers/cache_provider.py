import os
import pandas as pd
from .base_provider import BaseDataProvider


class LocalCacheProvider(BaseDataProvider):
    """本地缓存数据提供者"""

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_path(self, stock_code: str, period: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f'{stock_code}_{period}.csv')

    def get_hist_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
        """
        从本地缓存获取历史数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期

        Returns:
            DataFrame 或 None（如果缓存不存在）
        """
        cache_path = self.get_cache_path(stock_code, period)
        if not os.path.exists(cache_path):
            return None

        try:
            df = pd.read_csv(cache_path, index_col='datetime', parse_dates=True)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            print(f'[LocalCacheProvider] 加载缓存失败: {e}')
            return None

    def is_available(self) -> bool:
        """检查本地缓存目录是否可访问"""
        return os.path.exists(self.cache_dir) and os.access(self.cache_dir, os.W_OK)

    def save_data(self, df: pd.DataFrame, stock_code: str, period: str):
        """保存数据到本地缓存"""
        cache_path = self.get_cache_path(stock_code, period)
        df_local = df.copy()
        if df_local.index.tzinfo is not None:
            df_local.index = df_local.index.tz_localize(None)
        df_local.index.name = 'datetime'
        df_local.to_csv(cache_path)

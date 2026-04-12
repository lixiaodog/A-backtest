from typing import List
import pandas as pd
from .base_provider import BaseDataProvider
from .cache_provider import LocalCacheProvider
from .tushare_provider import TushareProvider


class DataProviderManager:
    """数据提供者管理器，支持多数据源自动回退"""

    def __init__(self, priority: List[str] = None):
        """
        初始化数据提供者管理器

        Args:
            priority: Provider 优先级列表，如 ['local', 'tushare']
                   可选值: 'local', 'tushare'
        """
        if priority is None:
            priority = ['local', 'tushare']

        self.providers = []
        for name in priority:
            if name == 'local':
                self.providers.append(LocalCacheProvider())
            elif name == 'tushare':
                self.providers.append(TushareProvider())

    def get_hist_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
        """
        按优先级获取历史数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期

        Returns:
            DataFrame 或 None（所有 Provider 都失败）
        """
        last_error = None

        for provider in self.providers:
            try:
                print(f'[{provider.get_provider_name()}] 尝试获取数据...')
                df = provider.get_hist_data(stock_code, start_date, end_date, period)
                if df is not None and len(df) > 0:
                    print(f'[{provider.get_provider_name()}] 成功获取 {len(df)} 条数据')
                    return df
                else:
                    print(f'[{provider.get_provider_name()}] 返回数据为空，继续尝试下一个 Provider')
            except Exception as e:
                last_error = e
                print(f'[{provider.get_provider_name()}] 获取失败: {e}，继续尝试下一个 Provider')

        print(f'[DataProviderManager] 所有 Provider 都失败了，最后错误: {last_error}')
        return None

    def get_cache_provider(self) -> LocalCacheProvider:
        """获取本地缓存 Provider"""
        for provider in self.providers:
            if isinstance(provider, LocalCacheProvider):
                return provider
        return LocalCacheProvider()

    def save_to_cache(self, df: pd.DataFrame, stock_code: str, period: str):
        """保存数据到本地缓存"""
        cache_provider = self.get_cache_provider()
        cache_provider.save_data(df, stock_code, period)
        print(f'[DataProviderManager] 已保存数据到本地缓存')

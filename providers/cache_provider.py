import os
import pandas as pd
from .base_provider import BaseDataProvider


class LocalCacheProvider(BaseDataProvider):
    """本地缓存数据提供者"""

    MARKETS = ['SZ', 'SH', 'BJ']

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_market_from_code(self, stock_code: str) -> str:
        """根据股票代码判断市场"""
        if stock_code.startswith('6'):
            return 'SH'
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return 'SZ'
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            return 'BJ'
        return 'SZ'

    def get_cache_path(self, stock_code: str, period: str, market: str = None) -> str:
        """获取缓存文件路径"""
        if market is None:
            market = self._get_market_from_code(stock_code)
        period_map = {'daily': '1d', '1d': '1d', '1day': '1d', 'weekly': '1w', '1w': '1w', 'monthly': '1M', '1M': '1M'}
        period_dir = period_map.get(period, period)
        return os.path.join(self.cache_dir, market, period_dir, f'{stock_code}.csv')

    def get_hist_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'daily', market: str = None) -> pd.DataFrame:
        """
        从本地缓存获取历史数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期
            market: 市场（可选，自动判断）

        Returns:
            DataFrame 或 None（如果缓存不存在）
        """
        if market is None:
            market = self._get_market_from_code(stock_code)

        cache_path = self.get_cache_path(stock_code, period, market)
        if not os.path.exists(cache_path):
            return None

        try:
            df = pd.read_csv(cache_path, index_col='stime', parse_dates=True)
            df.sort_index(inplace=True)

            start_dt = pd.to_datetime(start_date[:4] + '-' + start_date[4:6] + '-' + start_date[6:8])
            end_dt = pd.to_datetime(end_date[:4] + '-' + end_date[4:6] + '-' + end_date[6:8])

            mask = (df.index >= start_dt) & (df.index <= end_dt)
            return df.loc[mask]

        except Exception as e:
            print(f'[LocalCacheProvider] 加载缓存失败: {e}')
            return None

    def is_available(self) -> bool:
        """检查本地缓存目录是否可访问"""
        return os.path.exists(self.cache_dir) and os.access(self.cache_dir, os.W_OK)

    def save_data(self, df: pd.DataFrame, stock_code: str, period: str, market: str = None):
        """保存数据到本地缓存"""
        if market is None:
            market = self._get_market_from_code(stock_code)

        cache_path = self.get_cache_path(stock_code, period, market)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        df_local = df.copy()
        if df_local.index.tzinfo is not None:
            df_local.index = df_local.index.tz_localize(None)
        df_local.index.name = 'datetime'
        df_local.to_csv(cache_path)

    def get_available_stocks(self, market: str = None, period: str = 'daily') -> list:
        """获取可用的股票列表"""
        period_map = {'daily': '1d', '1d': '1d', '1day': '1d', 'weekly': '1w', '1w': '1w', 'monthly': '1M', '1M': '1M'}
        period_dir = period_map.get(period, period)
        if market:
            market_dir = os.path.join(self.cache_dir, market, period_dir)
            if not os.path.exists(market_dir):
                return []
            return [f[:-4] for f in os.listdir(market_dir) if f.endswith('.csv')]

        stocks = set()
        for mkt in self.MARKETS:
            mkt_dir = os.path.join(self.cache_dir, mkt, period_dir)
            if os.path.exists(mkt_dir):
                for f in os.listdir(mkt_dir):
                    if f.endswith('.csv'):
                        stocks.add(f[:-4])
        return sorted(list(stocks))

    def get_markets(self) -> list:
        """获取可用的市场列表"""
        markets = []
        for mkt in self.MARKETS:
            if os.path.exists(os.path.join(self.cache_dir, mkt)):
                markets.append(mkt)
        return markets

    def get_stock_info(self, stock_code: str) -> dict:
        """获取股票信息"""
        return {'code': stock_code, 'name': stock_code}

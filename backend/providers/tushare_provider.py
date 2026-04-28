import pandas as pd
import tushare as ts
from .base_provider import BaseDataProvider


class TushareProvider(BaseDataProvider):
    """Tushare 数据提供者"""

    def __init__(self):
        self.initialized = True

    def _period_to_ktype(self, period: str) -> str:
        """将 period 转换为 tushare 的 ktype"""
        mapping = {
            'daily': 'D',
            'weekly': 'W',
            'monthly': 'M',
            '1min': '1',
            '5min': '5',
            '15min': '15',
            '30min': '30',
            '60min': '60',
        }
        return mapping.get(period, 'D')

    def get_hist_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
        """
        从 Tushare 获取历史数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期

        Returns:
            DataFrame 或 None（如果获取失败）
        """
        try:
            start_str = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}'
            end_str = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}'
            ktype = self._period_to_ktype(period)

            df = ts.get_k_data(code=stock_code, start=start_str, end=end_str, ktype=ktype)

            if df is None or len(df) == 0:
                print('[TushareProvider] 获取数据为空')
                return None

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

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            print(f'[TushareProvider] 获取数据失败: {e}')
            return None

    def is_available(self) -> bool:
        """检查 Tushare 是否可用"""
        try:
            ts.get_k_data('600000', '20230101', '20230110')
            return True
        except Exception:
            return False

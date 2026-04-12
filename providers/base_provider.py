from abc import ABC, abstractmethod
import pandas as pd


class BaseDataProvider(ABC):
    """数据提供者抽象基类"""

    @abstractmethod
    def get_hist_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
        """
        获取历史K线数据

        Args:
            stock_code: 股票代码（如 '300766'）
            start_date: 开始日期（如 '20200101'）
            end_date: 结束日期（如 '20260401'）
            period: 周期（daily/weekly/monthly/1min/5min/15min/30min/60min）

        Returns:
            DataFrame，包含 open, high, low, close, volume 列，datetime 索引
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查数据源是否可用

        Returns:
            True 如果可用，False 否则
        """
        pass

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        return self.__class__.__name__

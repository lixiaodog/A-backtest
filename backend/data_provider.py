"""
数据提供者抽象基类 - Provider 模式实现
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd


class DataProvider(ABC):
    """数据提供者抽象基类
    
    所有数据源提供者必须继承此类，实现以下方法：
    - get_stock_data: 获取单只股票数据
    - get_market_stocks: 获取市场所有股票代码
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称标识"""
        pass
    
    @abstractmethod
    def get_stock_data(self, stock_code: str, **kwargs) -> Optional[pd.DataFrame]:
        """获取单只股票数据
        
        Args:
            stock_code: 股票代码，如 "000001"
            **kwargs: 额外参数，如 period, days, date 等
            
        Returns:
            DataFrame 包含股票数据，列名应包括：
            - date: 日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量
            - name: 股票名称（可选）
        """
        pass
    
    @abstractmethod
    def get_market_stocks(self, market: str, **kwargs) -> List[str]:
        """获取市场所有股票代码
        
        Args:
            market: 市场代码，如 "SZ", "SH", "BJ"
            **kwargs: 额外参数
            
        Returns:
            股票代码列表
        """
        pass
    
    def is_available(self) -> bool:
        """检查数据源是否可用
        
        Returns:
            bool: 数据源是否可用
        """
        return True
    
    def get_error_message(self) -> str:
        return ""
    
    def get_stock_info(self, stock_code: str) -> dict:
        return {'code': stock_code, 'name': stock_code}

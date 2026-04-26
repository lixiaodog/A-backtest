"""
AKShare 数据提供者

从 AKShare 获取实时股票数据
"""
import traceback
from typing import List, Optional
import pandas as pd
import akshare as ak

from backend.data_provider import DataProvider


class AKShareProvider(DataProvider):
    """AKShare 数据提供者
    
    从 AKShare API 获取实时股票数据
    """
    
    def __init__(self, period: str = '1d', days: int = 300):
        """初始化
        
        Args:
            period: 数据周期，如 '1d', '1w', '1m'
            days: 获取历史数据的天数
        """
        self.period = period
        self.days = days
    
    @property
    def name(self) -> str:
        return "akshare"
    
    def get_stock_data(self, stock_code: str, **kwargs) -> Optional[pd.DataFrame]:
        """从 AKShare 获取股票数据
        
        Args:
            stock_code: 股票代码，如 "000001"
            **kwargs: 可选参数
                - period: 周期，覆盖初始化时的设置
                - days: 天数，覆盖初始化时的设置
                - market: 市场代码，自动推断
                
        Returns:
            DataFrame 包含股票数据
        """
        try:
            period = kwargs.get('period', self.period)
            days = kwargs.get('days', self.days)
            
            # 判断市场
            market = kwargs.get('market')
            if not market:
                market = self._infer_market(stock_code)
            
            # 根据市场获取数据
            if market == 'SH':
                # 上海市场
                df = ak.stock_zh_a_hist(
                    symbol=stock_code, 
                    period=period, 
                    adjust="qfq",
                    start_date="19700101"
                )
            elif market == 'BJ':
                # 北京市场
                df = ak.stock_bj_a_hist(
                    symbol=stock_code,
                    period=period,
                    adjust="qfq",
                    start_date="19700101"
                )
            else:
                # 默认深圳市场
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period=period,
                    adjust="qfq",
                    start_date="19700101"
                )
            
            if df is None or df.empty:
                print(f"[AKShareProvider] {stock_code} 无数据")
                return None
            
            # 标准化列名
            df = self._standardize_columns(df)
            
            # 获取股票名称
            try:
                stock_name = self._get_stock_name(stock_code, market)
                df['name'] = stock_name
            except:
                df['name'] = stock_code
            
            # 只取最近 N 天数据
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)
            
            return df
            
        except Exception as e:
            print(f"[AKShareProvider] 获取 {stock_code} 数据失败: {e}")
            return None
    
    def get_market_stocks(self, market: str, **kwargs) -> List[str]:
        """获取市场所有股票代码
        
        Args:
            market: 市场代码，如 "SZ", "SH", "BJ"
            
        Returns:
            股票代码列表
        """
        try:
            if market.upper() == "SZ":
                df = ak.stock_info_sz_name_code()
                return [str(code) for code in df["A股代码"].tolist()]
            elif market.upper() == "SH":
                df = ak.stock_info_sh_name_code()
                return [str(code) for code in df["证券代码"].tolist()]
            elif market.upper() == "BJ":
                df = ak.stock_info_bj_name_code()
                return [str(code) for code in df["证券代码"].tolist()]
            else:
                print(f"[AKShareProvider] 未知市场: {market}")
                return []
        except Exception as e:
            print(f"[AKShareProvider] 获取{market}股票列表失败: {e}")
            return []
    
    def _infer_market(self, stock_code: str) -> str:
        """根据股票代码推断市场
        
        Args:
            stock_code: 股票代码
            
        Returns:
            市场代码: SZ, SH, BJ
        """
        code = str(stock_code)
        
        # 上海市场
        if code.startswith(('60', '68', '69')):
            return 'SH'
        # 北京市场
        elif code.startswith(('8', '4')):
            return 'BJ'
        # 默认深圳市场
        else:
            return 'SZ'
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名
        
        将 AKShare 返回的列名统一为标准格式
        """
        # AKShare 默认列名: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover'
        }
        
        df = df.rename(columns=column_mapping)
        
        # 确保必要的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                print(f"[AKShareProvider] 警告: 缺少列 {col}")
        
        return df
    
    def _get_stock_name(self, stock_code: str, market: str) -> str:
        """获取股票名称
        
        Args:
            stock_code: 股票代码
            market: 市场代码
            
        Returns:
            股票名称
        """
        try:
            if market == 'SZ':
                df = ak.stock_info_sz_name_code()
                match = df[df['A股代码'] == stock_code]
                if not match.empty:
                    return match.iloc[0]['A股简称']
            elif market == 'SH':
                df = ak.stock_info_sh_name_code()
                match = df[df['证券代码'] == stock_code]
                if not match.empty:
                    return match.iloc[0]['证券简称']
            elif market == 'BJ':
                df = ak.stock_info_bj_name_code()
                match = df[df['证券代码'] == stock_code]
                if not match.empty:
                    return match.iloc[0]['证券简称']
        except:
            pass
        
        return stock_code

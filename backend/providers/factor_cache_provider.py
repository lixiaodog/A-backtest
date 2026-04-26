"""
因子缓存数据提供者

从本地因子缓存数据库读取数据用于预测
"""
import os
import sqlite3
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime

from backend.data_provider import DataProvider


class FactorCacheProvider(DataProvider):
    """因子缓存数据提供者
    
    从本地因子缓存数据库读取因子数据，用于选股
    同时也从本地CSV文件读取原始行情数据（用于标签计算等）
    """
    
    def __init__(self, 
                 cache_path: str = './data/factor_cache/',
                 raw_data_path: str = './data/',
                 factor_library: str = 'alpha191',
                 silent: bool = False,
                 stock_file_map: Dict[str, str] = None):
        """
        初始化因子缓存提供者
        
        Args:
            cache_path: 因子缓存目录路径
            raw_data_path: 原始数据目录路径（用于获取行情数据）
            factor_library: 因子库名称 ('alpha191' 或 'technical')
            silent: 是否静默模式（不输出日志）
            stock_file_map: 预先扫描好的股票文件映射（用于子进程，避免重复扫描）
        """
        self.cache_path = cache_path
        self.raw_data_path = raw_data_path
        self.factor_library = factor_library
        self._silent = silent
        self._stock_file_map = stock_file_map
        self._error_message = None
        self._available_stocks = None
        self._raw_data_provider = None
        
        self._check_availability()
    
    @property
    def name(self) -> str:
        return 'factor_cache'
    
    def _check_availability(self) -> None:
        """检查缓存目录是否可用"""
        if not os.path.exists(self.cache_path):
            self._error_message = f"因子缓存目录不存在: {self.cache_path}"
            return
        
        if not os.path.isdir(self.cache_path):
            self._error_message = f"因子缓存路径不是目录: {self.cache_path}"
            return
        
        db_files = [f for f in os.listdir(self.cache_path) if f.endswith('.db')]
        if not db_files:
            self._error_message = f"因子缓存目录下没有数据库文件: {self.cache_path}"
            return
        
        self._error_message = None
    
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self._error_message is None
    
    def get_error_message(self) -> Optional[str]:
        return self._error_message
    
    def get_stock_info(self, stock_code: str) -> Dict:
        return {'code': stock_code, 'name': stock_code}
    
    def _get_db_path(self, stock_code: str) -> str:
        """获取股票缓存数据库路径"""
        return os.path.join(self.cache_path, f"{stock_code}.db")
    
    def _get_cached_stocks(self) -> List[str]:
        """获取所有已缓存的股票代码"""
        if self._available_stocks is not None:
            return self._available_stocks
        
        stocks = []
        try:
            for f in os.listdir(self.cache_path):
                if f.endswith('.db'):
                    code = f[:-3]
                    stocks.append(code)
            self._available_stocks = sorted(stocks)
        except Exception as e:
            if not self._silent:
                print(f"[FactorCacheProvider] 获取缓存股票列表失败: {e}")
        
        return self._available_stocks or []
    
    def get_stock_data(self, stock_code: str, 
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       **kwargs) -> Optional[pd.DataFrame]:
        try:
            factor_library = kwargs.get('factor_library', self.factor_library)
            include_raw_data = kwargs.get('include_raw_data', True)
            factor_names = kwargs.get('factor_names', None)
            latest_only = kwargs.get('latest_only', False)
            
            db_path = self._get_db_path(stock_code)
            if not os.path.exists(db_path):
                return None
            
            if latest_only:
                alpha_df = self._query_factors(db_path, start_date, end_date, factor_names, 'alpha191', latest_only=True)
                tech_df = self._query_factors(db_path, start_date, end_date, factor_names, 'technical', latest_only=True)
                
                dfs = []
                if alpha_df is not None and not alpha_df.empty:
                    dfs.append(alpha_df)
                if tech_df is not None and not tech_df.empty:
                    dfs.append(tech_df)
                
                if not dfs:
                    return None
                
                df = pd.concat(dfs, axis=1)
                
                if factor_names:
                    available = [f for f in factor_names if f in df.columns]
                    if available:
                        df = df[available]
            else:
                df = self._query_factors(db_path, start_date, end_date, factor_names, factor_library, latest_only=False)
                
                if df is None or df.empty:
                    return None
                
                if include_raw_data:
                    raw_data = self._get_raw_data(stock_code, start_date, end_date, **kwargs)
                    if raw_data is not None and not raw_data.empty:
                        df = self._merge_data(df, raw_data)
            
            return df
            
        except Exception as e:
            if not self._silent:
                print(f"[FactorCacheProvider] 获取 {stock_code} 数据失败: {e}")
            return None
    
    def _query_factors(self, db_path: str, 
                       start_date: Optional[str], 
                       end_date: Optional[str],
                       factor_names: Optional[List[str]],
                       factor_library: str,
                       latest_only: bool = False) -> Optional[pd.DataFrame]:
        """从数据库查询因子数据"""
        try:
            with sqlite3.connect(db_path) as conn:
                if latest_only:
                    query = '''
                        SELECT trade_date, factor_name, factor_value 
                        FROM factor_data 
                        WHERE factor_library = ?
                        AND trade_date = (SELECT MAX(trade_date) FROM factor_data WHERE factor_library = ?)
                    '''
                    params = [factor_library, factor_library]
                else:
                    query = '''
                        SELECT trade_date, factor_name, factor_value 
                        FROM factor_data 
                        WHERE factor_library = ?
                    '''
                    params = [factor_library]
                    
                    if start_date:
                        query += ' AND trade_date >= ?'
                        params.append(start_date)
                    if end_date:
                        query += ' AND trade_date <= ?'
                        params.append(end_date)
                
                if factor_names:
                    placeholders = ','.join(['?' for _ in factor_names])
                    query += f' AND factor_name IN ({placeholders})'
                    params.extend(factor_names)
                
                if not latest_only:
                    query += ' ORDER BY trade_date'
                
                df = pd.read_sql_query(query, conn, params=params)
                
                if df.empty:
                    return None
                
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.pivot(index='trade_date', columns='factor_name', values='factor_value')
                
                return df
                
        except sqlite3.Error as e:
            if not self._silent:
                print(f"[FactorCacheProvider] 查询因子数据失败: {e}")
            return None
    
    def _get_raw_data(self, stock_code: str,
                      start_date: Optional[str],
                      end_date: Optional[str],
                      **kwargs) -> Optional[pd.DataFrame]:
        """获取原始行情数据"""
        try:
            if self._raw_data_provider is None:
                from backend.providers.local_provider import LocalDataProvider
                self._raw_data_provider = LocalDataProvider(
                    data_path=self.raw_data_path,
                    silent=self._silent,
                    stock_file_map=self._stock_file_map
                )
            
            market = kwargs.get('market')
            period = kwargs.get('period', '1d')
            
            raw_data = self._raw_data_provider.get_stock_data(
                stock_code, 
                start_date=start_date,
                end_date=end_date,
                market=market,
                period=period
            )
            
            return raw_data
            
        except Exception as e:
            if not self._silent:
                print(f"[FactorCacheProvider] 获取原始数据失败: {e}")
            return None
    
    def _merge_data(self, factor_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
        """合并因子数据和原始行情数据"""
        try:
            if isinstance(raw_df.index, pd.DatetimeIndex):
                raw_df = raw_df.reset_index()
            
            date_col = None
            for col in ['date', 'trade_date', 'datetime']:
                if col in raw_df.columns:
                    date_col = col
                    break
            
            if date_col:
                raw_df[date_col] = pd.to_datetime(raw_df[date_col])
                raw_df = raw_df.set_index(date_col)
            
            common_dates = factor_df.index.intersection(raw_df.index)
            if len(common_dates) == 0:
                return factor_df
            
            raw_cols = ['open', 'high', 'low', 'close', 'volume']
            raw_cols = [c for c in raw_cols if c in raw_df.columns]
            
            merged = factor_df.loc[common_dates].copy()
            for col in raw_cols:
                if col in raw_df.columns:
                    merged[col] = raw_df.loc[common_dates, col]
            
            return merged
            
        except Exception as e:
            if not self._silent:
                print(f"[FactorCacheProvider] 合并数据失败: {e}")
            return factor_df
    
    def get_market_stocks(self, market: str, **kwargs) -> List[str]:
        """
        获取市场股票列表
        
        从缓存目录中筛选指定市场的股票
        
        Args:
            market: 市场代码（'SH', 'SZ', 'BJ'）
            
        Returns:
            股票代码列表
        """
        stocks = self._get_cached_stocks()
        
        market_prefix = {
            'SH': ['6', '5'],
            'SZ': ['0', '3', '2'],
            'BJ': ['4', '8', '9']
        }
        
        prefixes = market_prefix.get(market, [])
        filtered = [s for s in stocks if any(s.startswith(p) for p in prefixes)]
        
        return filtered
    
    def get_cache_info(self, stock_code: str) -> dict:
        """获取股票缓存信息"""
        db_path = self._get_db_path(stock_code)
        if not os.path.exists(db_path):
            return {'exists': False}
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*), MIN(trade_date), MAX(trade_date)
                    FROM factor_data WHERE factor_library = ?
                ''', (self.factor_library,))
                
                count, min_date, max_date = cursor.fetchone()
                
                return {
                    'exists': True,
                    'record_count': count,
                    'min_date': min_date,
                    'max_date': max_date
                }
                
        except Exception as e:
            return {'exists': False, 'error': str(e)}
    
    def get_status(self) -> dict:
        """获取数据源状态"""
        stocks = self._get_cached_stocks()
        return {
            'available': self.is_available(),
            'cache_path': self.cache_path,
            'raw_data_path': self.raw_data_path,
            'factor_library': self.factor_library,
            'cached_stocks_count': len(stocks),
            'error': self._error_message
        }

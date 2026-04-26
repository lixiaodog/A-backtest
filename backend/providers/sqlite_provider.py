"""
SQLite 数据提供者

从 SQLite 数据库读取股票数据
"""
import os
import sqlite3
import pandas as pd
from typing import Optional, List
from datetime import datetime, timedelta

from backend.data_provider import DataProvider


class SQLiteProvider(DataProvider):
    """SQLite 数据库数据提供者
    
    从 SQLite 数据库读取股票历史数据
    
    数据库表结构预期:
    - 表名: stock_data 或动态表名（每只股票一个表）
    - 列: date, open, high, low, close, volume
    """
    
    def __init__(self, 
                 db_path: str = './data/stocks.db',
                 table_name: str = 'stock_data',
                 code_column: str = 'stock_code',
                 date_column: str = 'date'):
        """
        初始化 SQLite 提供者
        
        Args:
            db_path: SQLite 数据库文件路径
            table_name: 数据表名称，如果每只股票一个表，使用 '{stock_code}' 占位符
            code_column: 股票代码列名（如果使用单表存储多只股票）
            date_column: 日期列名
        """
        self.db_path = db_path
        self.table_name = table_name
        self.code_column = code_column
        self.date_column = date_column
        self._connection = None
        self._error_message = None
        
        # 检查数据库文件是否存在
        self._check_availability()
    
    @property
    def name(self) -> str:
        return 'sqlite'
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            # 启用 DataFrame 支持
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def _check_availability(self) -> None:
        """检查数据库是否可用"""
        if not os.path.exists(self.db_path):
            self._error_message = f"数据库文件不存在: {self.db_path}"
            return
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 检查表是否存在
            if '{stock_code}' not in self.table_name:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (self.table_name,)
                )
                if not cursor.fetchone():
                    self._error_message = f"数据表不存在: {self.table_name}"
                    return
            
            self._error_message = None
            
        except sqlite3.Error as e:
            self._error_message = f"数据库连接错误: {e}"
    
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self._error_message is None and os.path.exists(self.db_path)
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message
    
    def _get_table_name(self, stock_code: str) -> str:
        """获取指定股票的数据表名"""
        if '{stock_code}' in self.table_name:
            return self.table_name.format(stock_code=stock_code)
        return self.table_name
    
    def get_stock_data(self, stock_code: str, 
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       **kwargs) -> Optional[pd.DataFrame]:
        """
        获取股票历史数据
        
        Args:
            stock_code: 股票代码（如 '000001'）
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
            **kwargs: 额外参数
            
        Returns:
            DataFrame 包含股票数据，列名标准化为: date, open, high, low, close, volume
        """
        try:
            conn = self._get_connection()
            table = self._get_table_name(stock_code)
            
            # 构建查询
            if '{stock_code}' in self.table_name:
                # 每只股票一个表
                query = f"SELECT * FROM {table} WHERE 1=1"
                params = []
            else:
                # 单表存储，需要过滤股票代码
                query = f"SELECT * FROM {table} WHERE {self.code_column} = ?"
                params = [stock_code]
            
            # 添加日期过滤
            if start_date:
                query += f" AND {self.date_column} >= ?"
                params.append(start_date)
            if end_date:
                query += f" AND {self.date_column} <= ?"
                params.append(end_date)
            
            # 添加排序
            query += f" ORDER BY {self.date_column} ASC"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if df.empty:
                return None
            
            return self._standardize_columns(df)
            
        except sqlite3.Error as e:
            print(f"[SQLiteProvider] 查询错误: {e}")
            return None
        except Exception as e:
            print(f"[SQLiteProvider] 获取数据失败: {e}")
            return None
    
    def get_market_stocks(self, market: str, **kwargs) -> List[str]:
        """
        获取市场股票列表
        
        从数据库中查询所有可用的股票代码
        
        Args:
            market: 市场代码（'SH', 'SZ', 'BJ'）
            **kwargs: 额外参数
            
        Returns:
            股票代码列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stocks = []
            
            if '{stock_code}' in self.table_name:
                # 每只股票一个表，从表名提取代码
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                prefix = market.lower()
                for row in cursor.fetchall():
                    table_name = row[0]
                    # 假设表名格式为: sh600000, sz000001 等
                    if table_name.startswith(prefix):
                        # 去掉前缀，保留数字部分
                        code = table_name[len(prefix):]
                        stocks.append(code)
            else:
                # 单表存储，查询股票代码列
                query = f"SELECT DISTINCT {self.code_column} FROM {self.table_name}"
                cursor.execute(query)
                
                market_prefix = {
                    'SH': ['6', '5'],
                    'SZ': ['0', '3', '2'],
                    'BJ': ['4', '8', '9']
                }
                
                prefixes = market_prefix.get(market, [])
                for row in cursor.fetchall():
                    code = str(row[0])
                    if any(code.startswith(p) for p in prefixes):
                        stocks.append(code)
            
            return sorted(stocks)
            
        except sqlite3.Error as e:
            print(f"[SQLiteProvider] 查询市场股票失败: {e}")
            return []
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化 DataFrame 列名"""
        # 列名映射（支持常见的变体）
        column_mapping = {
            # 日期
            'date': 'date',
            'Date': 'date',
            'DATE': 'date',
            'trade_date': 'date',
            'datetime': 'date',
            # 开盘
            'open': 'open',
            'Open': 'open',
            'OPEN': 'open',
            # 最高
            'high': 'high',
            'High': 'high',
            'HIGH': 'high',
            # 最低
            'low': 'low',
            'Low': 'low',
            'LOW': 'low',
            # 收盘
            'close': 'close',
            'Close': 'close',
            'CLOSE': 'close',
            # 成交量
            'volume': 'volume',
            'Volume': 'volume',
            'VOLUME': 'volume',
            'vol': 'volume',
            'Vol': 'volume',
            'amount': 'volume',
        }
        
        # 重命名存在的列
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # 确保必需的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                print(f"[SQLiteProvider] 警告: 缺少列 '{col}'")
        
        return df
    
    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def __del__(self):
        """析构时关闭连接"""
        self.close()

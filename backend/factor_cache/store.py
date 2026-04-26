"""
SQLite 因子存储实现
"""

import sqlite3
import pandas as pd
import os
from typing import List, Optional


class SQLiteFactorStore:
    """单股票SQLite存储"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化单股票数据库"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # 因子数据表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS factor_data (
                    trade_date DATE NOT NULL,
                    factor_name VARCHAR(50) NOT NULL,
                    factor_library VARCHAR(20) NOT NULL,
                    factor_value REAL,
                    PRIMARY KEY (trade_date, factor_name, factor_library)
                )
            ''')
            
            # 创建索引
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lookup 
                ON factor_data(factor_library, factor_name, trade_date)
            ''')
            
            # 元数据表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS meta (
                    key VARCHAR(50) PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            conn.commit()
    
    def query(self, start_date: str = None, end_date: str = None,
              factor_names: List[str] = None,
              factor_library: str = 'alpha191') -> pd.DataFrame:
        """查询因子数据"""
        if not os.path.exists(self.db_path):
            return pd.DataFrame()
        
        with sqlite3.connect(self.db_path) as conn:
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
            
            query += ' ORDER BY trade_date'
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if df.empty:
                return pd.DataFrame()
            
            # 转换为宽格式
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.pivot(index='trade_date', columns='factor_name', values='factor_value')
            
            return df
    
    def _get_date_column(self, data: pd.DataFrame) -> pd.Series:
        """从数据中获取日期列"""
        # 首先检查是否有 date 或 stime 列
        if 'date' in data.columns:
            return pd.to_datetime(data['date'])
        elif 'stime' in data.columns:
            # stime 是整数格式如 20150105
            return pd.to_datetime(data['stime'].astype(str), format='%Y%m%d')
        # 然后检查索引是否是日期类型
        elif isinstance(data.index, pd.DatetimeIndex):
            return pd.to_datetime(data.index)
        elif hasattr(data.index, 'strftime'):
            return pd.to_datetime(data.index)
        # 尝试将索引转换为日期
        else:
            try:
                return pd.to_datetime(data.index)
            except:
                # 如果都失败，抛出错误而不是使用当前日期
                raise ValueError(f"无法从数据中获取日期列。columns: {data.columns.tolist()}, index: {data.index[:3]}")
    
    def save(self, data: pd.DataFrame, factor_library: str = 'alpha191'):
        """保存因子数据（全量替换）"""
        data = data.copy()
        
        # 获取日期列
        date_series = self._get_date_column(data)
        data['trade_date'] = date_series
        
        # 转换为长格式
        df_long = data.reset_index(drop=True).melt(
            id_vars=['trade_date'],
            var_name='factor_name',
            value_name='factor_value'
        )
        
        with sqlite3.connect(self.db_path) as conn:
            # 删除该库的所有数据
            conn.execute('DELETE FROM factor_data WHERE factor_library = ?', (factor_library,))
            
            # 插入新数据（使用 REPLACE 避免唯一性冲突）
            for _, row in df_long.iterrows():
                trade_date = row['trade_date']
                # 统一转换为字符串格式
                if pd.notna(trade_date):
                    trade_date = pd.to_datetime(trade_date).strftime('%Y-%m-%d')
                else:
                    trade_date = None
                conn.execute('''
                    INSERT OR REPLACE INTO factor_data (trade_date, factor_name, factor_library, factor_value)
                    VALUES (?, ?, ?, ?)
                ''', (trade_date, row['factor_name'], factor_library, row['factor_value']))
            
            conn.commit()
            
            # 更新元数据
            conn.execute('''
                INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)
            ''', (f'last_update_{factor_library}', pd.Timestamp.now().isoformat()))
            conn.commit()
    
    def append(self, data: pd.DataFrame, factor_library: str = 'alpha191'):
        """追加因子数据（增量）"""
        data = data.copy()
        
        # 获取日期列
        date_series = self._get_date_column(data)
        data['trade_date'] = date_series
        
        # 转换为长格式
        df_long = data.reset_index(drop=True).melt(
            id_vars=['trade_date'],
            var_name='factor_name',
            value_name='factor_value'
        )
        
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df_long.iterrows():
                trade_date = row['trade_date']
                # 统一转换为字符串格式
                if pd.notna(trade_date):
                    trade_date = pd.to_datetime(trade_date).strftime('%Y-%m-%d')
                else:
                    trade_date = None
                conn.execute('''
                    INSERT OR REPLACE INTO factor_data 
                        (trade_date, factor_name, factor_library, factor_value)
                    VALUES (?, ?, ?, ?)
                ''', (trade_date, row['factor_name'], factor_library, row['factor_value']))
            
            conn.commit()
            
            # 更新元数据
            conn.execute('''
                INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)
            ''', (f'last_update_{factor_library}', pd.Timestamp.now().isoformat()))
            conn.commit()
    
    def exists(self, factor_library: str = 'alpha191') -> bool:
        """检查是否有该库的缓存"""
        if not os.path.exists(self.db_path):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM factor_data WHERE factor_library = ?',
                (factor_library,)
            )
            return cursor.fetchone()[0] > 0
    
    def get_last_date(self, factor_library: str = 'alpha191') -> Optional[str]:
        """获取最后更新的日期"""
        if not os.path.exists(self.db_path):
            return None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT MAX(trade_date) FROM factor_data WHERE factor_library = ?',
                (factor_library,)
            )
            result = cursor.fetchone()[0]
            return result
    
    def get_stats(self, factor_library: str = 'alpha191') -> dict:
        """获取统计信息"""
        if not os.path.exists(self.db_path):
            return {'count': 0, 'min_date': None, 'max_date': None}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT COUNT(*), MIN(trade_date), MAX(trade_date) 
                FROM factor_data 
                WHERE factor_library = ?
            ''', (factor_library,))
            count, min_date, max_date = cursor.fetchone()
            
            # 获取因子数量
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT factor_name) 
                FROM factor_data 
                WHERE factor_library = ?
            ''', (factor_library,))
            factor_count = cursor.fetchone()[0]
            
            # 获取日期数量
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT trade_date) 
                FROM factor_data 
                WHERE factor_library = ?
            ''', (factor_library,))
            date_count = cursor.fetchone()[0]
            
            return {
                'count': count,
                'min_date': min_date,
                'max_date': max_date,
                'factor_count': factor_count,
                'date_count': date_count
            }
    
    def verify_completeness(self, factor_library: str = 'alpha191',
                           expected_factors: int = 191) -> dict:
        """
        验证数据完整性

        Returns:
            {
                'is_complete': bool,      # 是否完整
                'is_valid': bool,         # 是否有效（有数据）
                'date_count': int,        # 日期数量
                'factor_count': int,      # 实际因子数量
                'expected_factors': int,  # 期望因子数量
                'record_count': int,      # 总记录数
                'expected_records': int,  # 期望记录数
                'issues': list            # 发现的问题
            }
        """
        issues = []

        # 检查文件是否存在
        if not os.path.exists(self.db_path):
            return {
                'is_complete': False,
                'is_valid': False,
                'date_count': 0,
                'factor_count': 0,
                'expected_factors': expected_factors,
                'record_count': 0,
                'expected_records': 0,
                'issues': ['数据库文件不存在']
            }

        with sqlite3.connect(self.db_path) as conn:
            # 获取基本统计
            cursor = conn.execute('''
                SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT factor_name)
                FROM factor_data
                WHERE factor_library = ?
            ''', (factor_library,))
            record_count, date_count, factor_count = cursor.fetchone()

            # 无数据
            if record_count == 0:
                return {
                    'is_complete': False,
                    'is_valid': False,
                    'date_count': 0,
                    'factor_count': 0,
                    'expected_factors': expected_factors,
                    'record_count': 0,
                    'expected_records': 0,
                    'issues': ['无数据']
                }

            # 计算期望记录数
            expected_records = date_count * expected_factors

            # 检查因子数量
            if factor_count < expected_factors:
                issues.append(f'因子数量不足: {factor_count}/{expected_factors}')

            # 检查记录数（日期 × 因子数）
            if record_count < expected_records:
                issues.append(f'记录数不足: {record_count}/{expected_records}')

            # 注：不再检查重复记录，因为数据库主键约束已确保唯一性
            # (trade_date, factor_name, factor_library) 是联合主键

            is_complete = len(issues) == 0

            return {
                'is_complete': is_complete,
                'is_valid': True,
                'date_count': date_count,
                'factor_count': factor_count,
                'expected_factors': expected_factors,
                'record_count': record_count,
                'expected_records': expected_records,
                'issues': issues
            }
    
    def mark_complete(self, factor_library: str = 'alpha191', is_complete: bool = True):
        """标记缓存是否完整"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO meta (key, value) 
                VALUES (?, ?)
            ''', (f'is_complete_{factor_library}', '1' if is_complete else '0'))
            conn.commit()
    
    def is_marked_complete(self, factor_library: str = 'alpha191') -> bool:
        """检查是否标记为完整"""
        if not os.path.exists(self.db_path):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT value FROM meta WHERE key = ?',
                (f'is_complete_{factor_library}',)
            )
            result = cursor.fetchone()
            return result is not None and result[0] == '1'

"""
因子缓存管理器 - 对外统一接口
"""

import pandas as pd
from typing import List, Optional, Callable
from .router import FactorStoreRouter
from .store import SQLiteFactorStore
import os
from datetime import datetime


def _get_current_time():
    """获取当前时间字符串"""
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


def _load_single_stock_data(stock_code: str, data_path: str) -> pd.DataFrame:
    """
    直接加载单只股票数据（子进程使用，避免扫描整个目录）
    
    Args:
        stock_code: 股票代码
        data_path: 数据目录路径
        
    Returns:
        DataFrame 包含股票数据，未找到返回 None
    """
    import os
    
    # 尝试直接构建文件路径
    filepath = os.path.join(data_path, f"{stock_code}.csv")
    
    if not os.path.exists(filepath):
        # 如果在根目录找不到，尝试在子目录中搜索
        for root, dirs, files in os.walk(data_path):
            if f"{stock_code}.csv" in files:
                filepath = os.path.join(root, f"{stock_code}.csv")
                break
    
    if not os.path.exists(filepath):
        print(f"[子进程] 未找到股票 {stock_code} 的数据文件")
        return None
    
    try:
        df = pd.read_csv(filepath)
        
        if df.empty:
            print(f"[子进程] {stock_code} 数据为空")
            return None
        
        # 标准化列名（与 LocalDataProvider 保持一致）
        column_mapping = {
            'stock_code': 'code',
            'ts_code': 'code',
            'trade_date': 'date',
            ' TradingDay': 'date',
            'stime': 'date',  # 关键：stime 也是日期列
            'open': 'open',
            ' OpenPrice': 'open',
            'high': 'high',
            ' HighPrice': 'high',
            'low': 'low',
            ' LowPrice': 'low',
            'close': 'close',
            ' ClosePrice': 'close',
            'volume': 'volume',
            ' Volume': 'volume',
            'amount': 'amount',
            ' Amount': 'amount',
        }
        
        # 去除列名空格
        df.columns = [col.strip() for col in df.columns]
        
        # 应用映射
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        # 处理日期列
        if 'date' in df.columns:
            try:
                if df['date'].dtype in ['int64', 'int32', 'float64']:
                    df['date'] = pd.to_datetime(df['date'].astype(int).astype(str), format='%Y%m%d')
                else:
                    df['date'] = pd.to_datetime(df['date'])
            except:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.sort_values('date')
            df = df.set_index('date')
        
        print(f"[子进程] 成功加载 {stock_code}: {len(df)} 条记录")
        return df
        
    except Exception as e:
        print(f"[子进程] 读取 {stock_code} 数据失败: {e}")
        return None


def _generate_factors_for_stock(stock_code: str, raw_data: pd.DataFrame, 
                                factor_library: str, base_path: str,
                                force_full: bool = False) -> tuple:
    """
    统一的股票因子生成函数 - 被单进程/多进程/多线程共用
    
    Args:
        stock_code: 股票代码
        raw_data: 原始股票数据（已设置日期索引）
        factor_library: 因子库名称 'alpha191' 或 'technical'
        base_path: 缓存基础路径
        force_full: 是否强制全量更新
        
    Returns:
        (success: bool, message: str, updated_count: int)
    """
    try:
        # 创建manager实例
        manager = FactorCacheManager(base_path)
        
        # 获取更新类型
        if force_full:
            update_type = 'full'
        else:
            update_type = manager.get_cache_update_type(stock_code, raw_data, factor_library)
        
        # 详细日志
        store = manager._get_store(stock_code)
        cache_last_date = store.get_last_date(factor_library)
        expected_factors = 29 if factor_library == 'technical' else 191
        verification = store.verify_completeness(factor_library, expected_factors)
        raw_last_date = manager._get_raw_data_last_date(raw_data)
        
        pid = os.getpid()
        print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 检测: 缓存日期={cache_last_date}, 数据日期={raw_last_date}, 完整={verification['is_complete']}, 记录={verification.get('record_count', 0)}/{verification.get('expected_records', 0)}")
        
        if update_type == 'none':
            print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 无需更新")
            return True, '无需更新', 0
        elif update_type == 'full':
            # 全量更新
            print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 执行全量更新")
            manager.compute_and_save(stock_code, raw_data, factor_library)
            print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 全量更新完成: {len(raw_data)} 条记录")
            return True, '全量更新完成', len(raw_data)
        else:
            # 增量更新
            print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 执行增量更新 (缓存: {cache_last_date} → 数据: {raw_last_date})")
            manager.incremental_update(stock_code, raw_data, factor_library)
            print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 增量更新完成")
            return True, '增量更新完成', 1
            
    except Exception as e:
        import traceback
        pid = os.getpid()
        print(f"[{_get_current_time()}] [进程-{pid}] {stock_code} 处理失败: {e}")
        print(traceback.format_exc())
        return False, str(e), 0


def _update_single_stock(args):
    """
    多进程更新单只股票（独立函数，必须在模块顶层定义）
    
    Args:
        args: (stock_code, data_path, factor_library, base_path, force_full)
    
    Returns:
        (stock_code, success, message, updated_count)
    """
    stock_code, data_path, factor_library, base_path, force_full = args
    
    print(f"[{_get_current_time()}] [子进程-{os.getpid()}] 开始处理 {stock_code}")
    
    # 加载数据
    raw_data = _load_single_stock_data(stock_code, data_path)
    
    if raw_data is None:
        print(f"[{_get_current_time()}] [子进程-{os.getpid()}] {stock_code} 未找到数据文件，跳过")
        return stock_code, False, '未找到数据文件', 0
    
    print(f"[{_get_current_time()}] [子进程-{os.getpid()}] {stock_code} 数据加载完成: {len(raw_data)} 条记录")
    
    # 调用统一的因子生成函数
    success, message, updated_count = _generate_factors_for_stock(
        stock_code, raw_data, factor_library, base_path, force_full
    )
    
    return stock_code, success, message, updated_count


class FactorCacheManager:
    """因子缓存管理器 - 对外主要接口"""
    
    def __init__(self, base_path: str = None):
        # 使用 router 的默认路径逻辑（绝对路径）
        self.router = FactorStoreRouter(base_path)
        self.base_path = self.router.base_path
        self._store_cache = {}  # 连接缓存
    
    def _get_store(self, stock_code: str) -> SQLiteFactorStore:
        """获取（或创建）股票的存储实例"""
        if stock_code not in self._store_cache:
            db_path = self.router.get_db_path(stock_code)
            self._store_cache[stock_code] = SQLiteFactorStore(db_path)
        return self._store_cache[stock_code]
    
    # ========== 读取接口 ==========
    
    def get_factors(self, stock_code: str,
                   start_date: str = None,
                   end_date: str = None,
                   factor_names: List[str] = None,
                   factor_library: str = 'alpha191') -> pd.DataFrame:
        """
        读取因子数据（业务层唯一需要调用的方法）
        
        如果没有缓存，返回空DataFrame（不自动计算）
        """
        store = self._get_store(stock_code)
        return store.query(start_date, end_date, factor_names, factor_library)
    
    def has_cache(self, stock_code: str, 
                  factor_library: str = 'alpha191') -> bool:
        """检查是否有缓存"""
        store = self._get_store(stock_code)
        return store.exists(factor_library)
    
    def get_cache_status(self, stock_code: str) -> dict:
        """获取缓存状态"""
        store = self._get_store(stock_code)
        
        technical_stats = store.get_stats('technical')
        alpha191_stats = store.get_stats('alpha191')
        
        # 使用新的验证方法
        technical_verify = store.verify_completeness('technical', 29)
        alpha191_verify = store.verify_completeness('alpha191', 191)
        
        return {
            'stock_code': stock_code,
            'technical': {**technical_stats, **technical_verify},
            'alpha191': {**alpha191_stats, **alpha191_verify},
            'is_complete': technical_verify.get('is_complete', False) and alpha191_verify.get('is_complete', False)
        }
    
    def verify_stock_cache(self, stock_code: str, 
                          factor_library: str = 'alpha191',
                          expected_factors: int = 191) -> dict:
        """
        验证单股票缓存完整性
        
        Returns:
            完整性验证结果
        """
        store = self._get_store(stock_code)
        return store.verify_completeness(factor_library, expected_factors)
    
    def is_cache_complete(self, stock_code: str,
                         factor_library: str = 'alpha191',
                         raw_data: pd.DataFrame = None) -> bool:
        """
        检查缓存是否完整（带验证）
        
        如果提供了raw_data，会同时检查日期范围是否匹配
        
        Args:
            stock_code: 股票代码
            factor_library: 因子库
            raw_data: 可选，原始数据，用于比对日期范围
        
        Returns:
            True - 缓存完整且日期匹配（不需要更新）
            False - 需要重新计算或增量更新
        """
        store = self._get_store(stock_code)
        
        # 如果标记为不完整，直接返回False
        if not store.is_marked_complete(factor_library):
            return False
        
        # 获取缓存的最后日期
        cache_last_date = store.get_last_date(factor_library)
        if cache_last_date is None:
            return False
        
        # 如果提供了原始数据，检查日期范围
        if raw_data is not None and not raw_data.empty:
            raw_last_date = self._get_raw_data_last_date(raw_data)
            
            # 如果原始数据有更新，缓存不算"完整"（需要增量更新）
            if raw_last_date and str(raw_last_date) > str(cache_last_date):
                return False
        
        # 即使标记为完整，也进行实际验证
        expected_factors = 29 if factor_library == 'technical' else 191
        verification = store.verify_completeness(factor_library, expected_factors)
        
        # 如果实际不完整，更新标记
        if not verification['is_complete']:
            store.mark_complete(factor_library, False)
            return False
        
        return True
    
    def get_cache_update_type(self, stock_code: str,
                             raw_data: pd.DataFrame,
                             factor_library: str = 'alpha191') -> str:
        """
        判断缓存更新类型
        
        Returns:
            'none' - 不需要更新（完整且日期匹配）
            'incremental' - 增量更新（有缓存，但日期落后）
            'full' - 全量更新（无缓存或不完整）
        """
        store = self._get_store(stock_code)
        
        # 检查是否有缓存
        cache_last_date = store.get_last_date(factor_library)
        if cache_last_date is None:
            return 'full'
        
        # 检查完整性
        expected_factors = 29 if factor_library == 'technical' else 191
        verification = store.verify_completeness(factor_library, expected_factors)
        if not verification['is_complete']:
            return 'full'
        
        # 检查日期数量是否足够（防止缓存只有少量数据的情况）
        cache_date_count = verification.get('date_count', 0)
        raw_date_count = len(raw_data)
        if cache_date_count < raw_date_count * 0.5:
            return 'full'
        
        # 检查日期范围
        raw_last_date = self._get_raw_data_last_date(raw_data)
        if raw_last_date and str(raw_last_date) > str(cache_last_date):
            return 'incremental'
        
        return 'none'
    
    def _compute_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标（不依赖外部模块）
        
        使用字典收集数据避免DataFrame内存碎片警告
        
        Returns:
            DataFrame with technical indicators
        """
        import numpy as np
        
        data = {}
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # 移动平均线 - 相对值（MA/CLOSE）
        for period in [5, 10, 20, 30, 60, 120, 250]:
            data[f'ma{period}'] = close.rolling(window=period).mean() / close
        
        # EMA - 相对值（EMA/CLOSE）
        data['ema12'] = close.ewm(span=12).mean() / close
        data['ema26'] = close.ewm(span=26).mean() / close
        
        # MACD - 相对值（MACD/CLOSE）
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = (ema12 - ema26) / close
        data['macd'] = macd
        macd_signal = macd.ewm(span=9).mean()
        data['macd_signal'] = macd_signal
        data['macd_diff'] = macd - macd_signal
        
        # RSI
        for period in [6, 12, 24]:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            data[f'rsi{period}'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands - 相对值（BOLL/CLOSE）
        ma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        data['bollinger_upper'] = (ma20 + 2 * std20) / close
        data['bollinger_middle'] = ma20 / close
        data['bollinger_lower'] = (ma20 - 2 * std20) / close
        
        # KDJ
        low_min = low.rolling(window=9).min()
        high_max = high.rolling(window=9).max()
        rsv = 100 * (close - low_min) / (high_max - low_min)
        kdj_k = rsv.ewm(com=2).mean()
        kdj_d = kdj_k.ewm(com=2).mean()
        data['kdj_k'] = kdj_k
        data['kdj_d'] = kdj_d
        data['kdj_j'] = 3 * kdj_k - 2 * kdj_d
        
        # ATR - 相对值（ATR/CLOSE）
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        data['atr'] = tr.rolling(window=14).mean() / close
        
        # Volume ratio
        data['volume_ratio'] = volume / volume.rolling(window=5).mean()
        
        # Returns
        for period in [1, 5, 10]:
            data[f'return_{period}d'] = close.pct_change(period)
        
        # Volatility
        for period in [5, 20]:
            data[f'volatility_{period}d'] = close.pct_change().rolling(window=period).std()
        
        # High-Low ratio
        data['high_low_ratio'] = high / low
        
        return pd.DataFrame(data, index=df.index)
    
    def compute_and_save(self, stock_code: str,
                        raw_data: pd.DataFrame,
                        factor_library: str = 'alpha191'):
        """
        计算并保存因子（全量）
        """
        if factor_library == 'alpha191':
            from backend.ml.alpha191 import Alpha191
            calculator = Alpha191()
            factors = calculator.get_all_alphas(raw_data)
        elif factor_library == 'technical':
            factors = self._compute_technical_indicators(raw_data)
        else:
            raise ValueError(f"未知的因子库: {factor_library}")
        
        store = self._get_store(stock_code)
        store.save(factors, factor_library)
        
        # 验证并标记完整性
        expected_factors = 29 if factor_library == 'technical' else 191
        verification = store.verify_completeness(factor_library, expected_factors)
        store.mark_complete(factor_library, verification['is_complete'])
    
    def incremental_update(self, stock_code: str,
                          raw_data: pd.DataFrame,
                          factor_library: str = 'alpha191'):
        """
        增量更新因子
        
        只计算新增日期的数据
        """
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        ml_path = os.path.join(project_root, 'ml')
        if ml_path not in sys.path:
            sys.path.insert(0, ml_path)
        
        store = self._get_store(stock_code)
        
        # 获取已有数据的最新日期
        last_date = store.get_last_date(factor_library)
        
        if last_date is None:
            # 无缓存，全量计算
            self.compute_and_save(stock_code, raw_data, factor_library)
            return
        
        # 只取新数据
        new_data = raw_data[raw_data.index > last_date]
        
        if len(new_data) == 0:
            return  # 无新数据
        
        # 计算新数据（需要包含窗口期）
        if factor_library == 'alpha191':
            # Alpha191主要用20天窗口
            window_size = 30
            start_idx = max(0, len(raw_data) - len(new_data) - window_size)
            extended_data = raw_data.iloc[start_idx:]
            
            from backend.ml.alpha191 import Alpha191
            calculator = Alpha191()
            new_factors = calculator.get_all_alphas(extended_data)
            # 只保存新日期的数据
            new_factors = new_factors.loc[new_data.index]
            
        elif factor_library == 'technical':
            # 技术指标计算 - 直接计算，不依赖外部模块
            # 技术指标需要窗口期，取更多历史数据
            window_size = 250  # 最长均线周期
            start_idx = max(0, len(raw_data) - len(new_data) - window_size)
            extended_data = raw_data.iloc[start_idx:]
            
            all_factors = self._compute_technical_indicators(extended_data)
            # 只保存新日期的数据
            new_factors = all_factors.loc[new_data.index]
        else:
            raise ValueError(f"未知的因子库: {factor_library}")
        
        store.append(new_factors, factor_library)
    
    def delete_stock_cache(self, stock_code: str):
        """删除指定股票的缓存"""
        db_path = self.router.get_db_path(stock_code)
        if os.path.exists(db_path):
            os.remove(db_path)
        if stock_code in self._store_cache:
            del self._store_cache[stock_code]
    
    def delete_all_cache(self):
        """删除所有缓存"""
        if os.path.exists(self.base_path):
            for filename in os.listdir(self.base_path):
                if filename.endswith('.db'):
                    os.remove(os.path.join(self.base_path, filename))
        self._store_cache.clear()
    
    def _get_raw_data_last_date(self, raw_data: pd.DataFrame) -> str:
        """从原始数据中获取最后日期，统一返回 YYYY-MM-DD 格式"""
        if raw_data is None or raw_data.empty:
            return None
        
        # 优先使用 date/stime 列
        if 'date' in raw_data.columns:
            date_col = pd.to_datetime(raw_data['date'])
            return date_col.max().strftime('%Y-%m-%d')
        elif 'stime' in raw_data.columns:
            # stime 是整数格式如 20150105，转换为 YYYY-MM-DD
            date_col = pd.to_datetime(raw_data['stime'].astype(str), format='%Y%m%d')
            return date_col.max().strftime('%Y-%m-%d')
        elif isinstance(raw_data.index, pd.DatetimeIndex):
            # 日期在索引中
            return raw_data.index.max().strftime('%Y-%m-%d')
        else:
            # 尝试将索引转换为日期
            try:
                return pd.to_datetime(raw_data.index).max().strftime('%Y-%m-%d')
            except:
                return None
    
    def get_global_stats(self) -> dict:
        """获取全局统计信息"""
        base_path = self.router.base_path
        
        stock_count = 0
        total_size_bytes = 0
        technical_count = 0
        alpha191_count = 0
        
        try:
            for entry in os.scandir(base_path):
                if entry.name.endswith('.db'):
                    stock_count += 1
                    stat = entry.stat()
                    total_size_bytes += stat.st_size
                    
                    # 根据文件大小估算包含的因子库
                    file_size = stat.st_size
                    if file_size > 100 * 1024:  # 100KB
                        technical_count += 1
                        if file_size > 1 * 1024 * 1024:  # 1MB
                            alpha191_count += 1
        except Exception as e:
            print(f"[get_global_stats] 扫描目录失败: {e}")
        
        libraries = {
            'technical': {'factor_count': 29, 'stock_count': technical_count},
            'alpha191': {'factor_count': 191, 'stock_count': alpha191_count}
        }
        
        # 计算覆盖率（假设全市场5000只）
        coverage = stock_count / 5000
        
        # 同时返回 MB 和 GB 格式
        total_size_mb = total_size_bytes / (1024 * 1024)
        
        return {
            'stock_count': stock_count,
            'total_size_mb': total_size_mb,
            'total_size_gb': round(total_size_mb / 1024, 2),
            'coverage': coverage,
            'libraries': libraries,
            'last_update': None
        }

    def batch_incremental_update(self,
                                 stock_data_map: dict,
                                 factor_library: str = 'alpha191',
                                 max_workers: int = None,
                                 progress_callback: Callable = None,
                                 data_path: str = None,
                                 force_full: bool = False) -> dict:
        """
        批量增量更新（多进程）

        Args:
            stock_data_map: {stock_code: raw_data_df} 字典（只用于获取股票代码列表）
            factor_library: 因子库名称
            max_workers: 并发进程数
            progress_callback: 进度回调函数，接收 (current, total, stock_code, status)
            data_path: 数据目录路径，用于子进程加载数据
            force_full: 是否强制全量更新

        Returns:
            {
                'success': [stock_code, ...],
                'failed': [(stock_code, error), ...],
                'skipped': [stock_code, ...],
                'total': int,
                'updated': int
            }
        """
        from multiprocessing import Pool, cpu_count

        # 自动确定进程数：CPU核心数-2，最少2个，最多8个
        if max_workers is None:
            max_workers = max(2, cpu_count() - 2)

        total = len(stock_data_map)
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'total': total,
            'updated': 0
        }

        # 准备参数（只传递股票代码，让子进程自己加载数据）
        args_list = []
        for stock_code in stock_data_map.keys():
            args_list.append((stock_code, data_path, factor_library, self.base_path, force_full))

        # 使用进程池并行处理
        completed = 0
        with Pool(processes=max_workers) as pool:
            # 使用 imap_unordered 获取实时结果
            for result in pool.imap_unordered(_update_single_stock, args_list):
                stock_code, success, message, updated_count = result
                completed += 1

                # 检查是否被取消（通过回调函数返回值判断）
                if progress_callback:
                    should_stop = progress_callback(completed, total, stock_code, 'success' if success else 'failed')
                    if should_stop:
                        # 终止剩余任务
                        pool.terminate()
                        pool.join()
                        break

                if success:
                    if '无需更新' in message:
                        results['skipped'].append(stock_code)
                    else:
                        results['success'].append(stock_code)
                        results['updated'] += updated_count
                else:
                    results['failed'].append((stock_code, message))

        return results

    def batch_incremental_update_threaded(self,
                                          stock_data_map: dict,
                                          factor_library: str = 'alpha191',
                                          max_workers: int = None,
                                          progress_callback: Callable = None,
                                          stop_event=None,
                                          force_full: bool = False) -> dict:
        """
        批量增量更新（多线程模式）

        适用于I/O密集型场景，线程间共享内存，开销更小

        Args:
            stock_data_map: {stock_code: raw_data_df} 字典
            factor_library: 因子库名称
            max_workers: 并发线程数
            progress_callback: 进度回调函数，接收 (current, total, stock_code, status)，返回True表示停止
            stop_event: 线程事件，用于取消任务
            force_full: 是否强制全量更新

        Returns:
            {
                'success': [stock_code, ...],
                'failed': [(stock_code, error), ...],
                'skipped': [stock_code, ...],
                'total': int,
                'updated': int
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from multiprocessing import cpu_count

        # 自动确定线程数：CPU核心数*2（线程适合I/O密集型），最少2个，最多16个
        if max_workers is None:
            max_workers = max(2, min(cpu_count() * 2, 16))

        total = len(stock_data_map)
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'total': total,
            'updated': 0
        }

        completed = 0

        def process_single_stock(stock_code, raw_data):
            """处理单只股票的辅助函数"""
            try:
                # 获取更新类型
                if force_full:
                    update_type = 'full'
                else:
                    update_type = self.get_cache_update_type(stock_code, raw_data, factor_library)

                if update_type == 'none':
                    return (stock_code, True, '无需更新', 0)
                elif update_type == 'full':
                    # 全量更新
                    self.compute_and_save(stock_code, raw_data, factor_library)
                    return (stock_code, True, '全量更新完成', len(raw_data))
                else:
                    # 增量更新
                    self.incremental_update(stock_code, raw_data, factor_library)
                    return (stock_code, True, f'增量更新完成', 1)
            except Exception as e:
                return (stock_code, False, str(e), 0)

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(process_single_stock, stock_code, raw_data): stock_code
                for stock_code, raw_data in stock_data_map.items()
            }

            # 处理完成的任务
            for future in as_completed(future_to_stock):
                # 检查停止事件
                if stop_event and stop_event.is_set():
                    # 取消剩余任务
                    for f in future_to_stock:
                        f.cancel()
                    break

                stock_code = future_to_stock[future]
                try:
                    stock_code, success, message, updated_count = future.result()
                    completed += 1

                    # 检查是否停止（通过回调返回值）
                    if progress_callback:
                        should_stop = progress_callback(completed, total, stock_code, 'success' if success else 'failed')
                        if should_stop:
                            # 取消剩余任务
                            for f in future_to_stock:
                                f.cancel()
                            break

                    if success:
                        if '无需更新' in message:
                            results['skipped'].append(stock_code)
                        else:
                            results['success'].append(stock_code)
                            results['updated'] += updated_count
                    else:
                        results['failed'].append((stock_code, message))

                except Exception as e:
                    completed += 1
                    results['failed'].append((stock_code, str(e)))
                    if progress_callback:
                        progress_callback(completed, total, stock_code, 'failed')

        return results

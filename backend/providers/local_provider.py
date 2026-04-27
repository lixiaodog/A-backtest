"""
本地数据提供者

从本地 CSV 文件读取股票历史数据
支持自动搜索配置路径下的所有 CSV 文件
"""
import os
import re
from typing import List, Optional, Dict
import pandas as pd

from backend.data_provider import DataProvider


class LocalDataProvider(DataProvider):
    """本地数据提供者
    
    自动搜索配置路径下的所有 CSV 文件，支持多种文件名格式
    """
    
    # 支持的股票代码提取模式
    STOCK_CODE_PATTERNS = [
        r'^(\d{6})',           # 000001, 600000 等6位数字
        r'^[szshbj]{2}(\d{6})',  # sz000001, sh600000 等带前缀
        r'^(\d{6})_',          # 000001_data 等带后缀
    ]
    
    def __init__(self, data_path: str = None, file_pattern: str = None, 
                 silent: bool = False, stock_file_map: Dict[str, str] = None):
        """初始化
        
        Args:
            data_path: 本地数据目录路径，如果为None或空则从配置读取
            file_pattern: 文件名模式（可选，用于过滤）
            silent: 是否静默模式（不输出扫描日志，用于子进程）
            stock_file_map: 预先扫描好的股票文件映射（用于子进程，避免重复扫描）
        """
        if not data_path:
            from backend.config import DataSourceConfig
            config = DataSourceConfig.get_config('local')
            data_path = config.get('data_path', './data/')
        
        self.data_path = data_path
        self.file_pattern = file_pattern
        self._silent = silent
        self._available_stocks: Optional[List[str]] = None
        self._scanned_dirs: set = set()
        
        if stock_file_map:
            self._stock_file_map = stock_file_map
            self._scanned_dirs.add(os.path.normpath(data_path))
        else:
            self._stock_file_map: Dict[str, str] = {}
            self._scan_data_directory()
    
    def _scan_data_directory(self):
        """扫描数据目录，建立股票代码到文件的映射"""
        self._stock_file_map = {}
        self._scan_specific_directory(self.data_path)
    
    def _scan_specific_directory(self, directory: str):
        """扫描指定目录
        
        Args:
            directory: 要扫描的目录路径
        """
        norm_dir = os.path.normpath(directory)
        if norm_dir in self._scanned_dirs:
            return
        
        if not os.path.exists(directory) or not os.path.isdir(directory):
            return
        
        try:
            csv_files = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.csv'):
                        csv_files.append(os.path.join(root, file))
            
            for filepath in csv_files:
                stock_code = self._extract_stock_code_from_filename(filepath)
                if stock_code:
                    if stock_code not in self._stock_file_map:
                        self._stock_file_map[stock_code] = filepath
                    else:
                        if len(filepath) < len(self._stock_file_map[stock_code]):
                            self._stock_file_map[stock_code] = filepath
            
            self._scanned_dirs.add(norm_dir)
            
            if not self._silent:
                print(f"[LocalDataProvider] 扫描 {directory}: 找到 {len(self._stock_file_map)} 只股票")
            
        except Exception as e:
            if not self._silent:
                print(f"[LocalDataProvider] 扫描目录失败: {e}")
    
    def _extract_stock_code_from_filename(self, filepath: str) -> Optional[str]:
        """从文件路径提取股票代码
        
        Args:
            filepath: 文件完整路径
            
        Returns:
            6位股票代码或None
        """
        filename = os.path.basename(filepath)
        name_without_ext = filename.replace('.csv', '')
        
        # 尝试所有模式
        for pattern in self.STOCK_CODE_PATTERNS:
            match = re.match(pattern, name_without_ext, re.IGNORECASE)
            if match:
                code = match.group(1)
                # 验证代码格式
                if len(code) == 6 and code.isdigit():
                    return code
        
        return None
    
    @property
    def name(self) -> str:
        return "local"
    
    def is_available(self) -> bool:
        """检查本地数据路径是否存在"""
        return os.path.exists(self.data_path) and os.path.isdir(self.data_path)
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        if not os.path.exists(self.data_path):
            return f"数据路径不存在: {self.data_path}"
        if not os.path.isdir(self.data_path):
            return f"数据路径不是目录: {self.data_path}"
        if not self._stock_file_map:
            return f"路径下未找到有效的股票数据文件: {self.data_path}"
        return None
    
    def _get_market_path(self, market: str = None, period: str = '1d') -> str:
        """根据市场和周期获取数据路径
        
        支持两种目录结构：
        1. 平铺结构: ./data/000001.csv
        2. 分层结构: ./data/SZ/1d/000001.csv
        
        Args:
            market: 市场代码 (SZ/SH/BJ)
            period: 周期 (1d/1m/1w等)
            
        Returns:
            数据路径
        """
        base_path = self.data_path
        
        # 检查是否存在市场和周期子目录
        if market:
            market_path = os.path.join(base_path, market)
            if os.path.exists(market_path):
                # 检查是否有周期子目录
                period_path = os.path.join(market_path, period)
                if os.path.exists(period_path):
                    return period_path
                return market_path
        
        # 检查是否有周期子目录（在根目录下）
        period_path = os.path.join(base_path, period)
        if os.path.exists(period_path):
            return period_path
        
        return base_path
    
    def get_stock_data(self, stock_code: str, **kwargs) -> Optional[pd.DataFrame]:
        """从本地文件读取股票数据
        
        Args:
            stock_code: 股票代码，如 "000001"
            **kwargs: 可选参数
                - market: 市场代码 (SZ/SH/BJ)
                - period: 周期 (1d/1m等)
                - date: 特定日期，格式 YYYY-MM-DD
                - days: 读取最近 N 天数据
                - start_date: 开始日期
                - end_date: 结束日期
                
        Returns:
            DataFrame 包含股票数据
        """
        if not self.is_available():
            print(f"[LocalDataProvider] 数据路径不可用: {self.data_path}")
            return None
        
        # 根据市场和周期确定路径
        market = kwargs.get('market')
        period = kwargs.get('period', '1d')
        data_path = self._get_market_path(market, period)
        
        code_only = stock_code.split('.')[0] if '.' in stock_code else stock_code
        
        filename = f"{code_only}.csv"
        filepath = os.path.join(data_path, filename)
        
        if not os.path.exists(filepath):
            filepath = self._stock_file_map.get(code_only) or self._stock_file_map.get(stock_code)
            if not filepath:
                self._scan_specific_directory(data_path)
                filepath = self._stock_file_map.get(code_only) or self._stock_file_map.get(stock_code)
                if not filepath:
                    for code, path in self._stock_file_map.items():
                        if code == code_only or code == stock_code:
                            filepath = path
                            break
        
        if not filepath or not os.path.exists(filepath):
            print(f"[LocalDataProvider] 未找到股票 {stock_code} 的数据文件 (market={market}, period={period})")
            return None
        
        try:
            # 读取 CSV
            df = pd.read_csv(filepath)
            
            if df.empty:
                print(f"[LocalDataProvider] {stock_code} 数据为空")
                return None
            
            # 标准化列名
            df = self._standardize_columns(df)
            
            # 确保日期列存在并排序
            if 'date' in df.columns:
                # 尝试不同的日期格式
                try:
                    # 先尝试整数格式 (如 20150105)
                    if df['date'].dtype in ['int64', 'int32', 'float64']:
                        df['date'] = pd.to_datetime(df['date'].astype(int).astype(str), format='%Y%m%d')
                    else:
                        df['date'] = pd.to_datetime(df['date'])
                except:
                    # 如果失败，尝试自动推断
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.sort_values('date')
            
            # 日期范围过滤
            if 'start_date' in kwargs and 'date' in df.columns:
                start_date = pd.to_datetime(kwargs['start_date'])
                df = df[df['date'] >= start_date]
            
            if 'end_date' in kwargs and 'date' in df.columns:
                end_date = pd.to_datetime(kwargs['end_date'])
                df = df[df['date'] <= end_date]
            
            # 过滤特定日期
            if 'date' in kwargs and 'date' in df.columns:
                target_date = pd.to_datetime(kwargs['date'])
                df = df[df['date'] == target_date]
            
            # 取最近 N 天
            if 'days' in kwargs and 'date' in df.columns:
                days = kwargs['days']
                df = df.tail(days)
            
            # 如果有日期列，设为索引
            if 'date' in df.columns:
                df = df.set_index('date')
            
            return df
            
        except Exception as e:
            print(f"[LocalDataProvider] 读取 {stock_code} 数据失败: {e}")
            return None
    
    def get_market_stocks(self, market: str = None, **kwargs) -> List[str]:
        """获取股票列表
        
        Args:
            market: 市场代码（用于过滤，可选）
            **kwargs: 可选参数
                - period: 周期 (1d/1m等)
            
        Returns:
            股票代码列表
        """
        if not self.is_available():
            return []
        
        # 如果已经扫描过，直接使用缓存的结果
        if self._stock_file_map:
            data_path = self._get_market_path(market, kwargs.get('period', '1d'))
            norm_data_path = os.path.normpath(data_path)
            
            stocks = []
            for code, filepath in self._stock_file_map.items():
                norm_filepath = os.path.normpath(filepath)
                if norm_filepath.startswith(norm_data_path):
                    stocks.append(code)
            return sorted(stocks)
        
        # 根据市场和周期确定扫描路径
        period = kwargs.get('period', '1d')
        data_path = self._get_market_path(market, period)
        
        # 扫描该路径下的股票
        self._scan_specific_directory(data_path)
        
        # 规范化路径（处理 Windows/Linux 路径分隔符差异）
        norm_data_path = os.path.normpath(data_path)
        
        # 获取该路径下的所有股票
        stocks = []
        for code, filepath in self._stock_file_map.items():
            # 只选择在当前扫描路径下的股票
            norm_filepath = os.path.normpath(filepath)
            if norm_filepath.startswith(norm_data_path):
                stocks.append(code)
        
        return sorted(stocks)
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        column_mapping = {
            # 日期
            'date': 'date', 'Date': 'date', '日期': 'date',
            'time': 'date', 'Time': 'date', 'trade_date': 'date',
            'stime': 'date', 'Stime': 'date', 'STime': 'date',  # stime 是常见日期列
            
            # 开盘价
            'open': 'open', 'Open': 'open', '开盘': 'open',
            
            # 最高价
            'high': 'high', 'High': 'high', '最高': 'high',
            
            # 最低价
            'low': 'low', 'Low': 'low', '最低': 'low',
            
            # 收盘价
            'close': 'close', 'Close': 'close', '收盘': 'close',
            
            # 成交量
            'volume': 'volume', 'Volume': 'volume', 'vol': 'volume',
            '成交量': 'volume', 'vol_volume': 'volume',
            
            # 成交额
            'amount': 'amount', 'Amount': 'amount', '成交额': 'amount',
            
            # 股票名称
            'name': 'name', 'Name': 'name', '股票名称': 'name',
            'stock_name': 'name'
        }
        
        # 重命名存在的列
        rename_dict = {k: v for k, v in column_mapping.items() 
                      if k in df.columns and k != v}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        return df
    
    def _infer_market(self, stock_code: str) -> str:
        """根据股票代码推断市场"""
        code = str(stock_code)
        
        # 上海市场
        if code.startswith(('60', '68', '69', '5')):
            return 'SH'
        # 北京市场
        elif code.startswith(('8', '4', '9')):
            return 'BJ'
        # 深圳市场 (00, 30, 20)
        else:
            return 'SZ'
    
    def get_available_stocks(self) -> List[str]:
        """获取所有可用的股票代码列表"""
        return self.get_market_stocks()
    
    def get_data_info(self) -> dict:
        """获取数据目录信息"""
        if not self.is_available():
            return {
                'available': False,
                'path': self.data_path,
                'error': self.get_error_message()
            }
        
        stocks = self.get_available_stocks()
        
        # 按市场分组统计
        market_counts = {'SH': 0, 'SZ': 0, 'BJ': 0, 'OTHER': 0}
        for code in stocks:
            market = self._infer_market(code)
            market_counts[market] = market_counts.get(market, 0) + 1
        
        return {
            'available': True,
            'path': self.data_path,
            'total_stocks': len(stocks),
            'market_counts': market_counts,
            'sample_stocks': stocks[:10]  # 只显示前10个
        }
    
    def refresh(self):
        """刷新数据目录扫描"""
        self._scan_data_directory()

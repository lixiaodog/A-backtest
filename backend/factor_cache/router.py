"""
因子存储路由 - 管理按股票分库的数据库路径
"""

import os


def _get_default_cache_path() -> str:
    """获取默认缓存路径（绝对路径）"""
    # 当前文件在 backend/factor_cache/ 下，项目根目录是上两级
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, 'data', 'factor_cache')


class FactorStoreRouter:
    """因子存储路由 - 决定数据存取位置"""
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = _get_default_cache_path()
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def get_db_path(self, stock_code: str) -> str:
        """获取股票对应的DB路径"""
        return os.path.join(self.base_path, f'{stock_code}.db')
    
    def get_all_stock_codes(self) -> list:
        """获取所有已缓存的股票代码"""
        stocks = []
        if os.path.exists(self.base_path):
            for filename in os.listdir(self.base_path):
                if filename.endswith('.db'):
                    stocks.append(filename[:-3])  # 去掉 .db
        return stocks
    
    def get_cache_size(self, stock_code: str = None) -> float:
        """获取缓存大小(MB)"""
        if stock_code:
            db_path = self.get_db_path(stock_code)
            if os.path.exists(db_path):
                return os.path.getsize(db_path) / (1024 * 1024)
            return 0
        
        # 计算总大小
        total_size = 0
        if os.path.exists(self.base_path):
            for filename in os.listdir(self.base_path):
                if filename.endswith('.db'):
                    filepath = os.path.join(self.base_path, filename)
                    total_size += os.path.getsize(filepath)
        
        return total_size / (1024 * 1024)

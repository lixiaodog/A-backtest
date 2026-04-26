"""
数据源配置管理

集中管理各种数据源的连接配置
"""
import os
from typing import Dict, Any, Optional


class DataSourceConfig:
    """数据源配置类
    
    统一管理所有数据源的连接参数
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        'local': {
            'data_path': './data/',  # 本地CSV数据路径
        },
        'sqlite': {
            'db_path': './data/stock_data.db',       # SQLite数据库路径
            'table_name': 'stock_data',               # 数据表名称
            'code_column': 'stock_code',              # 股票代码列名
            'date_column': 'date',                    # 日期列名
        },
        'factor_cache': {
            'cache_path': './data/factor_cache/',     # 因子缓存目录
            'raw_data_path': './data/',               # 原始数据目录
            'factor_library': 'alpha191',             # 默认因子库
        }
    }
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config = cls.DEFAULT_CONFIG.copy()
        return cls._instance
    
    @classmethod
    def get_config(cls, source_type: str) -> Dict[str, Any]:
        """
        获取指定数据源的配置
        
        Args:
            source_type: 数据源类型 ('local', 'sqlite')
            
        Returns:
            配置字典
        """
        instance = cls()
        return instance._config.get(source_type, {})
    
    @classmethod
    def set_config(cls, source_type: str, **kwargs):
        """
        设置数据源配置
        
        Args:
            source_type: 数据源类型
            **kwargs: 配置参数
        """
        instance = cls()
        if source_type not in instance._config:
            instance._config[source_type] = {}
        instance._config[source_type].update(kwargs)
    
    @classmethod
    def get_local_data_path(cls) -> str:
        """获取本地数据路径"""
        return cls.get_config('local').get('data_path', './data/stocks/')
    
    @classmethod
    def get_sqlite_config(cls) -> Dict[str, Any]:
        """获取 SQLite 配置"""
        return cls.get_config('sqlite')
    
    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        instance = cls()
        
        # 本地数据路径
        local_path = os.getenv('LOCAL_DATA_PATH')
        if local_path:
            instance._config['local']['data_path'] = local_path
        
        # SQLite 配置
        sqlite_db = os.getenv('SQLITE_DB_PATH')
        if sqlite_db:
            instance._config['sqlite']['db_path'] = sqlite_db
        
        sqlite_table = os.getenv('SQLITE_TABLE_NAME')
        if sqlite_table:
            instance._config['sqlite']['table_name'] = sqlite_table
    
    @classmethod
    def load_from_file(cls, config_path: str):
        """从配置文件加载"""
        import json
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                instance = cls()
                for source_type, settings in config.items():
                    if source_type in instance._config:
                        instance._config[source_type].update(settings)
    
    @classmethod
    def save_to_file(cls, config_path: str):
        """保存配置到文件"""
        import json
        instance = cls()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(instance._config, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def list_available_sources(cls) -> list:
        """列出所有可用的数据源类型"""
        return ['akshare', 'local', 'sqlite']


# 便捷函数
def get_data_source_config(source_type: str) -> Dict[str, Any]:
    """获取数据源配置的便捷函数"""
    return DataSourceConfig.get_config(source_type)


def init_config():
    """初始化配置，从环境变量和配置文件加载"""
    DataSourceConfig.load_from_env()
    
    # 尝试加载配置文件
    config_path = os.getenv('DATA_SOURCE_CONFIG', './config/data_sources.json')
    if os.path.exists(config_path):
        DataSourceConfig.load_from_file(config_path)


# 模块加载时自动初始化
init_config()

"""
数据提供者模块

提供多种数据源的统一访问接口
"""
from backend.data_provider import DataProvider


class ProviderFactory:
    """Provider 工厂类
    
    用于创建和管理各种数据提供者实例
    """
    
    _providers = {}
    _instances = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """注册新的 Provider 类型
        
        Args:
            name: Provider 名称
            provider_class: Provider 类（必须继承 DataProvider）
        """
        if not issubclass(provider_class, DataProvider):
            raise ValueError(f"Provider 类必须继承 DataProvider: {provider_class}")
        cls._providers[name] = provider_class
    
    @classmethod
    def create_provider(cls, provider_type: str, **kwargs) -> DataProvider:
        """创建 Provider 实例
        
        Args:
            provider_type: Provider 类型名称，如 'akshare', 'local'
            **kwargs: 传递给 Provider 构造函数的参数
            
        Returns:
            DataProvider 实例
            
        Raises:
            ValueError: 当 provider_type 不存在时
        """
        # 延迟导入，避免循环依赖
        if not cls._providers:
            cls._register_default_providers()
        
        if provider_type not in cls._providers:
            raise ValueError(f"未知的 Provider 类型: {provider_type}。"
                           f"可用类型: {list(cls._providers.keys())}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(**kwargs)
    
    @classmethod
    def get_provider(cls, provider_type: str, **kwargs) -> DataProvider:
        """获取 Provider 实例（单例模式）
        
        相同类型的 Provider 会复用实例
        
        Args:
            provider_type: Provider 类型名称
            **kwargs: 传递给 Provider 构造函数的参数
            
        Returns:
            DataProvider 实例
        """
        # 根据参数创建唯一标识
        cache_key = f"{provider_type}:{hash(str(sorted(kwargs.items())))}"
        
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls.create_provider(provider_type, **kwargs)
        
        return cls._instances[cache_key]
    
    @classmethod
    def _register_default_providers(cls):
        """注册默认的 Provider 类型"""
        try:
            from backend.providers.akshare_provider import AKShareProvider
            cls.register_provider('akshare', AKShareProvider)
        except ImportError as e:
            print(f"[ProviderFactory] AKShareProvider 注册失败: {e}")
        
        try:
            from backend.providers.local_provider import LocalDataProvider
            cls.register_provider('local', LocalDataProvider)
        except ImportError as e:
            print(f"[ProviderFactory] LocalDataProvider 注册失败: {e}")
        
        try:
            from backend.providers.sqlite_provider import SQLiteProvider
            cls.register_provider('sqlite', SQLiteProvider)
        except ImportError as e:
            print(f"[ProviderFactory] SQLiteProvider 注册失败: {e}")
        
        try:
            from backend.providers.factor_cache_provider import FactorCacheProvider
            cls.register_provider('factor_cache', FactorCacheProvider)
        except ImportError as e:
            print(f"[ProviderFactory] FactorCacheProvider 注册失败: {e}")
    
    @classmethod
    def list_providers(cls) -> list:
        """列出所有可用的 Provider 类型"""
        if not cls._providers:
            cls._register_default_providers()
        return list(cls._providers.keys())
    
    @classmethod
    def clear_cache(cls):
        """清除 Provider 实例缓存"""
        cls._instances.clear()


# 便捷函数
def get_provider(provider_type: str, **kwargs) -> DataProvider:
    """获取 Provider 实例的便捷函数"""
    return ProviderFactory.get_provider(provider_type, **kwargs)


def create_provider(provider_type: str, **kwargs) -> DataProvider:
    """创建 Provider 实例的便捷函数"""
    return ProviderFactory.create_provider(provider_type, **kwargs)

import inspect
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Type
from .builtins.base import BaseFilter


class FilterRegistry:
    _filters: Dict[str, BaseFilter] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, filter_instance: BaseFilter):
        """注册条件"""
        cls._filters[filter_instance.filter_id] = filter_instance
    
    @classmethod
    def unregister(cls, filter_id: str):
        """注销条件"""
        if filter_id in cls._filters:
            del cls._filters[filter_id]
    
    @classmethod
    def get_filter(cls, filter_id: str) -> Optional[BaseFilter]:
        """获取条件"""
        return cls._filters.get(filter_id)
    
    @classmethod
    def get_all_filters(cls) -> Dict[str, BaseFilter]:
        """获取所有条件"""
        return cls._filters.copy()
    
    @classmethod
    def get_filters_by_category(cls, category: str) -> List[BaseFilter]:
        """按分类获取条件"""
        return [f for f in cls._filters.values() if f.category == category]
    
    @classmethod
    def get_filters_by_stage(cls, stage: str) -> List[BaseFilter]:
        """按阶段获取条件"""
        return [f for f in cls._filters.values() if f.filter_stage == stage]
    
    @classmethod
    def auto_discover(cls, force: bool = False):
        """自动发现并注册所有条件
        
        Args:
            force: 是否强制重新扫描，即使已经初始化过
        """
        if cls._initialized and not force:
            return
        
        if force:
            cls._filters = {}
        
        builtins_dir = Path(__file__).parent / 'builtins'
        if not builtins_dir.exists():
            return
        
        for file in builtins_dir.glob('*.py'):
            if file.name.startswith('_'):
                continue
            
            module_name = file.stem
            try:
                module = import_module(f'backend.stock_filters.builtins.{module_name}')
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BaseFilter) and 
                        obj != BaseFilter):
                        try:
                            instance = obj()
                            cls.register(instance)
                        except Exception as e:
                            print(f"[FilterRegistry] 注册条件 {name} 失败: {e}")
            except Exception as e:
                print(f"[FilterRegistry] 加载模块 {module_name} 失败: {e}")
        
        cls._initialized = True
        print(f"[FilterRegistry] 已注册 {len(cls._filters)} 个条件: {list(cls._filters.keys())}")
    
    @classmethod
    def list_filters(cls) -> List[Dict]:
        """列出所有条件信息"""
        return [f.to_dict() for f in cls._filters.values()]

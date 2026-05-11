import json
import os
from typing import Optional
from .models import FilterConfig


class FilterStorage:
    DEFAULT_STORAGE_PATH = 'data/stock_filters.json'
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
    
    def load(self) -> FilterConfig:
        if not os.path.exists(self.storage_path):
            return FilterConfig()
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return FilterConfig.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[FilterStorage] 加载配置失败: {e}")
            return FilterConfig()
    
    def save(self, config: FilterConfig) -> bool:
        try:
            self._ensure_storage_dir()
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"[FilterStorage] 保存配置失败: {e}")
            return False
    
    def export_to_file(self, config: FilterConfig, file_path: str) -> bool:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"[FilterStorage] 导出配置失败: {e}")
            return False
    
    def import_from_file(self, file_path: str) -> Optional[FilterConfig]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return FilterConfig.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[FilterStorage] 导入配置失败: {e}")
            return None

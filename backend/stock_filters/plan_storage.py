"""
选股计划存储模块
"""
import json
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


@dataclass
class SelectionPlan:
    """选股计划"""
    id: str
    name: str
    description: str = ""
    filters: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'filters': self.filters,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SelectionPlan':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            filters=data.get('filters', []),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
        )


class SelectionPlanStorage:
    """选股计划存储"""
    
    DEFAULT_STORAGE_PATH = os.path.join(DATA_DIR, 'selection_plans.json')
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
    
    def load_all(self) -> List[SelectionPlan]:
        """加载所有选股计划"""
        if not os.path.exists(self.storage_path):
            return []
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [SelectionPlan.from_dict(p) for p in data.get('plans', [])]
        except (json.JSONDecodeError, IOError) as e:
            print(f"[SelectionPlanStorage] 加载选股计划失败: {e}")
            return []
    
    def save_all(self, plans: List[SelectionPlan]) -> bool:
        """保存所有选股计划"""
        try:
            self._ensure_storage_dir()
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'plans': [p.to_dict() for p in plans]
                }, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"[SelectionPlanStorage] 保存选股计划失败: {e}")
            return False
    
    def add_plan(self, plan: SelectionPlan) -> bool:
        """添加选股计划"""
        plans = self.load_all()
        plans.append(plan)
        return self.save_all(plans)
    
    def update_plan(self, plan_id: str, updates: Dict[str, Any]) -> bool:
        """更新选股计划"""
        plans = self.load_all()
        for i, plan in enumerate(plans):
            if plan.id == plan_id:
                for key, value in updates.items():
                    if hasattr(plan, key):
                        setattr(plan, key, value)
                plan.updated_at = datetime.now().isoformat()
                plans[i] = plan
                return self.save_all(plans)
        return False
    
    def delete_plan(self, plan_id: str) -> bool:
        """删除选股计划"""
        plans = self.load_all()
        plans = [p for p in plans if p.id != plan_id]
        return self.save_all(plans)
    
    def get_plan(self, plan_id: str) -> Optional[SelectionPlan]:
        """获取选股计划"""
        plans = self.load_all()
        for plan in plans:
            if plan.id == plan_id:
                return plan
        return None


_selection_plan_storage: Optional[SelectionPlanStorage] = None


def get_selection_plan_storage() -> SelectionPlanStorage:
    """获取全局选股计划存储实例"""
    global _selection_plan_storage
    if _selection_plan_storage is None:
        _selection_plan_storage = SelectionPlanStorage()
    return _selection_plan_storage

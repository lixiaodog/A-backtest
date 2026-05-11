from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


@dataclass
class StockFilter:
    id: str
    name: str
    description: str
    category: str  # technical, fundamental, custom
    filter_stage: str  # pre_filter, post_filter
    condition_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
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
            'category': self.category,
            'filter_stage': self.filter_stage,
            'condition_type': self.condition_type,
            'parameters': self.parameters,
            'enabled': self.enabled,
            'priority': self.priority,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockFilter':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            category=data.get('category', 'technical'),
            filter_stage=data.get('filter_stage', 'post_filter'),
            condition_type=data.get('condition_type', ''),
            parameters=data.get('parameters', {}),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 0),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
        )


@dataclass
class FilterConfig:
    filters: List[StockFilter] = field(default_factory=list)
    
    def add_filter(self, stock_filter: StockFilter):
        self.filters.append(stock_filter)
    
    def remove_filter(self, filter_id: str):
        self.filters = [f for f in self.filters if f.id != filter_id]
    
    def get_filter(self, filter_id: str) -> Optional[StockFilter]:
        for f in self.filters:
            if f.id == filter_id:
                return f
        return None
    
    def get_enabled_filters(self) -> List[StockFilter]:
        return [f for f in self.filters if f.enabled]
    
    def get_pre_filters(self) -> List[StockFilter]:
        return [f for f in self.filters if f.enabled and f.filter_stage == 'pre_filter']
    
    def get_post_filters(self) -> List[StockFilter]:
        return [f for f in self.filters if f.enabled and f.filter_stage == 'post_filter']
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'filters': [f.to_dict() for f in self.filters]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterConfig':
        config = cls()
        for f_data in data.get('filters', []):
            config.add_filter(StockFilter.from_dict(f_data))
        return config

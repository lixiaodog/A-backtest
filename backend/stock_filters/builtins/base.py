from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseFilter(ABC):
    """条件基类 - 所有条件必须继承此类"""
    
    filter_id: str = ''
    name: str = ''
    description: str = ''
    category: str = 'technical'
    filter_stage: str = 'post_filter'
    parameters_schema: Dict[str, Any] = {}
    
    @abstractmethod
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        """评估股票是否满足条件
        
        Args:
            stock_code: 股票代码
            context: 上下文数据，包含：
                - stock_data: 股票行情数据
                - prediction_result: 模型预测结果（仅post_filter）
                - parameters: 条件参数
                
        Returns:
            bool: 是否满足条件
        """
        pass
    
    def validate_parameters(self, parameters: Dict) -> bool:
        """验证参数是否合法"""
        if not self.parameters_schema:
            return True
        
        properties = self.parameters_schema.get('properties', {})
        for key, schema in properties.items():
            if schema.get('required', False) and key not in parameters:
                return False
        
        return True
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """获取默认参数"""
        if not self.parameters_schema:
            return {}
        
        defaults = {}
        properties = self.parameters_schema.get('properties', {})
        for key, schema in properties.items():
            if 'default' in schema:
                defaults[key] = schema['default']
        
        return defaults
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'filter_id': self.filter_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'filter_stage': self.filter_stage,
            'parameters_schema': self.parameters_schema
        }

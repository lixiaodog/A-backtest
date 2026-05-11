from typing import Dict
from .base import BaseFilter


class MarketCapFilter(BaseFilter):
    filter_id = 'market_cap_filter'
    name = '市值筛选'
    description = '按市值范围筛选股票'
    category = 'fundamental'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'cap_type': {
                'type': 'string',
                'title': '市值类型',
                'description': 'total=总市值, circulating=流通市值',
                'enum': ['total', 'circulating'],
                'default': 'total'
            },
            'min_cap': {
                'type': 'number',
                'default': 0,
                'title': '最小市值(亿元)',
                'minimum': 0
            },
            'max_cap': {
                'type': 'number',
                'default': 10000,
                'title': '最大市值(亿元)',
                'minimum': 0
            }
        }
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        pre_close = context.get('pre_close')
        total_capital = context.get('total_capital')
        circulating_capital = context.get('circulating_capital')
        
        if pre_close is None:
            return True
        
        parameters = context.get('parameters', {})
        cap_type = parameters.get('cap_type', 'total')
        min_cap = parameters.get('min_cap', 0)
        max_cap = parameters.get('max_cap', 10000)
        
        try:
            if cap_type == 'total':
                if total_capital is None:
                    return True
                market_cap = pre_close * total_capital
            else:
                if circulating_capital is None:
                    return True
                market_cap = pre_close * circulating_capital
            
            cap_in_yi = market_cap / 100000000
            
            return min_cap <= cap_in_yi <= max_cap
        except Exception as e:
            print(f"[MarketCapFilter] 评估 {stock_code} 失败: {e}")
            return True

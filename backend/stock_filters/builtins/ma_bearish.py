from typing import Dict
from .base import BaseFilter


class MABearishFilter(BaseFilter):
    filter_id = 'ma_bearish'
    name = '均线空头排列'
    description = 'MA5 < MA10 < MA20 < MA60'
    category = 'technical'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'ma_periods': {
                'type': 'array',
                'items': {'type': 'integer'},
                'default': [5, 10, 20, 60],
                'title': '均线周期'
            }
        }
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        ma_periods = parameters.get('ma_periods', [5, 10, 20, 60])
        
        try:
            close = stock_data['close']
            if len(close) < max(ma_periods):
                return False
            
            mas = [close.rolling(p).mean().iloc[-1] for p in ma_periods]
            
            return all(mas[i] < mas[i+1] for i in range(len(mas)-1))
        except Exception as e:
            print(f"[MABearishFilter] 评估 {stock_code} 失败: {e}")
            return True

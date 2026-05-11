from typing import Dict
from .base import BaseFilter


class RSIFilter(BaseFilter):
    filter_id = 'rsi_filter'
    name = 'RSI条件'
    description = 'RSI指标筛选'
    category = 'technical'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'rsi_period': {
                'type': 'integer',
                'default': 14,
                'title': 'RSI周期',
                'minimum': 5,
                'maximum': 30
            },
            'condition': {
                'type': 'string',
                'default': 'oversold',
                'title': '条件类型',
                'enum': ['oversold', 'overbought', 'range']
            },
            'lower_threshold': {
                'type': 'number',
                'default': 30,
                'title': '下限阈值',
                'minimum': 0,
                'maximum': 50
            },
            'upper_threshold': {
                'type': 'number',
                'default': 70,
                'title': '上限阈值',
                'minimum': 50,
                'maximum': 100
            }
        }
    }
    
    def calculate_rsi(self, close, period):
        period = int(period)  # 确保period是整数
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        rsi_period = int(parameters.get('rsi_period', 14))
        condition = parameters.get('condition', 'oversold')
        lower_threshold = parameters.get('lower_threshold', 30)
        upper_threshold = parameters.get('upper_threshold', 70)
        
        try:
            close = stock_data['close']
            if len(close) < rsi_period + 1:
                return False
            
            rsi = self.calculate_rsi(close, rsi_period)
            current_rsi = rsi.iloc[-1]
            
            if condition == 'oversold':
                return current_rsi < lower_threshold
            elif condition == 'overbought':
                return current_rsi > upper_threshold
            elif condition == 'range':
                return lower_threshold <= current_rsi <= upper_threshold
            
            return True
        except Exception as e:
            print(f"[RSIFilter] 评估 {stock_code} 失败: {e}")
            return True

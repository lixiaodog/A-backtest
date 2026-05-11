from typing import Dict
from .base import BaseFilter


class MACDFilter(BaseFilter):
    filter_id = 'macd_filter'
    name = 'MACD金叉'
    description = 'MACD快线上穿慢线'
    category = 'technical'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'fast_period': {
                'type': 'integer',
                'default': 12,
                'title': '快线周期',
                'minimum': 5,
                'maximum': 30
            },
            'slow_period': {
                'type': 'integer',
                'default': 26,
                'title': '慢线周期',
                'minimum': 10,
                'maximum': 60
            },
            'signal_period': {
                'type': 'integer',
                'default': 9,
                'title': '信号线周期',
                'minimum': 5,
                'maximum': 20
            },
            'signal_type': {
                'type': 'string',
                'default': 'golden_cross',
                'title': '信号类型',
                'enum': ['golden_cross', 'death_cross', 'above_zero', 'below_zero']
            }
        }
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        fast_period = parameters.get('fast_period', 12)
        slow_period = parameters.get('slow_period', 26)
        signal_period = parameters.get('signal_period', 9)
        signal_type = parameters.get('signal_type', 'golden_cross')
        
        try:
            close = stock_data['close']
            if len(close) < slow_period + signal_period + 1:
                return False
            
            ema_fast = close.ewm(span=fast_period, adjust=False).mean()
            ema_slow = close.ewm(span=slow_period, adjust=False).mean()
            dif = ema_fast - ema_slow
            dea = dif.ewm(span=signal_period, adjust=False).mean()
            macd = (dif - dea) * 2
            
            if signal_type == 'golden_cross':
                return dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]
            elif signal_type == 'death_cross':
                return dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]
            elif signal_type == 'above_zero':
                return macd.iloc[-1] > 0
            elif signal_type == 'below_zero':
                return macd.iloc[-1] < 0
            
            return True
        except Exception as e:
            print(f"[MACDFilter] 评估 {stock_code} 失败: {e}")
            return True

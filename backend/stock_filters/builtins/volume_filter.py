from typing import Dict
from .base import BaseFilter


class VolumeFilter(BaseFilter):
    filter_id = 'volume_filter'
    name = '成交量放大'
    description = '成交量大于N日均量的M倍'
    category = 'technical'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'volume_days': {
                'type': 'integer',
                'default': 5,
                'title': '均量天数',
                'minimum': 1,
                'maximum': 60
            },
            'volume_multiple': {
                'type': 'number',
                'default': 1.5,
                'title': '放量倍数',
                'minimum': 1.0,
                'maximum': 10.0
            }
        }
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        volume_days = parameters.get('volume_days', 5)
        volume_multiple = parameters.get('volume_multiple', 1.5)
        
        try:
            volume = stock_data['volume']
            if len(volume) < volume_days + 1:
                return False
            
            current_volume = volume.iloc[-1]
            avg_volume = volume.iloc[-(volume_days+1):-1].mean()
            
            if avg_volume == 0:
                return False
            
            return current_volume >= avg_volume * volume_multiple
        except Exception as e:
            print(f"[VolumeFilter] 评估 {stock_code} 失败: {e}")
            return True

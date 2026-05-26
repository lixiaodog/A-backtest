"""
连续创新高/新低筛选器
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class ConsecutiveNewHighLowFilter(BaseFilter):
    """连续创新高/新低筛选器
    
    筛选连续N天每天创新高或创新低的股票
    - 创新高：每天的最高价都比前一天的最高价高
    - 创新低：每天的最低价都比前一天的最低价低
    """
    
    filter_id = 'consecutive_new_high_low'
    name = "连续创新高/新低"
    description = "筛选连续N天每天创新高或创新低的股票"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "consecutive_days": {
                "type": "integer",
                "title": "连续天数",
                "description": "连续创新高/新低的天数",
                "default": 3,
                "minimum": 2,
                "maximum": 10
            },
            "direction": {
                "type": "string",
                "title": "方向",
                "description": "创新高或创新低",
                "default": "new_high",
                "enum": ["new_high", "new_low"]
            },
            "offset_days": {
                "type": "integer",
                "title": "偏移天数",
                "description": "从哪天开始算，0表示当天，-1表示前一天，以此类推",
                "default": 0,
                "minimum": -10,
                "maximum": 0
            }
        },
        "required": ["consecutive_days", "direction"]
    }
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        """评估股票是否满足条件
        
        Args:
            stock_code: 股票代码
            context: 上下文信息，包含stock_data等
            
        Returns:
            是否满足筛选条件
        """
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        consecutive_days = int(parameters.get('consecutive_days', 3))
        direction = parameters.get('direction', 'new_high')
        offset_days = int(parameters.get('offset_days', 0))
        predict_date = context.get('predict_date')
        
        try:
            if len(stock_data) < consecutive_days + 1:
                return False
            
            high = stock_data['high'].values
            low = stock_data['low'].values
            
            idx = None
            if predict_date:
                try:
                    import pandas as pd
                    predict_date_dt = pd.to_datetime(predict_date)
                    if predict_date_dt in stock_data.index:
                        idx = stock_data.index.get_loc(predict_date_dt)
                except:
                    pass
            
            if idx is None:
                idx = len(stock_data) - 1
            
            idx = idx + offset_days
            
            if idx < consecutive_days:
                return False
            
            if direction == 'new_high':
                for i in range(consecutive_days):
                    current_idx = idx - i
                    prev_idx = current_idx - 1
                    
                    if prev_idx < 0:
                        return False
                    
                    if high[current_idx] <= high[prev_idx]:
                        return False
                
                return True
            
            elif direction == 'new_low':
                for i in range(consecutive_days):
                    current_idx = idx - i
                    prev_idx = current_idx - 1
                    
                    if prev_idx < 0:
                        return False
                    
                    if low[current_idx] >= low[prev_idx]:
                        return False
                
                return True
            
            return False
                
        except Exception as e:
            print(f"[ConsecutiveNewHighLowFilter] 评估 {stock_code} 失败: {e}")
            return True

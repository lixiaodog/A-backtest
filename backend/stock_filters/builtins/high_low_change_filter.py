"""
几日内涨跌幅筛选器（基于最高价和最低价）
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class HighLowChangeFilter(BaseFilter):
    """几日内涨跌幅筛选器
    
    基于最高价和最低价计算N天内的涨跌幅（从远到近）
    - 涨幅：(期间结束最高价 - 期间起始最低价) / 期间起始最低价 * 100
    - 跌幅：(期间起始最高价 - 期间结束最低价) / 期间起始最高价 * 100
    """
    
    filter_id = 'high_low_change'
    name = "几日涨跌幅"
    description = "基于最高价和最低价计算N天内的涨跌幅"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "title": "天数",
                "description": "计算涨跌幅的天数",
                "default": 5,
                "minimum": 1,
                "maximum": 30
            },
            "direction": {
                "type": "string",
                "title": "方向",
                "description": "涨幅或跌幅",
                "default": "rise",
                "enum": ["rise", "fall"]
            },
            "min_change": {
                "type": "number",
                "title": "最小涨跌幅(%)",
                "description": "最小涨跌幅百分比",
                "default": 5.0,
                "minimum": 0,
                "maximum": 50
            },
            "max_change": {
                "type": "number",
                "title": "最大涨跌幅(%)",
                "description": "最大涨跌幅百分比，0表示不限制",
                "default": 0,
                "minimum": 0,
                "maximum": 50
            },
            "offset_days": {
                "type": "integer",
                "title": "偏移天数",
                "description": "从哪天开始算，0表示当天，-1表示前一天，以此类推",
                "default": 0,
                "minimum": -30,
                "maximum": 0
            }
        },
        "required": ["days", "direction", "min_change"]
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
        days = int(parameters.get('days', 5))
        direction = parameters.get('direction', 'rise')
        min_change = float(parameters.get('min_change', 5.0))
        max_change = float(parameters.get('max_change', 0))
        offset_days = int(parameters.get('offset_days', 0))
        predict_date = context.get('predict_date')
        
        try:
            if len(stock_data) < days:
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
            
            end_idx = idx + offset_days
            start_idx = end_idx - days + 1
            
            if start_idx < 0:
                return False
            
            start_high = high[start_idx]
            start_low = low[start_idx]
            end_high = high[end_idx]
            end_low = low[end_idx]
            
            if direction == 'rise':
                if start_low <= 0:
                    return False
                change_percent = (end_high - start_low) / start_low * 100
                
                if change_percent < min_change:
                    return False
                
                if max_change > 0 and change_percent > max_change:
                    return False
                
                return True
            
            elif direction == 'fall':
                if start_high <= 0:
                    return False
                change_percent = (start_high - end_low) / start_high * 100
                
                if change_percent < min_change:
                    return False
                
                if max_change > 0 and change_percent > max_change:
                    return False
                
                return True
            
            return False
                
        except Exception as e:
            print(f"[HighLowChangeFilter] 评估 {stock_code} 失败: {e}")
            return True

"""
当日涨幅筛选器
"""
from typing import Dict
from .base import BaseFilter


class DailyChangeFilter(BaseFilter):
    """当日涨幅筛选器
    
    筛选当日涨幅在指定范围内的股票
    """
    
    filter_id = 'daily_change'
    name = "当日涨幅"
    description = "筛选当日涨幅在指定范围内的股票"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "min_change": {
                "type": "number",
                "title": "最小涨幅(%)",
                "description": "最小涨幅百分比，如-10表示跌幅不超过10%",
                "default": -10,
                "minimum": -30,
                "maximum": 30
            },
            "max_change": {
                "type": "number",
                "title": "最大涨幅(%)",
                "description": "最大涨幅百分比，如10表示涨幅不超过10%",
                "default": 10,
                "minimum": -30,
                "maximum": 30
            }
        },
        "required": ["min_change", "max_change"]
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
        min_change = parameters.get('min_change', -10)
        max_change = parameters.get('max_change', 10)
        
        try:
            if len(stock_data) < 2:
                return False
            
            latest = stock_data.iloc[-1]
            prev = stock_data.iloc[-2]
            
            close = latest.get('close')
            prev_close = prev.get('close')
            
            if close is None or prev_close is None or prev_close == 0:
                return True
            
            change_pct = (close - prev_close) / prev_close * 100
            
            return min_change <= change_pct <= max_change
                
        except Exception as e:
            print(f"[DailyChangeFilter] 评估 {stock_code} 失败: {e}")
            return True

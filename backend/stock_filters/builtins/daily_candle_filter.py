"""
当日K线形态筛选器
"""
from typing import Dict
from .base import BaseFilter


class DailyCandleFilter(BaseFilter):
    """当日K线形态筛选器
    
    筛选当日收阳或收阴的股票
    """
    
    filter_id = 'daily_candle'
    name = "当日K线形态"
    description = "筛选当日收阳或收阴的股票"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "candle_type": {
                "type": "string",
                "title": "K线形态",
                "description": "选择当日K线形态",
                "enum": ["收阳", "收阴", "平盘"],
                "default": "收阳"
            }
        },
        "required": ["candle_type"]
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
        candle_type = parameters.get('candle_type', '收阳')
        
        try:
            if len(stock_data) == 0:
                return False
            
            latest = stock_data.iloc[-1]
            close = latest.get('close')
            open_price = latest.get('open')
            
            if close is None or open_price is None:
                return True
            
            if candle_type == "收阳":
                return close > open_price
            elif candle_type == "收阴":
                return close < open_price
            elif candle_type == "平盘":
                return abs(close - open_price) < 0.01
            else:
                return True
                
        except Exception as e:
            print(f"[DailyCandleFilter] 评估 {stock_code} 失败: {e}")
            return True

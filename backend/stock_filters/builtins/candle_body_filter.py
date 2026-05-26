"""
K线实体筛选器
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class CandleBodyFilter(BaseFilter):
    """K线实体筛选器
    
    筛选K线实体占整个K线范围一定比例以上的股票
    """
    
    filter_id = 'candle_body'
    name = "K线实体筛选"
    description = "筛选K线实体占整个K线范围一定比例以上的股票"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "min_body_ratio": {
                "type": "number",
                "title": "最小实体比例",
                "description": "K线实体占整个K线的最小比例，0.75表示4分之3",
                "default": 0.75,
                "minimum": 0,
                "maximum": 1
            },
            "candle_type": {
                "type": "string",
                "title": "K线类型",
                "description": "选择阳线、阴线或不限制",
                "enum": ["不限", "阳线", "阴线"],
                "default": "不限"
            }
        },
        "required": ["min_body_ratio"]
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
        min_body_ratio = parameters.get('min_body_ratio', 0.75)
        candle_type = parameters.get('candle_type', '不限')
        predict_date = context.get('predict_date')
        
        try:
            if len(stock_data) < 1:
                return False
            
            # 根据预测日期决定使用哪个BAR
            idx = None
            if predict_date:
                # 如果有预测日期，查找对应的BAR
                try:
                    import pandas as pd
                    predict_date_dt = pd.to_datetime(predict_date)
                    if predict_date_dt in stock_data.index:
                        idx = stock_data.index.get_loc(predict_date_dt)
                except:
                    pass
            
            # 如果没有找到预测日期对应的BAR，使用倒数第二个BAR
            if idx is None:
                idx = len(stock_data) - 2
            
            if idx < 0:
                idx = 0
            
            latest = stock_data.iloc[idx]
            
            open_price = latest.get('open')
            close = latest.get('close')
            high = latest.get('high')
            low = latest.get('low')
            
            if any(v is None or np.isnan(v) for v in [open_price, close, high, low]):
                return True
            
            # 计算实体和整个K线范围
            body = abs(close - open_price)
            total_range = high - low
            
            if total_range == 0:
                return False
            
            body_ratio = body / total_range
            
            # 检查K线类型
            if candle_type == "阳线" and close <= open_price:
                return False
            elif candle_type == "阴线" and close >= open_price:
                return False
            
            return body_ratio >= min_body_ratio
                
        except Exception as e:
            print(f"[CandleBodyFilter] 评估 {stock_code} 失败: {e}")
            return True

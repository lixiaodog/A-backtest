"""
均线位置筛选器
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class MAAboveFilter(BaseFilter):
    """均线位置筛选器
    
    筛选连续多少天在某均线之上或之下的股票
    - above: 最低价在均线之上，且距离均线不小于指定比例
    - below: 最高价在均线之下，且距离均线不小于指定比例
    """
    
    filter_id = 'ma_above'
    name = "均线位置"
    description = "筛选连续多少天在某均线之上或之下的股票"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "ma_period": {
                "type": "integer",
                "title": "MA周期",
                "default": 20,
                "minimum": 1,
                "maximum": 250
            },
            "consecutive_days": {
                "type": "integer",
                "title": "连续天数",
                "description": "连续多少天在均线之上/下",
                "default": 5,
                "minimum": 1,
                "maximum": 100
            },
            "direction": {
                "type": "string",
                "title": "方向",
                "description": "均线之上或均线之下",
                "default": "above",
                "enum": ["above", "below"]
            },
            "min_distance": {
                "type": "number",
                "title": "最小距离比例",
                "description": "价格到均线的最小距离比例，0表示刚好在均线上，0.01表示距离1%",
                "default": 0,
                "minimum": 0,
                "maximum": 0.5
            },
            "start_offset": {
                "type": "integer",
                "title": "起始日期偏移",
                "description": "0表示从当日开始，-1表示从前一天开始，以此类推",
                "default": 0,
                "minimum": -100,
                "maximum": 0
            }
        },
        "required": ["ma_period", "consecutive_days", "direction"]
    }
    
    def _calc_ma(self, data, period):
        """计算简单移动平均"""
        period = int(period)
        n = len(data)
        if n < period:
            return np.full(n, np.nan)
        result = np.full(n, np.nan)
        for i in range(period - 1, n):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result
    
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
        ma_period = int(parameters.get('ma_period', 20))
        consecutive_days = int(parameters.get('consecutive_days', 5))
        direction = parameters.get('direction', 'above')
        min_distance = float(parameters.get('min_distance', 0))
        start_offset = int(parameters.get('start_offset', 0))
        predict_date = context.get('predict_date')
        
        try:
            if len(stock_data) < ma_period + consecutive_days:
                return False
            
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
            
            idx += start_offset
            
            if idx < ma_period + consecutive_days - 1 or idx >= len(stock_data):
                return False
            
            close = stock_data['close'].values
            low = stock_data['low'].values
            high = stock_data['high'].values
            
            ma = self._calc_ma(close, ma_period)
            
            for i in range(consecutive_days):
                check_idx = idx - i
                if check_idx < 0:
                    return False
                
                if np.isnan(ma[check_idx]):
                    return False
                
                current_ma = ma[check_idx]
                
                if direction == 'above':
                    if low[check_idx] <= current_ma:
                        return False
                    
                    if min_distance > 0:
                        distance_ratio = (low[check_idx] - current_ma) / current_ma
                        if distance_ratio < min_distance:
                            return False
                else:
                    if high[check_idx] >= current_ma:
                        return False
                    
                    if min_distance > 0:
                        distance_ratio = (current_ma - high[check_idx]) / current_ma
                        if distance_ratio < min_distance:
                            return False
            
            return True
                
        except Exception as e:
            print(f"[MAAboveFilter] 评估 {stock_code} 失败: {e}")
            return True

"""
MA20支撑筛选器
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class MA20SupportFilter(BaseFilter):
    """MA20支撑筛选器
    
    筛选当日价格触及MA20，并收出长下影，并且收阳的股票
    """
    
    filter_id = 'ma20_support'
    name = "MA20支撑"
    description = "筛选当日价格触及MA20，并收出长下影，并且收阳的股票"
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
            "min_lower_shadow_ratio": {
                "type": "number",
                "title": "最小下影线比例",
                "description": "下影线占整个K线的最小比例，0.5表示下影线占K线的一半",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1
            },
            "touch_threshold": {
                "type": "number",
                "title": "触及阈值(%)",
                "description": "最低价跌破MA的最大幅度百分比，1表示最低价最多比MA低1%",
                "default": 1.0,
                "minimum": 0,
                "maximum": 5
            }
        },
        "required": ["ma_period"]
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
        min_lower_shadow_ratio = parameters.get('min_lower_shadow_ratio', 0.5)
        touch_threshold = parameters.get('touch_threshold', 1.0)
        predict_date = context.get('predict_date')
        
        try:
            if len(stock_data) < ma_period + 1:
                return False
            
            # 根据预测日期决定使用哪个BAR
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
                idx = len(stock_data) - 2
            
            if idx < ma_period:
                return False
            
            close = stock_data['close'].values
            open_price = stock_data['open'].values
            high = stock_data['high'].values
            low = stock_data['low'].values
            
            # 计算MA
            ma = self._calc_ma(close, ma_period)
            
            if np.isnan(ma[idx]):
                return False
            
            # 获取当日的数据
            today_close = close[idx]
            today_open = open_price[idx]
            today_high = high[idx]
            today_low = low[idx]
            today_ma = ma[idx]
            
            # 条件1：收阳（收盘价 > 开盘价）
            if today_close <= today_open:
                return False
            
            # 条件2：触及MA20（最低价 < MA20，收盘价 > MA20）
            if today_low >= today_ma:
                # 最低价没有跌破MA20，不满足"触及"条件
                return False
            
            if today_close <= today_ma:
                # 收盘价没有站上MA20，不满足"触及"条件
                return False
            
            # 条件3：跌破幅度在阈值范围内
            # 跌破幅度 = (MA20 - 最低价) / MA20 * 100
            break_ratio = (today_ma - today_low) / today_ma * 100
            if break_ratio > touch_threshold:
                # 跌破幅度超过阈值，不满足条件
                return False
            
            # 条件4：长下影（下影线占整个K线的比例 >= min_lower_shadow_ratio）
            body = abs(today_close - today_open)
            total_range = today_high - today_low
            lower_shadow = min(today_close, today_open) - today_low
            
            if total_range == 0:
                return False
            
            lower_shadow_ratio = lower_shadow / total_range
            
            if lower_shadow_ratio < min_lower_shadow_ratio:
                return False
            
            return True
                
        except Exception as e:
            print(f"[MA20SupportFilter] 评估 {stock_code} 失败: {e}")
            return True

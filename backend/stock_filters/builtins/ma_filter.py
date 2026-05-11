"""
均线过滤筛选器
"""
from typing import Dict
import numpy as np
from .base import BaseFilter


class MAFilter(BaseFilter):
    """均线过滤筛选器
    
    根据均线排列情况进行筛选
    """
    
    filter_id = 'ma_filter'
    name = "均线过滤"
    description = "根据均线排列情况进行筛选，支持多头、空头、金叉、死叉等"
    category = "技术指标"
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "filter_mode": {
                "type": "string",
                "title": "筛选模式",
                "description": "选择均线排列模式",
                "enum": ["多头排列", "空头排列", "金叉", "死叉"],
                "default": "多头排列"
            },
            "ma1_period": {
                "type": "integer",
                "title": "MA1周期",
                "default": 7,
                "minimum": 1,
                "maximum": 250
            },
            "ma2_period": {
                "type": "integer",
                "title": "MA2周期",
                "default": 21,
                "minimum": 1,
                "maximum": 250
            },
            "ma3_period": {
                "type": "integer",
                "title": "MA3周期",
                "description": "可选，用于多头/空头排列",
                "default": 0,
                "minimum": 0,
                "maximum": 250
            }
        },
        "required": ["filter_mode", "ma1_period", "ma2_period"]
    }
    
    def _calc_ma(self, data, period):
        """计算简单移动平均"""
        period = int(period)  # 确保period是整数
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
        filter_mode = parameters.get('filter_mode', '多头排列')
        ma1_period = int(parameters.get('ma1_period', 7))
        ma2_period = int(parameters.get('ma2_period', 21))
        ma3_period = int(parameters.get('ma3_period', 0))
        
        try:
            close = stock_data['close'].values
            
            n = len(close)
            min_required = max(ma1_period, ma2_period, ma3_period) if ma3_period > 0 else max(ma1_period, ma2_period)
            
            if n < min_required + 1:  # 需要额外1个BAR，因为排除最后一个BAR
                return False
            
            # 计算MA
            ma1 = self._calc_ma(close, ma1_period)
            ma2 = self._calc_ma(close, ma2_period)
            ma3 = self._calc_ma(close, ma3_period) if ma3_period > 0 else None
            
            # 排除最后一个BAR（可能是当天的数据，还在更新中）
            # 使用倒数第二个BAR作为最新的数据
            idx = n - 2
            
            if np.isnan(ma1[idx]) or np.isnan(ma2[idx]):
                return False
            
            if ma3 is not None and np.isnan(ma3[idx]):
                return False
            
            # 根据筛选模式判断
            if filter_mode == "多头排列":
                # MA1 > MA2 > MA3
                if ma3 is not None:
                    return ma1[idx] > ma2[idx] > ma3[idx]
                else:
                    return ma1[idx] > ma2[idx]
            
            elif filter_mode == "空头排列":
                # MA1 < MA2 < MA3
                if ma3 is not None:
                    return ma1[idx] < ma2[idx] < ma3[idx]
                else:
                    return ma1[idx] < ma2[idx]
            
            elif filter_mode == "金叉":
                # MA1上穿MA2
                if idx < 1:
                    return False
                # 前一天MA1 <= MA2，今天MA1 > MA2
                return ma1[idx - 1] <= ma2[idx - 1] and ma1[idx] > ma2[idx]
            
            elif filter_mode == "死叉":
                # MA1下穿MA2
                if idx < 1:
                    return False
                # 前一天MA1 >= MA2，今天MA1 < MA2
                return ma1[idx - 1] >= ma2[idx - 1] and ma1[idx] < ma2[idx]
            
            else:
                return True
                
        except Exception as e:
            print(f"[MAFilter] 评估 {stock_code} 失败: {e}")
            return True

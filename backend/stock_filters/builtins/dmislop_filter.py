from typing import Dict
import numpy as np
from .base import BaseFilter


class DMISLOPFilter(BaseFilter):
    filter_id = 'dmislop_filter'
    name = 'DMISLOP信号'
    description = 'DMI+斜率综合信号筛选'
    category = 'technical'
    filter_stage = 'pre_filter'
    parameters_schema = {
        'type': 'object',
        'properties': {
            'ma1_period': {
                'type': 'integer',
                'default': 7,
                'title': '短期均线周期',
                'minimum': 3,
                'maximum': 20
            },
            'ma2_period': {
                'type': 'integer',
                'default': 21,
                'title': '中期均线周期',
                'minimum': 10,
                'maximum': 60
            },
            'ma100_period': {
                'type': 'integer',
                'default': 10,
                'title': '斜率均线周期',
                'minimum': 5,
                'maximum': 30
            },
            'slope_up': {
                'type': 'number',
                'default': 0.3,
                'title': '上升斜率阈值',
                'minimum': 0,
                'maximum': 5
            },
            'slope_down': {
                'type': 'number',
                'default': -0.3,
                'title': '下降斜率阈值',
                'minimum': -5,
                'maximum': 0
            },
            'adx_period': {
                'type': 'integer',
                'default': 14,
                'title': 'DMI周期',
                'minimum': 5,
                'maximum': 30
            },
            'pdi_threshold': {
                'type': 'number',
                'default': 30.0,
                'title': 'PDI阈值',
                'minimum': 0,
                'maximum': 100
            },
            'signal_type': {
                'type': 'string',
                'default': 'buy',
                'title': '信号类型',
                'enum': ['buy', 'sell']
            },
            'prev_signal_type': {
                'type': 'string',
                'default': '任意',
                'title': '上个信号类型',
                'description': '任意=不检查, 空信号=无持仓, 多信号=之前是买入',
                'enum': ['任意', '空信号', '多信号']
            }
        }
    }
    
    def _calc_ma(self, data, period):
        period = int(period)  # 确保period是整数
        n = len(data)
        if n < period:
            return np.full(n, np.nan)
        result = np.full(n, np.nan)
        for i in range(period - 1, n):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result
    
    def _calc_slope(self, ma_values, idx, lookback=2):
        if idx < lookback:
            return 0.0
        ma_now = ma_values[idx]
        ma_prev = ma_values[idx - lookback]
        if np.isnan(ma_now) or np.isnan(ma_prev) or ma_now == 0:
            return 0.0
        slope_ratio = (ma_now - ma_prev) / lookback / ma_now * 100.0
        slope = np.arctan(slope_ratio) * 180.0 / np.pi
        return slope
    
    def _calc_dmi(self, high, low, close, idx, period):
        period = int(period)  # 确保period是整数
        n = len(close)
        pdi = 0.0
        mdi = 0.0
        
        if idx < period:
            return pdi, mdi
        
        tr_sum = 0.0
        dmp_sum = 0.0
        dmm_sum = 0.0
        
        for j in range(period):
            jdx = idx - j
            jdx_prev = jdx - 1
            if jdx >= 1 and jdx < n and jdx_prev >= 0:
                tr = max(high[jdx] - low[jdx],
                        abs(high[jdx] - close[jdx_prev]),
                        abs(low[jdx] - close[jdx_prev]))
                hd = high[jdx] - high[jdx_prev]
                ld = low[jdx_prev] - low[jdx]
                tr_sum += tr
                dmp_sum += hd if (hd > 0 and hd > ld) else 0
                dmm_sum += ld if (ld > 0 and ld > hd) else 0
        
        if tr_sum > 0:
            pdi = dmp_sum * 100.0 / tr_sum
            mdi = dmm_sum * 100.0 / tr_sum
        
        return pdi, mdi
    
    def _calc_signal_for_bar(self, high, low, close, ma1, ma2, ma100, idx, 
                              slope_up, slope_down, adx_period, pdi_threshold,
                              ma1_period, ma2_period, ma100_period):
        n = len(close)
        
        min_idx = max(ma1_period - 1, ma2_period - 1, ma100_period + 1, adx_period + 1, 2)
        if idx < min_idx:
            return 0
        
        if np.isnan(ma1[idx]) or np.isnan(ma2[idx]) or np.isnan(ma100[idx]):
            return 0
        
        slope = self._calc_slope(ma100, idx)
        pdi, mdi = self._calc_dmi(high, low, close, idx, adx_period)
        
        ma1_val = ma1[idx]
        ma2_val = ma2[idx]
        
        jc = 1 if ma1_val > ma2_val else 0
        sc = 1 if ma1_val < ma2_val else 0
        
        dn1 = 1 if pdi > mdi else 0
        dn2 = 1 if pdi < mdi else 0
        
        yy1 = 1 if slope > slope_up else 0
        yy2 = 1 if slope < slope_down else 0
        
        high_break = close[idx] > max(high[idx - 1], high[idx - 2])
        low_break = close[idx] < min(low[idx - 1], low[idx - 2])
        
        if (jc == 1 and dn1 == 1 and yy1 == 1 and 
            high_break and pdi > pdi_threshold):
            return 1
        
        if (sc == 1 and dn2 == 1 and yy2 == 1 and 
            low_break and mdi > pdi_threshold):
            return -1
        
        return 0
    
    def evaluate(self, stock_code: str, context: Dict) -> bool:
        stock_data = context.get('stock_data')
        if stock_data is None:
            return True
        
        parameters = context.get('parameters', {})
        ma1_period = int(parameters.get('ma1_period', 7))
        ma2_period = int(parameters.get('ma2_period', 21))
        ma100_period = int(parameters.get('ma100_period', 10))
        slope_up = parameters.get('slope_up', 0.3)
        slope_down = parameters.get('slope_down', -0.3)
        adx_period = int(parameters.get('adx_period', 14))
        pdi_threshold = parameters.get('pdi_threshold', 30.0)
        signal_type = parameters.get('signal_type', 'buy')
        prev_signal_type = parameters.get('prev_signal_type', '任意')
        
        try:
            high = stock_data['high'].values
            low = stock_data['low'].values
            close = stock_data['close'].values
            
            n = len(close)
            min_required = max(ma2_period, adx_period + 3, ma100_period + 3)
            if n < min_required + 1:  # 需要额外1个BAR，因为排除最后一个BAR
                return False
            
            ma1 = self._calc_ma(close, ma1_period)
            ma2 = self._calc_ma(close, ma2_period)
            ma100 = self._calc_ma(close, ma100_period)
            
            # 排除最后一个BAR（可能是当天的数据，还在更新中）
            # 使用倒数第二个BAR作为最新的信号
            signal_list = []
            for i in range(n - 1):  # 不包括最后一个BAR
                sig = self._calc_signal_for_bar(high, low, close, ma1, ma2, ma100, i,
                                                 slope_up, slope_down, adx_period, pdi_threshold,
                                                 ma1_period, ma2_period, ma100_period)
                signal_list.append(sig)
            
            # 获取最新的信号（倒数第二个BAR的信号）
            curr_signal = signal_list[-1]
            
            if signal_type == 'buy' and curr_signal != 1:
                return False
            if signal_type == 'sell' and curr_signal != -1:
                return False
            
            if prev_signal_type != '任意':
                last_signal = 0
                for i in range(len(signal_list) - 2, -1, -1):
                    if signal_list[i] != 0:
                        last_signal = signal_list[i]
                        break
                
                if prev_signal_type == '空信号' and last_signal == 1:
                    return False
                if prev_signal_type == '多信号' and last_signal != 1:
                    return False
            
            return True
            
        except Exception as e:
            print(f"[DMISLOPFilter] 评估 {stock_code} 失败: {e}")
            return True

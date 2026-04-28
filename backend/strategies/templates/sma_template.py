"""
均线交叉策略模板

策略名称: 均线交叉策略
策略描述: 基于两条均线的交叉进行交易决策。短期均线上穿长期均线买入，下穿卖出。

参数说明:
- fast_period: 快速均线周期，值越小对价格变化越敏感，典型值10 (type: int, range: 3-30)
- slow_period: 慢速均线周期，值越大趋势越稳定，典型值30 (type: int, range: 10-100)

交易逻辑:
1. 当快速均线上穿慢速均线（金叉）且无持仓时，产生买入信号
2. 当快速均线下穿慢速均线（死叉）且有持仓时，产生卖出信号

原理:
- 均线是过去N天收盘价的平均值
- 短期均线对价格变化更敏感
- 金叉表示短期趋势向上，可能继续上涨
- 死叉表示短期趋势向下，可能继续下跌
"""

import backtrader as bt
from backend.strategies.base_strategy import BaseStrategy

class SMAFramework(BaseStrategy):
    """
    均线交叉策略框架 - 可通过参数自定义均线的周期
    """
    params = (
        ('fast_period', 10, '快速均线周期', int),
        ('slow_period', 30, '慢速均线周期', int),
        ('printlog', False),
    )

    name = '均线交叉策略'
    description = '短期均线上穿长期均线买入，下穿卖出'

    def __init__(self):
        """初始化均线指标"""
        super().__init__()
        self.fast_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        """每个bar执行一次交易逻辑"""
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                self.log(f'买入信号, Fast MA: {self.fast_ma[0]:.2f}, Slow MA: {self.slow_ma[0]:.2f}')
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.log(f'卖出信号, Fast MA: {self.fast_ma[0]:.2f}, Slow MA: {self.slow_ma[0]:.2f}')
                self.order = self.sell()

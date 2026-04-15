"""
动量策略模板

策略名称: 动量策略
策略描述: 基于价格动量进行交易决策。当动量超过正向阈值时买入，超过负向阈值时卖出。

参数说明:
- momentum_period: 动量计算周期，表示与多少天前价格比较，典型值12 (type: int, range: 5-30)
- threshold: 动量阈值，正值表示上涨动量，负值表示下跌动量，典型值0.02 (type: float, range: 0.001-0.1)

交易逻辑:
1. 当动量 > threshold 且无持仓时，产生买入信号
2. 当动量 < -threshold 且有持仓时，产生卖出信号

原理:
- 动量 = 当前价格 - N天前价格（也可用收益率表示）
- 正动量表示价格在上涨趋势中
- 负动量表示价格在下跌趋势中
- 动量策略假设趋势会延续
"""

import backtrader as bt
from strategies.base_strategy import BaseStrategy

class MomentumFramework(BaseStrategy):
    """
    动量策略框架 - 可通过参数自定义动量周期和阈值
    """
    params = (
        ('momentum_period', 12, '动量计算周期', int),
        ('threshold', 0.02, '动量阈值，正值买入负值卖出', float),
        ('printlog', False),
    )

    name = '动量策略'
    description = '基于动量指标，当动量超过阈值时产生信号'

    def __init__(self):
        """初始化动量指标"""
        super().__init__()
        self.momentum = bt.indicators.Momentum(
            self.datas[0].close,
            period=self.params.momentum_period
        )

    def next(self):
        """每个bar执行一次交易逻辑"""
        if self.order:
            return

        if not self.position:
            if self.momentum[0] > self.params.threshold:
                self.log(f'买入信号 (动量: {self.momentum[0]:.4f})')
                self.order = self.buy()
        else:
            if self.momentum[0] < -self.params.threshold:
                self.log(f'卖出信号 (动量: {self.momentum[0]:.4f})')
                self.order = self.sell()

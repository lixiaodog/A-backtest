"""
MACD策略模板

策略名称: MACD策略
策略描述: 基于MACD指标的金叉死叉进行交易决策。MACD线上穿Signal线买入，下穿卖出。

参数说明:
- fast_period: 快线EMA周期，值越小对价格变化越敏感，典型值12 (type: int, range: 5-30)
- slow_period: 慢线EMA周期，值越大趋势越稳定，典型值26 (type: int, range: 15-50)
- signal_period: Signal线平滑周期，典型值9 (type: int, range: 5-20)

交易逻辑:
1. 当MACD线上穿Signal线（金叉）且无持仓时，产生买入信号
2. 当MACD线下穿Signal线（死叉）且有持仓时，产生卖出信号

原理:
- MACD由快线EMA减去慢线EMA得出，反映短期与长期趋势差异
- Signal线是MACD的EMA平滑线
- 金叉表示短期动量强于长期，可能上涨
- 死叉表示短期动量弱于长期，可能下跌
"""

import backtrader as bt
from strategies.base_strategy import BaseStrategy

class MACDFramework(BaseStrategy):
    """
    MACD策略框架 - 可通过参数自定义快慢线周期
    """
    params = (
        ('fast_period', 12, '快线EMA周期', int),
        ('slow_period', 26, '慢线EMA周期', int),
        ('signal_period', 9, 'Signal线平滑周期', int),
        ('printlog', False),
    )

    name = 'MACD策略'
    description = 'MACD金叉买入，死叉卖出'

    def __init__(self):
        """初始化MACD指标"""
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.datas[0].close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        """每个bar执行一次交易逻辑"""
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                self.log(f'买入信号, MACD: {self.macd.macd[0]:.2f}, Signal: {self.macd.signal[0]:.2f}')
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.log(f'卖出信号, MACD: {self.macd.macd[0]:.2f}, Signal: {self.macd.signal[0]:.2f}')
                self.order = self.sell()

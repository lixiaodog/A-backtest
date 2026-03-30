import backtrader as bt
from strategies.base_strategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    params = (
        ('momentum_period', 12),
        ('threshold', 0.02),
        ('printlog', False),
    )

    name = '动量策略'
    description = '当价格动量超过阈值时买入或卖出'

    def __init__(self):
        super().__init__()
        self.momentum = bt.indicators.Momentum(
            self.datas[0].close, period=self.params.momentum_period)

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.momentum[0] > self.params.threshold:
                self.log(f'买入信号 (动量: {self.momentum[0]:.4f}), 收盘价: {self.dataclose[0]:.2f}')
                self.order = self.buy()
        else:
            if self.momentum[0] < -self.params.threshold:
                self.log(f'卖出信号 (动量: {self.momentum[0]:.4f}), 收盘价: {self.dataclose[0]:.2f}')
                self.order = self.sell()

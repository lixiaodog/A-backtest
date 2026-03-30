import backtrader as bt
from strategies.base_strategy import BaseStrategy

class SMACrossStrategy(BaseStrategy):
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
    )

    name = '双均线交叉策略'
    description = '当快速均线上穿慢速均线时买入，下穿时卖出'

    def __init__(self):
        super().__init__()
        self.fast_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
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

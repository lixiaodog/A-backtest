import backtrader as bt
from backend.strategies.base_strategy import BaseStrategy

class MACDStrategy(BaseStrategy):
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )

    name = 'MACD策略'
    description = 'MACD金叉买入，死叉卖出'

    def __init__(self):
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.datas[0].close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
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

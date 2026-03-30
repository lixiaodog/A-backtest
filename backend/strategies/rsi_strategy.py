import backtrader as bt
from strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
        ('printlog', False),
    )

    name = 'RSI策略'
    description = 'RSI超卖时买入，超买时卖出'

    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(
            self.datas[0].close,
            period=self.params.rsi_period
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.rsi < self.params.oversold:
                self.log(f'买入信号, RSI: {self.rsi[0]:.2f}')
                self.order = self.buy()
        else:
            if self.rsi > self.params.overbought:
                self.log(f'卖出信号, RSI: {self.rsi[0]:.2f}')
                self.order = self.sell()

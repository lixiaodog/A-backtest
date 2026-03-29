import backtrader as bt
from strategies.base_strategy import BaseStrategy

class SMACrossStrategy(BaseStrategy):
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('printlog', False),
    )

    def __init__(self):
        super().__init__()
        self.sma_fast = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.fast_period)
        self.sma_slow = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        if self.order:
            return

        bar_index = len(self) - 1
        if not self.position:
            if self.crossover > 0:
                self.log(f'买入信号, 收盘价: {self.dataclose[0]:.2f}')
                self.order = self.buy()
                if self._signal_callback:
                    self._signal_callback({
                        'bar_index': bar_index,
                        'type': 'buy',
                        'price': float(self.dataclose[0]),
                        'time': self.data.datetime.datetime(0).timestamp() if hasattr(self.data.datetime, 'datetime') else None
                    })
        else:
            if self.crossover < 0:
                self.log(f'卖出信号, 收盘价: {self.dataclose[0]:.2f}')
                self.order = self.sell()
                if self._signal_callback:
                    self._signal_callback({
                        'bar_index': bar_index,
                        'type': 'sell',
                        'price': float(self.dataclose[0]),
                        'time': self.data.datetime.datetime(0).timestamp() if hasattr(self.data.datetime, 'datetime') else None
                    })

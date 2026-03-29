import backtrader as bt
import pandas as pd

class BaseStrategy(bt.Strategy):
    params = (
        ('printlog', False),
    )

    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            bar_index = len(self) - 1
            trade_info = {
                'bar_index': bar_index,
                'type': 'buy' if order.isbuy() else 'sell',
                'price': float(order.executed.price),
                'size': abs(order.executed.size),
                'value': float(order.executed.value),
                'commission': float(order.executed.comm)
            }

            if hasattr(self, 'trades'):
                self.trades.append(trade_info)
            else:
                self.trades = [trade_info]

            self.order = None

            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, '
                         f'成本: {order.executed.value:.2f}, '
                         f'手续费: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, '
                         f'成本: {order.executed.value:.2f}, '
                         f'手续费: {order.executed.comm:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/拒绝')
            self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'交易完成, 利润: {trade.pnl:.2f}, 利润率: {trade.pnlcomm:.2f}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.trades = []
        self._signal_callback = None

    def set_signal_callback(self, callback):
        self._signal_callback = callback

    def next(self):
        pass

    def stop(self):
        pass

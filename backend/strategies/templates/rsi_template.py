"""
RSI策略模板

策略名称: RSI策略
策略描述: 基于相对强弱指数(RSI)进行交易决策。RSI低于超卖阈值时买入，高于超买阈值时卖出。

参数说明:
- rsi_period: RSI计算周期，值越大RSI越平滑，典型值14 (type: int, range: 2-50)
- oversold: 超卖阈值，低于此值产生买入信号，典型值30 (type: float, range: 10-50)
- overbought: 超买阈值，高于此值产生卖出信号，典型值70 (type: float, range: 50-90)

交易逻辑:
1. 当RSI < oversold 且无持仓时，产生买入信号
2. 当RSI > overbought 且有持仓时，产生卖出信号

原理:
- RSI衡量价格涨跌的相对强度，值域0-100
- RSI < 30 表示市场超卖，价格可能反弹
- RSI > 70 表示市场超买，价格可能回调
"""

import backtrader as bt
from backend.strategies.base_strategy import BaseStrategy

class RSIFramework(BaseStrategy):
    """
    RSI策略框架 - 可通过参数自定义RSI周期和超买超卖阈值
    """
    params = (
        ('rsi_period', 14, 'RSI计算周期', int),
        ('oversold', 30, '超卖阈值，低于此值买入', float),
        ('overbought', 70, '超买阈值，高于此值卖出', float),
        ('printlog', False),
    )

    name = 'RSI策略'
    description = 'RSI超卖时买入，超买时卖出'

    def __init__(self):
        """初始化RSI指标"""
        super().__init__()
        self.rsi = bt.indicators.RSI(
            self.datas[0].close,
            period=self.params.rsi_period
        )

    def next(self):
        """每个bar执行一次交易逻辑"""
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

import backtrader as bt
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

class AStockCommission:
    params = (
        ('stocklike', True),
        ('commission', 0.0003),
        ('mult', 1.0),
        ('margin', None),
    )

    def __init__(self):
        self._commission = 0.0003
        self._stamp_duty = 0.0005
        self._transfer_fee = 0.00002

    def getcommission(self, size, price):
        if size < 0:
            return abs(size) * price * self._stamp_duty + abs(size) * self._transfer_fee
        else:
            return abs(size) * price * self._commission

class AStockBacktestEngine:
    def __init__(self, initial_cash=1000000, commission_pct=0.0003, stake=100):
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(initial_cash)
        self.cerebro.broker.setcommission(commission=commission_pct)
        self.cerebro.addsizer(bt.sizers.FixedSize, stake=stake)

        self.initial_cash = initial_cash
        self.results = None

    def add_data(self, datafeed):
        self.cerebro.adddata(datafeed)

    def add_strategy(self, strategy_class, **kwargs):
        self._strategy_class = strategy_class
        self._strategy_params = kwargs
        self.cerebro.addstrategy(strategy_class, **kwargs)

    def run(self):
        print(f"初始资金: {self.cerebro.broker.getcash():.2f}")
        self.results = self.cerebro.run()
        return self.results

    def print_results(self):
        final_cash = self.cerebro.broker.getvalue()
        print(f"\n最终资金: {final_cash:.2f}")
        print(f"总收益: {final_cash - self.initial_cash:.2f}")
        print(f"收益率: {(final_cash / self.initial_cash - 1) * 100:.2f}%")

        return {
            'initial_cash': self.initial_cash,
            'final_cash': final_cash,
            'total_return': final_cash - self.initial_cash,
            'return_rate': (final_cash / self.initial_cash - 1) * 100
        }

    def plot(self, savefig=False, filepath='results/backtest_result.png'):
        os.makedirs('results', exist_ok=True)
        try:
            fig = self.cerebro.plot(style='candlestick', barup='red', bardown='green',
                                   returnfig=True)[0][0]
            if savefig:
                fig.savefig(filepath, dpi=100, bbox_inches='tight')
                print(f"图表已保存到: {os.path.abspath(filepath)}")
            plt.close(fig)
        except Exception as e:
            print(f"生成图表时出错: {e}")
            print("请尝试不使用 --plot 参数运行")

    def add_analyzer(self, analyzer_class, **kwargs):
        self.cerebro.addanalyzer(analyzer_class, **kwargs)

    def get_strategy(self):
        if self.results:
            return self.results[0]
        return None

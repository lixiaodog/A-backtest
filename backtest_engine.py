import backtrader as bt
import os
import uuid
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()
from matplotlib.figure import Figure

class RealtimeChartObserver(bt.Observer):
    lines = ('value',)
    params = (('socketio', None), ('task_id', None), ('emit_interval', 1))

    def __init__(self):
        self._bar_count = 0

    def next(self):
        self._bar_count += 1
        time.sleep(0.02)
        self.lines.value[0] = self._owner.broker.getvalue()
        if self.params.socketio and self._bar_count % self.params.emit_interval == 0:
            bar_data = {
                'task_id': self.params.task_id,
                'type': 'chart_data',
                'bar': {
                    'time': self.data.datetime.datetime(0).timestamp() if hasattr(self.data.datetime, 'datetime') else None,
                    'open': self.data.open[0],
                    'high': self.data.high[0],
                    'low': self.data.low[0],
                    'close': self.data.close[0],
                    'volume': self.data.volume[0],
                },
                'portfolio_value': self._owner.broker.getvalue(),
                'bar_index': self._bar_count
            }
            print(f"[实时图表] bar_index={self._bar_count}, close={self.data.close[0]:.2f}")
            self.params.socketio.emit('backtest_chart', bar_data)

class RealtimeSignalAnalyzer(bt.Analyzer):
    params = (('socketio', None), ('task_id', None))

    def notify_order(self, order):
        if order.status in [order.Completed] and self.params.socketio:
            strategy = self.strategy
            signal_data = {
                'task_id': self.params.task_id,
                'type': 'trade_signal',
                'signal': {
                    'bar_index': len(strategy) - 1,
                    'trade_type': 'buy' if order.isbuy() else 'sell',
                    'price': float(order.executed.price),
                    'time': strategy.data.datetime.datetime(0).timestamp() if hasattr(strategy.data.datetime, 'datetime') else None
                }
            }
            print(f"[实时信号] {'买入' if order.isbuy() else '卖出'} bar_index={len(strategy) - 1}, price={order.executed.price:.2f}")
            self.params.socketio.emit('backtest_signal', signal_data)

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
            return abs(size) * price * self._stamp_duty + abs(size) * price * self._transfer_fee
        else:
            return abs(size) * price * self._commission

class AStockBacktestEngine:
    def __init__(self, initial_cash=1000000, commission_pct=0.0003, stake=100):
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(initial_cash)
        self.cerebro.broker.setcommission(commission_pct)
        self.cerebro.addsizer(bt.sizers.FixedSize, stake=stake)

        self.initial_cash = initial_cash
        self.results = None
        self._analyzers = {}
        self._socketio = None
        self._task_id = None

    def set_socketio(self, socketio, task_id):
        self._socketio = socketio
        self._task_id = task_id

    def add_data(self, datafeed):
        self.cerebro.adddata(datafeed)

    def add_strategy(self, strategy_class, **kwargs):
        self._strategy_class = strategy_class
        self._strategy_params = kwargs
        self.cerebro.addstrategy(strategy_class, **kwargs)

    def run(self):
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown)
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer)

        if self._socketio:
            self.cerebro.addobserver(
                RealtimeChartObserver,
                socketio=self._socketio,
                task_id=self._task_id,
                emit_interval=1
            )
            self.cerebro.addanalyzer(
                RealtimeSignalAnalyzer,
                socketio=self._socketio,
                task_id=self._task_id
            )

        print(f"初始资金: {self.cerebro.broker.getcash():.2f}")
        self.results = self.cerebro.run()

        try:
            for analyzer in self.results[0].analyzers:
                self._analyzers[type(analyzer).__name__] = analyzer
        except Exception as e:
            print(f"收集分析器时出错: {e}")

        return self.results

    def get_analysis_data(self):
        equity_data = []
        if 'TimeReturn' in self._analyzers:
            timereturn_analysis = self._analyzers['TimeReturn'].get_analysis()
            initial_cash = self._strategy_params.get('cash', 100000)
            cumulative_value = initial_cash
            for i, (date, rate) in enumerate(timereturn_analysis.items()):
                cumulative_value = cumulative_value * (1 + rate)
                profit = cumulative_value - initial_cash
                timestamp = int(date.timestamp()) if hasattr(date, 'timestamp') else int(date)
                equity_data.append({'step': i + 1, 'time': timestamp, 'value': profit, 'date': str(date)})

        drawdown_data = []
        if 'DrawDown' in self._analyzers:
            drawdown_analysis = self._analyzers['DrawDown'].get_analysis()
            drawdown_data.append({
                'len': drawdown_analysis.get('len', 0),
                'drawdown': drawdown_analysis.get('drawdown', 0),
                'moneydown': drawdown_analysis.get('moneydown', 0),
                'max': drawdown_analysis.get('max', {}).get('drawdown', 0)
            })

        trade_analysis = self._analyzers.get('TradeAnalyzer', None)

        stats = {
            'final_cash': self.cerebro.broker.getvalue(),
            'total_return': self.cerebro.broker.getvalue() - self.initial_cash,
            'return_rate': ((self.cerebro.broker.getvalue() / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0,
        }

        if trade_analysis:
            ta = trade_analysis.get_analysis()
            stats['total_trades'] = ta.get('total', {}).get('total', 0) or 0
            stats['closed_trades'] = ta.get('total', {}).get('closed', 0) or 0
            stats['won_trades'] = ta.get('won', {}).get('total', 0) or 0
            stats['lost_trades'] = ta.get('lost', {}).get('total', 0) or 0

        return {
            'equity_data': equity_data,
            'drawdown_data': drawdown_data,
            'stats': stats
        }

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

    def save_chart_image(self, task_id=None):
        project_root = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(project_root, 'results')
        os.makedirs(results_dir, exist_ok=True)
        filename = f'backtest_{task_id or uuid.uuid4().hex[:8]}.png'
        filepath = os.path.join(results_dir, filename)
        try:
            fig = self.cerebro.plot(style='candlestick', barup='red', bardown='green',
                                   returnfig=True)[0][0]
            fig.savefig(filepath, dpi=100, bbox_inches='tight')
            plt.close(fig)
            return f'/api/chart/{filename}'
        except Exception as e:
            print(f"生成图表时出错: {e}")
            return None

    def add_analyzer(self, analyzer_class, **kwargs):
        self.cerebro.addanalyzer(analyzer_class, **kwargs)

    def get_strategy(self):
        if self.results:
            return self.results[0]
        return None

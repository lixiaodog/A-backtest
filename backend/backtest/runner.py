import argparse
import sys
from datetime import datetime

from backend.backtest.data_handler import get_astock_hist_data, AStockData
from backend.backtest.engine import AStockBacktestEngine
from backend.strategies.sma_cross import SMACrossStrategy
from backend.strategies.momentum import MomentumStrategy
from backend.strategies.rsi_strategy import RSIStrategy

STRATEGY_MAP = {
    'sma_cross': SMACrossStrategy,
    'momentum': MomentumStrategy,
    'rsi': RSIStrategy,
}

def parse_args():
    parser = argparse.ArgumentParser(description='Backtrader A股回测系统')
    parser.add_argument('--stock', type=str, default='600519',
                        help='股票代码，如 600519（贵州茅台）')
    parser.add_argument('--start', type=str, default='20230101',
                        help='开始日期，格式 YYYYMMDD')
    parser.add_argument('--end', type=str, default='20231231',
                        help='结束日期，格式 YYYYMMDD')
    parser.add_argument('--strategy', type=str, default='sma_cross',
                        choices=list(STRATEGY_MAP.keys()),
                        help='策略类型')
    parser.add_argument('--cash', type=float, default=1000000,
                        help='初始资金')
    parser.add_argument('--fast', type=int, default=10,
                        help='快速均线周期（仅SMA策略）')
    parser.add_argument('--slow', type=int, default=30,
                        help='慢速均线周期（仅SMA策略）')
    parser.add_argument('--rsi_period', type=int, default=14,
                        help='RSI周期（仅RSI策略）')
    parser.add_argument('--plot', action='store_true',
                        help='显示回测图表')
    return parser.parse_args()

def main():
    args = parse_args()

    print(f"{'='*50}")
    print(f"Backtrader A股回测系统")
    print(f"{'='*50}")
    print(f"股票代码: {args.stock}")
    print(f"日期范围: {args.start} - {args.end}")
    print(f"策略类型: {args.strategy}")
    print(f"初始资金: {args.cash}")
    print(f"{'='*50}\n")

    print("正在获取数据...")
    try:
        df = get_astock_hist_data(args.stock, args.start, args.end)
        print(f"成功获取 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取数据失败: {e}")
        sys.exit(1)

    datafeed = AStockData(dataname=df)

    engine = AStockBacktestEngine(initial_cash=args.cash)
    engine.add_data(datafeed)

    if args.strategy == 'sma_cross':
        engine.add_strategy(SMACrossStrategy,
                           fast_period=args.fast,
                           slow_period=args.slow)
    elif args.strategy == 'momentum':
        engine.add_strategy(MomentumStrategy)
    elif args.strategy == 'rsi':
        engine.add_strategy(RSIStrategy, rsi_period=args.rsi_period)

    print("\n开始回测...")
    engine.run()
    results = engine.print_results()

    if args.plot:
        print("\n生成回测图表...")
        engine.plot(savefig=True)

    return results

if __name__ == "__main__":
    main()

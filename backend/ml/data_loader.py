import pandas as pd
import os


class MLDataLoader:
    MARKETS = ['SZ', 'SH', 'BJ']
    PERIODS = ['1d', '1m', '5m', '15m', '30m', '60m', '1h', '4h', '1w']

    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data')
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_stock_path(self, stock_code: str, market: str, period: str) -> str:
        return os.path.join(self.data_dir, market, period, f'{stock_code}.csv')

    def _get_market_from_code(self, stock_code: str) -> str:
        if stock_code.startswith('6'):
            return 'SH'
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return 'SZ'
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            return 'BJ'
        return 'SZ'

    def load_stock_data(self, stock_code: str, start_date: str = None, end_date: str = None,
                       period: str = '1d', market: str = None) -> pd.DataFrame:
        if market is None:
            market = self._get_market_from_code(stock_code)

        cache_path = self._get_stock_path(stock_code, market, period)

        if not os.path.exists(cache_path):
            raise FileNotFoundError(f'数据文件不存在: {cache_path}')

        df = pd.read_csv(cache_path, index_col='stime', parse_dates=True)
        df.sort_index(inplace=True)

        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df.index >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df.index <= end_dt]

        return df

    def load_multiple_stocks(self, stock_codes: list, start_date: str = None, end_date: str = None,
                           period: str = '1d', market: str = None, progress_callback=None) -> pd.DataFrame:
        all_data = []
        total = len(stock_codes)
        for i, stock_code in enumerate(stock_codes):
            try:
                df = self.load_stock_data(stock_code, start_date, end_date, period, market)
                df['stock_code'] = stock_code
                if market:
                    df['market'] = market
                all_data.append(df)
                if progress_callback:
                    progress_callback(i + 1, total, stock_code)
            except FileNotFoundError:
                print(f'[MLDataLoader] 跳过不存在的股票: {stock_code}')
                continue

        if not all_data:
            raise FileNotFoundError('没有可用的股票数据')

        combined = pd.concat(all_data, ignore_index=False)
        combined.sort_index(inplace=True)
        return combined

    def get_available_stocks(self, market: str = None, period: str = '1d') -> list:
        if market:
            market_dir = os.path.join(self.data_dir, market, period)
            if not os.path.exists(market_dir):
                return []
            return [f[:-4] for f in os.listdir(market_dir) if f.endswith('.csv')]

        stocks = set()
        for mkt in self.MARKETS:
            mkt_dir = os.path.join(self.data_dir, mkt, period)
            if os.path.exists(mkt_dir):
                for f in os.listdir(mkt_dir):
                    if f.endswith('.csv'):
                        stocks.add(f[:-4])
        return sorted(list(stocks))

    def get_markets(self) -> list:
        markets = []
        for mkt in self.MARKETS:
            if os.path.exists(os.path.join(self.data_dir, mkt)):
                markets.append(mkt)
        return markets

    def get_periods(self, market: str = None) -> list:
        if market:
            market_dir = os.path.join(self.data_dir, market)
            if not os.path.exists(market_dir):
                return []
            return [d for d in os.listdir(market_dir) if os.path.isdir(os.path.join(market_dir, d)) and d in self.PERIODS]
        return self.PERIODS

    def get_data_tree(self) -> dict:
        tree = {}
        for mkt in self.get_markets():
            tree[mkt] = {}
            for period in self.get_periods(mkt):
                stocks = self.get_available_stocks(mkt, period)
                if stocks:
                    tree[mkt][period] = stocks
        return tree

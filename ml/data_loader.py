import pandas as pd
import os


class MLDataLoader:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def load_stock_data(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily') -> pd.DataFrame:
        cache_path = os.path.join(self.data_dir, f'{stock_code}_{period}.csv')

        if not os.path.exists(cache_path):
            raise FileNotFoundError(f'数据文件不存在: {cache_path}')

        df = pd.read_csv(cache_path, index_col='datetime', parse_dates=True)
        df.sort_index(inplace=True)

        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df.index >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df.index <= end_dt]

        return df

    def get_available_stocks(self):
        files = os.listdir(self.data_dir)
        stocks = set()
        for f in files:
            if f.endswith('.csv'):
                parts = f.rsplit('_', 1)
                if len(parts) == 2:
                    stock_code = parts[0]
                    stocks.add(stock_code)
        return sorted(list(stocks))

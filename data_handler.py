import akshare as ak
import pandas as pd
from datetime import datetime, timezone, timedelta
from backtrader.feeds import PandasData

class AStockData(PandasData):
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
    )

def get_astock_hist_data(stock_code: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
    period_map = {
        'daily': 'daily',
        'weekly': 'weekly',
        'monthly': 'monthly',
    }

    minute_periods = {'1min': '1', '5min': '5', '15min': '15', '30min': '30', '60min': '60'}

    if period in minute_periods:
        df = ak.stock_zh_a_hist_min_em(
            symbol=stock_code,
            period=minute_periods[period],
            adjust="qfq"
        )
        df.rename(columns={
            '时间': 'datetime',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }, inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize('Asia/Shanghai')
        df.set_index('datetime', inplace=True)
        df.sort_index(inplace=True)
        start_dt = pd.to_datetime(start_date).tz_localize('Asia/Shanghai')
        end_dt = pd.to_datetime(end_date).tz_localize('Asia/Shanghai')
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        return df[['open', 'high', 'low', 'close', 'volume']]

    ak_period = period_map.get(period, 'daily')
    df = ak.stock_zh_a_hist(symbol=stock_code, period=ak_period,
                            start_date=start_date, end_date=end_date, adjust="qfq")

    df.rename(columns={
        '日期': 'datetime',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume'
    }, inplace=True)

    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)

    return df[['open', 'high', 'low', 'close', 'volume']]

def get_astock_info(stock_code: str) -> dict:
    try:
        df = ak.stock_individual_info_em(symbol=stock_code)
        info = dict(zip(df['item'], df['value']))
        return info
    except Exception as e:
        print(f"获取股票信息失败: {e}")
        return {}

if __name__ == "__main__":
    df = get_astock_hist_data("600519", "20230101", "20231231")
    print(f"数据形状: {df.shape}")
    print(df.tail())

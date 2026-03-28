import sqlite3
import pandas as pd
import akshare as ak
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'stock.db')

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily (
            code TEXT,
            datetime TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (code, datetime)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_daily ON stock_daily(code, datetime)')
    conn.close()

def init_min1_table(code: str):
    conn = get_conn()
    table_name = f'min1_{code}'
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            datetime TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL
        )
    ''')
    conn.close()

def fetch_daily(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist(
        symbol=stock_code,
        period='daily',
        start_date=start_date,
        end_date=end_date,
        adjust='qfq'
    )
    df.rename(columns={
        '日期': 'datetime',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume'
    }, inplace=True)
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    df['code'] = stock_code
    return df

def save_daily(df: pd.DataFrame):
    if df.empty:
        return
    conn = get_conn()
    for _, row in df.iterrows():
        conn.execute('''
            INSERT OR REPLACE INTO stock_daily (code, datetime, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (row['code'], row['datetime'], row['open'], row['high'], row['low'], row['close'], row['volume']))
    conn.commit()
    conn.close()

def fetch_1min(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist_min_em(
        symbol=stock_code,
        period='1',
        adjust='qfq'
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
    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['dt_temp'] = pd.to_datetime(df['datetime'])
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
    df = df[(df['dt_temp'] >= start_dt) & (df['dt_temp'] < end_dt)]
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    df = df.drop_duplicates(subset=['datetime']).sort_values('datetime')
    return df

def save_1min(df: pd.DataFrame, stock_code: str):
    if df.empty:
        return
    init_min1_table(stock_code)
    conn = get_conn()
    table_name = f'min1_{stock_code}'
    for _, row in df.iterrows():
        conn.execute(f'''
            INSERT OR REPLACE INTO {table_name} (datetime, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (row['datetime'], row['open'], row['high'], row['low'], row['close'], row['volume']))
    conn.commit()
    conn.close()

def load_daily(stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    conn = get_conn()
    query = 'SELECT datetime, open, high, low, close, volume FROM stock_daily WHERE code = ?'
    params = [stock_code]
    if start_date:
        query += ' AND datetime >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND datetime <= ?'
        params.append(end_date)
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        df = df.sort_index()
    return df

def load_1min(stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    table_name = f'min1_{stock_code}'
    conn = get_conn()
    try:
        query = f'SELECT datetime, open, high, low, close, volume FROM {table_name}'
        conditions = []
        params = []
        if start_date:
            conditions.append('datetime >= ?')
            params.append(start_date)
        if end_date:
            conditions.append('datetime <= ?')
            params.append(end_date)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            df = df.sort_index()
        return df
    except sqlite3.OperationalError:
        conn.close()
        return pd.DataFrame()

def resample_1min(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty:
        return df
    freq_map = {
        '5min': '5min',
        '15min': '15min',
        '30min': '30min',
        '60min': '60min',
        'daily': 'D',
        'weekly': 'W',
        'monthly': 'M'
    }
    freq = freq_map.get(period, period)
    df_resampled = df.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    df_resampled = df_resampled.dropna()
    return df_resampled

def fetch_and_save(stock_code: str, period: str, start_date: str, end_date: str):
    if period == 'daily':
        df = fetch_daily(stock_code, start_date, end_date)
        save_daily(df)
    elif period == '1min':
        df = fetch_1min(stock_code, start_date, end_date)
        save_1min(df, stock_code)
    else:
        raise ValueError(f'Unsupported period: {period}')
    return df

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 4:
        print('Usage: python data_fetcher.py <stock_code> <period> <start_date> [end_date]')
        print('Example: python data_fetcher.py 600519 daily 20230101 20231231')
        print('Example: python data_fetcher.py 600519 1min 20260301 20260328')
        sys.exit(1)

    stock_code = sys.argv[1]
    period = sys.argv[2]
    start_date = sys.argv[3]
    end_date = sys.argv[4] if len(sys.argv) > 4 else datetime.now().strftime('%Y%m%d')

    init_db()
    print(f'Fetching {period} data for {stock_code} from {start_date} to {end_date}...')
    df = fetch_and_save(stock_code, period, start_date, end_date)
    print(f'Saved {len(df)} rows')

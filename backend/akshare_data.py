import akshare as ak
import pandas as pd
from datetime import datetime, timedelta


def get_stock_info(stock_code):
    """获取股票代码和名称"""
    try:
        market = 'sz' if stock_code.startswith(('000', '001', '002', '003', '300')) else 'sh'
        symbol = f'{market}{stock_code}'
        return {'code': stock_code, 'name': stock_code}
    except Exception as e:
        return {'code': stock_code, 'name': stock_code}


def get_realtime_data(stock_code, period='1d', days=300, end_date=None):
    """从AKShare获取股票数据

    Args:
        stock_code: 股票代码，如 '000001'
        period: 周期，'1d'日线, '1w'周线, '1m'月线
        days: 获取最近多少天的数据
        end_date: 结束日期，格式YYYYMMDD，如果指定则使用该日期

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    try:
        market = 'sz' if stock_code.startswith(('000', '001', '002', '003', '300')) else 'sh'
        symbol = f'{market}{stock_code}'

        if end_date:
            query_end_date = end_date
            start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=days)).strftime('%Y%m%d')
        else:
            query_end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        if period == '1d':
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=query_end_date, adjust='qfq')
        elif period == '1w':
            df = ak.stock_zh_a_hist(symbol=symbol, period='weekly', start_date=start_date, end_date=query_end_date, adjust='qfq')
        elif period == '1m':
            df = ak.stock_zh_a_hist(symbol=symbol, period='monthly', start_date=start_date, end_date=query_end_date, adjust='qfq')
        else:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=query_end_date, adjust='qfq')

        if df is None or not isinstance(df, pd.DataFrame) or len(df) == 0:
            print(f'[AKShare] 获取 {stock_code} 数据为空')
            return None

        if 'date' not in df.columns and '日期' not in df.columns:
            print(f'[AKShare] 获取 {stock_code} 数据缺少日期列，列: {df.columns.tolist()}')
            return None

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
        elif '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.set_index('日期').sort_index()

        rename_map = {
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }
        df = df.rename(columns=rename_map)

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                print(f'[AKShare] 获取 {stock_code} 数据缺少 {col} 列')
                return None

        return df[required_cols]

    except KeyError as e:
        print(f'[AKShare] 获取 {stock_code} 数据KeyError: {e}')
        return None
    except Exception as e:
        print(f'[AKShare] 获取 {stock_code} 数据失败: {e}')
        return None


def get_latest_price(stock_code):
    """获取最新价格"""
    try:
        df = ak.stock_zh_a_spot_em()
        stock_df = df[df['代码'] == stock_code]
        if len(stock_df) > 0:
            return {
                'code': stock_code,
                'name': stock_df.iloc[0]['名称'],
                'price': stock_df.iloc[0]['最新价'],
                'change': stock_df.iloc[0]['涨跌幅'],
                'volume': stock_df.iloc[0]['成交量'],
                'turnover': stock_df.iloc[0]['成交额']
            }
        return None
    except Exception as e:
        print(f'[AKShare] 获取最新价格失败: {e}')
        return None


if __name__ == '__main__':
    print('测试AKShare数据获取...')
    df = get_realtime_data('300968', '1d', 100)
    if df is not None:
        print(f'获取成功，数据形状: {df.shape}')
        print(df.tail())
    else:
        print('获取失败')
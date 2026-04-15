import multiprocessing as mp
from multiprocessing import Pool
import pandas as pd
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _process_single_stock(args):
    stock_code, params = args
    try:
        from ml import MLDataLoader, FeatureEngineer

        data_loader = MLDataLoader()
        raw_data = data_loader.load_stock_data(
            stock_code,
            params['start_date'],
            params['end_date'],
            period=params['period'],
            market=params['market']
        )

        if raw_data is None or len(raw_data) < 100:
            return None

        feature_engineer = FeatureEngineer()
        prepare_func = params['prepare_func']

        if prepare_func == 'prepare_data_regression':
            X, y = feature_engineer.prepare_data_regression(raw_data, params['features'], params['horizon'])
        elif prepare_func == 'prepare_data_with_volatility':
            X, y = feature_engineer.prepare_data_with_volatility(
                raw_data, params['features'], params['horizon'],
                params['vol_window'], params['lower_q'], params['upper_q']
            )
        elif prepare_func == 'prepare_data_multi':
            X, y = feature_engineer.prepare_data_multi(
                raw_data, params['features'], params['horizon'],
                params['lower_q'], params['upper_q']
            )
        else:
            X, y = feature_engineer.prepare_data(
                raw_data, params['features'], params['horizon'], params['threshold']
            )

        if X is None or len(X) < 50:
            return None

        return {
            'stock_code': stock_code,
            'X': X,
            'y': y,
            'sample_count': len(X),
            'scaler_params': feature_engineer.get_scaler_params()
        }

    except Exception as e:
        print(f'[多进程] {stock_code} 处理失败: {e}')
        return None


def parallel_train(stock_list, params, task_id=None, training_tasks=None):
    if task_id and training_tasks:
        training_tasks[task_id] = {
            'progress': 10,
            'status': '并行加载数据...',
            'message': f'使用 {min(4, len(stock_list))} 个进程处理 {len(stock_list)} 只股票'
        }
        print(f'[多进程训练] 任务ID: {task_id} - 启动多进程处理')

    start_time = time.time()

    tasks = [(stock, params) for stock in stock_list]

    cpu_count = os.cpu_count() or 4
    num_processes = max(1, min(cpu_count - 2, len(stock_list)))
    print(f'[多进程训练] CPU核心: {cpu_count}，使用 {num_processes} 个进程处理 {len(stock_list)} 只股票')

    completed = [0]
    total = len(tasks)

    def update_progress(completed_count):
        if task_id and training_tasks:
            progress = int(10 + (completed_count / total) * 50)
            training_tasks[task_id] = {
                'progress': progress,
                'status': f'并行处理 ({completed_count}/{total})',
                'message': f'已处理 {completed_count} 只股票'
            }

    start_time = time.time()
    results = []
    with Pool(processes=num_processes) as pool:
        for result in pool.imap_unordered(_process_single_stock, tasks):
            completed[0] += 1
            update_progress(completed[0])
            results.append(result)

    process_time = time.time() - start_time
    print(f'[多进程训练] 所有股票处理完成，耗时: {process_time:.2f}秒')

    all_X = []
    all_y = []
    stock_sample_counts = {}
    scaler_params = None

    for result in results:
        if result:
            stock_sample_counts[result['stock_code']] = result['sample_count']
            scaler_params = result['scaler_params']
            all_X.append(result['X'])
            all_y.append(result['y'])

    if not all_X:
        return None

    if task_id and training_tasks:
        training_tasks[task_id] = {
            'progress': 60,
            'status': '合并数据...',
            'message': f'成功处理 {len(all_X)} 只股票，合并特征数据'
        }

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)

    total_samples = len(X)
    total_time = time.time() - start_time
    print(f'[多进程训练] 数据合并完成，总样本: {total_samples}，总耗时: {total_time:.2f}秒')
    print(f'[多进程训练] 股票样本分布: {stock_sample_counts}')

    return {
        'X': X,
        'y': y,
        'stock_sample_counts': stock_sample_counts,
        'scaler_params': scaler_params,
        'process_time': process_time,
        'total_time': total_time
    }


if __name__ == '__main__':
    from ml import MLDataLoader

    params = {
        'start_date': '20230101',
        'end_date': '20231231',
        'period': '1d',
        'market': 'SZ',
        'features': ['ma5', 'ma10', 'ma20', 'rsi6', 'rsi12'],
        'horizon': 5,
        'threshold': 0.02,
        'prepare_func': 'prepare_data',
        'vol_window': 20,
        'lower_q': 0.2,
        'upper_q': 0.8
    }

    stock_list = ['000001', '000002', '000004', '000006', '000007']

    print('=' * 50)
    print('多进程训练测试')
    print('=' * 50)

    result = parallel_train(stock_list, params)
    if result:
        print(f'成功处理 {len(result["stock_sample_counts"])} 只股票')
        print(f'总样本: {len(result["X"])}')
        print(f'处理耗时: {result["process_time"]:.2f}秒')
        print(f'总耗时: {result["total_time"]:.2f}秒')

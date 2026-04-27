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
            X, y = feature_engineer.prepare_data_regression(raw_data, params['features'], params['horizon'], normalize=False, stock_code=stock_code, data_source=params.get('data_source', 'csv'))
        elif prepare_func == 'prepare_data_with_volatility':
            X, y = feature_engineer.prepare_data_with_volatility(
                raw_data, params['features'], params['horizon'],
                params['vol_window'], params['lower_q'], params['upper_q'],
                normalize=False, stock_code=stock_code, data_source=params.get('data_source', 'csv')
            )
        elif prepare_func == 'prepare_data_multi':
            X, y = feature_engineer.prepare_data_multi(
                raw_data, params['features'], params['horizon'],
                params['lower_q'], params['upper_q'],
                normalize=False, stock_code=stock_code, data_source=params.get('data_source', 'csv')
            )
        else:
            X, y = feature_engineer.prepare_data(
                raw_data, params['features'], params['horizon'], params['threshold'],
                normalize=False, stock_code=stock_code, data_source=params.get('data_source', 'csv')
            )

        if X is None or len(X) < 50:
            return None

        return {
            'stock_code': stock_code,
            'X': X,
            'y': y,
            'sample_count': len(X)
        }

    except Exception as e:
        print(f'[多进程] {stock_code} 处理失败: {e}')
        return None


def parallel_train(stock_list, params, task_id=None, training_tasks=None):
    """多进程训练 - 在后台线程中完成整个训练流程"""
    from ml import ModelTrainer, ModelRegistry

    trainer = ModelTrainer()
    registry = ModelRegistry()

    total_stocks = len(stock_list)

    if task_id and training_tasks:
        training_tasks[task_id] = {
            'progress': 5,
            'status': 'running',
            'message': f'使用多进程处理 {total_stocks} 只股票'
        }
        print(f'[多进程训练] 任务ID: {task_id} - 启动多进程处理')

    start_time = time.time()
    tasks = [(stock, params) for stock in stock_list]

    cpu_count = os.cpu_count() or 4
    num_processes = int(max(1, min(cpu_count / 2, len(stock_list))))
    print(f'[多进程训练] CPU核心: {cpu_count}，使用 {num_processes} 个进程处理 {len(stock_list)} 只股票')

    completed = [0]
    total = len(tasks)

    results = []
    with Pool(processes=num_processes) as pool:
        for result in pool.imap_unordered(_process_single_stock, tasks):
            completed[0] += 1
            if task_id and training_tasks:
                progress = int(5 + (completed[0] / total) * 50)
                training_tasks[task_id] = {
                    'progress': progress,
                    'status': "running",
                    'message': f'已处理 {completed[0]}/{total} 只股票'
                }
                if training_tasks[task_id].get('stopped', False):
                    print(f'[多进程训练] 收到停止信号，终止进程池')
                    pool.terminate()
                    pool.join()
                    training_tasks[task_id] = {
                        'progress': 0,
                        'status': 'completed',
                        'message': '用户手动停止'
                    }
                    return
            results.append(result)

    process_time = time.time() - start_time
    print(f'[多进程训练] 所有股票处理完成，耗时: {process_time:.2f}秒')

    all_X = []
    all_y = []
    stock_sample_counts = {}

    # 按股票代码排序，确保数据顺序一致（多进程返回顺序不确定）
    sorted_results = sorted([r for r in results if r], key=lambda x: x.get('stock_code', ''))
    
    for result in sorted_results:
        stock_sample_counts[result['stock_code']] = result['sample_count']
        all_X.append(result['X'])
        all_y.append(result['y'])

    if not all_X:
        if task_id and training_tasks:
            training_tasks[task_id] = {
                'progress': 0,
                'status': 'completed',
                'message': '没有足够的有效数据'
            }
        return

    if task_id and training_tasks:
        training_tasks[task_id] = {
            'progress': 55,
            'status': 'running',
            'message': f'成功处理 {len(all_X)} 只股票，合并特征数据'
        }

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)

    total_samples = len(X)
    total_time = time.time() - start_time
    print(f'[多进程训练] 数据合并完成，总样本: {total_samples}，总耗时: {total_time:.2f}秒')
    print(f'[多进程训练] 股票样本分布: {stock_sample_counts}')

    normalize = params.get('normalize', False)
    
    if normalize:
        if task_id and training_tasks:
            training_tasks[task_id] = {
                'progress': 58,
                'status': 'running',
                'message': f'对 {X.shape[1]} 个特征进行归一化'
            }

        from sklearn.preprocessing import StandardScaler
        import numpy as np
        
        feature_names = list(X.columns)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=feature_names)
        
        scaler_params = {
            'mean': scaler.mean_.tolist(),
            'scale': scaler.scale_.tolist(),
            'n_features_in_': scaler.n_features_in_,
            'feature_names': feature_names
        }
        print(f'[多进程训练] 归一化完成，特征数: {scaler.n_features_in_}, 特征: {len(feature_names)}')
    else:
        print(f'[多进程训练] 跳过特征归一化')
        scaler_params = None

    mode = params.get('mode', 'classification')
    use_ensemble = params.get('use_ensemble', False)
    model_type = params.get('model_type', 'RandomForest')
    model_name = params.get('model_name')
    features = params.get('features', [])
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    horizon = params.get('horizon', 5)
    threshold = params.get('threshold', 0.02)
    label_type = params.get('label_type', 'fixed')
    vol_window = params.get('vol_window', 20)
    lower_q = params.get('lower_q', 0.2)
    upper_q = params.get('upper_q', 0.8)

    label_short = {
        'fixed': 'fix',
        'volatility': 'vol',
        'multi': 'mul',
        'regression': 'reg'
    }.get(label_type, label_type[:3] if label_type else 'fix')

    if task_id and training_tasks:
        training_tasks[task_id] = {
            'progress': 65,
            'status': 'running',
            'message': f'总样本数: {total_samples}，来自 {len(stock_sample_counts)} 只股票'
        }

    if use_ensemble:
        print(f'[多进程训练] 任务ID: {task_id} - 集成训练模式')
        result = trainer.train_ensemble(X, y, mode=mode)
        print(f'[多进程训练] 任务ID: {task_id} - 集成训练完成, 指标: {result["test_metrics"]}')

        if task_id and training_tasks:
            training_tasks[task_id] = {'progress': 80, 'status': '保存模型...',
                'message': '正在保存子模型'}

        import uuid
        model_id = str(uuid.uuid4())[:8]
        parent_id = str(uuid.uuid4())
        stock_display = f'{len(stock_sample_counts)}只股票'
        base_name = model_name or f'{params["market"]}_{params["period"]}_ENS_{params["end_date"]}_{len(features)}f_{params["horizon"]}h_{label_short}_{params["threshold"]}t_{params["vol_window"]}v_{total_stocks}stocks'
        trained_models = []
        for i, model_key in enumerate(result['models'].keys()):
            if task_id and training_tasks:
                training_tasks[task_id] = {'progress': 85 + i*5, 'status': 'running',
                    'message': f'正在保存 {model_key} ({i+1}/{len(result["models"])})'}
            print(f'[多进程训练] 任务ID: {task_id} - 保存 {model_key} ({i+1}/{len(result["models"])})')
            model_obj = result['models'][model_key]
            sub_filename = f'{base_name}_{model_key}_{model_id}_{i}.pkl'
            sub_filepath = trainer.save_model(model_obj, sub_filename)
            sub_metric = result['test_metrics'].get(model_key, {})
            sub_model_info = registry.register_model(
                stock_code=stock_display,
                model_name=sub_filename.replace('.pkl', ''),
                start_date=start_date,
                end_date=end_date,
                model_type=model_key,
                features=features,
                file_path=sub_filepath,
                metrics=sub_metric,
                scaler_params=scaler_params,
                label_type=label_type,
                horizon=horizon,
                threshold=threshold,
                vol_window=vol_window,
                lower_q=lower_q,
                upper_q=upper_q,
                mode=mode,
                is_ensemble=True,
                parent_model_id=parent_id
            )
            trained_models.append(sub_model_info)

        if task_id and training_tasks:
            training_tasks[task_id] = {'progress': 100, 'status': 'running', 'message': '训练完成!'}
        print(f'[多进程训练] 任务ID: {task_id} - 集成训练完成, 保存了{len(trained_models)}个子模型')
        
        return {'model_id': parent_id, 'model_info': {'id': parent_id, 'type': 'ensemble', 'sub_models': trained_models}}

    else:
        print(f'[多进程训练] 任务ID: {task_id} - 单模型训练模式, 模型: {model_type}')
        result = trainer.train_with_split(X, y, model_type, mode=mode)
        print(f'[多进程训练] 任务ID: {task_id} - 模型训练完成, 指标: {result["test_metrics"]}')

        if task_id and training_tasks:
            training_tasks[task_id] = {'progress': 80, 'status': 'running', 'message': '正在保存模型'}

        import uuid
        model_id = str(uuid.uuid4())[:8]
        stock_display = f'{len(stock_sample_counts)}只股票'
        if not model_name:
            if mode == 'regression':
                main_metric = result['test_metrics']['r2']
            else:
                main_metric = result['test_metrics']['accuracy']
            model_name = f'{params["market"]}_{params["period"]}_{model_type}_{params["end_date"]}_{len(features)}f_{params["horizon"]}h_{label_short}_{params["threshold"]}t_{params["vol_window"]}v_{total_stocks}stocks_{main_metric:.2f}'
            model_name = f'{model_name}_{model_id}'

        filename = f'{model_name}.pkl'
        filepath = trainer.save_model(result['model'], filename)

        model_info = registry.register_model(
            stock_code=stock_display,
            model_name=model_name,
            start_date=start_date,
            end_date=end_date,
            model_type=model_type,
            features=features,
            file_path=filepath,
            metrics=result['test_metrics'],
            scaler_params=scaler_params,
            label_type=label_type,
            horizon=horizon,
            threshold=threshold,
            vol_window=vol_window,
            lower_q=lower_q,
            upper_q=upper_q,
            mode=mode,
            is_ensemble=False
        )

        if task_id and training_tasks:
            training_tasks[task_id] = {'progress': 100, 'status': 'completed', 'message': '训练完成!'}
        print(f'[多进程训练] 任务ID: {task_id} - 单模型训练完成, 模型已保存: {filename}')

    print(f'[多进程训练] 任务ID: {task_id} - 全部完成，总耗时: {time.time() - start_time:.2f}秒')
    
    return {'model_id': model_info.get('id'), 'model_info': model_info}


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

    parallel_train(stock_list, params)
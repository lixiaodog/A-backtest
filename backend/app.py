import re
import importlib
import inspect
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.utils import secure_filename
import threading
import traceback
import uuid
import sys
import os
import pandas as pd
import backtrader as bt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.backtest.data_handler import get_astock_hist_data, load_csv_data, AStockData
from backend.backtest.engine import AStockBacktestEngine


def _log(message, level='INFO'):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f'[{timestamp}] [{level}] {message}')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'backtrader-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def scan_strategies():
    strategies_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'strategies')
    strategies = []
    _strategy_mtimes = getattr(scan_strategies, '_mtimes', {})

    if not os.path.exists(strategies_dir):
        return strategies

    for filename in os.listdir(strategies_dir):
        if not filename.endswith('.py') or filename.startswith('__'):
            continue

        module_name = filename[:-3]
        strategy_id = module_name
        filepath = os.path.join(strategies_dir, filename)
        mtime = os.path.getmtime(filepath)

        try:
            if module_name in sys.modules:
                old_mtime = _strategy_mtimes.get(module_name, 0)
                if mtime > old_mtime:
                    importlib.reload(sys.modules[f'strategies.{module_name}'])
            else:
                importlib.import_module(f'strategies.{module_name}')

            _strategy_mtimes[module_name] = mtime
            scan_strategies._mtimes = _strategy_mtimes

            module = sys.modules[f'strategies.{module_name}']

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if name.endswith('Strategy') and name != 'BaseStrategy' and name != 'bt.Strategy':
                    cls = obj

                    name_attr = getattr(cls, 'name', None)
                    desc_attr = getattr(cls, 'description', None)

                    strategy_name = name_attr if name_attr else strategy_id.replace('_', ' ').title()
                    strategy_desc = desc_attr if desc_attr else ''

                    params = []
                    if hasattr(cls, 'params'):
                        try:
                            param_info = getattr(cls, 'params', None)
                            if param_info is None:
                                continue
                            param_names = [x for x in dir(param_info) if not x.startswith('_') and x not in ('isdefault', 'notdefault', 'printlog')]
                            for param_name in param_names:
                                if param_name in ('printlog',):
                                    continue
                                try:
                                    default_value = getattr(param_info, param_name)
                                    if callable(default_value):
                                        default_value = default_value()
                                except:
                                    default_value = None
                                if default_value is None:
                                    continue
                                if isinstance(default_value, tuple):
                                    default_value = default_value[0]
                                param_type = 'int' if isinstance(default_value, int) else 'float' if isinstance(default_value, float) else 'str'
                                params.append({
                                    'name': param_name,
                                    'label': param_name.replace('_', ' ').title(),
                                    'type': param_type,
                                    'default': default_value
                                })
                        except Exception as e:
                            print(f"[DEBUG] Error processing params: {e}")

                    strategies.append({
                        'id': strategy_id,
                        'name': strategy_name,
                        'description': strategy_desc,
                        'class': cls,
                        'params': params
                    })
        except Exception as e:
            print(f"Error loading strategy {module_name}: {e}")

    return strategies

scan_strategies._mtimes = {}

STRATEGY_REGISTRY = scan_strategies()
STRATEGY_MAP = {s['id']: s['class'] for s in STRATEGY_REGISTRY}

def watch_strategies_folder():
    while True:
        time.sleep(2)
        try:
            global STRATEGY_REGISTRY, STRATEGY_MAP
            new_registry = scan_strategies()
            old_ids = set(s['id'] for s in STRATEGY_REGISTRY)
            new_ids = set(s['id'] for s in new_registry)
            if old_ids != new_ids or len(new_registry) != len(STRATEGY_REGISTRY):
                STRATEGY_REGISTRY = new_registry
                STRATEGY_MAP = {s['id']: s['class'] for s in STRATEGY_REGISTRY}
                print(f"[策略热更新] 检测到策略变更，当前策略数: {len(STRATEGY_REGISTRY)}")
        except Exception as e:
            print(f"[策略监控] Error: {e}")

watcher_thread = threading.Thread(target=watch_strategies_folder, daemon=True)
watcher_thread.start()

tasks = {}
training_tasks = {}
training_threads = {}
task_queue = []
queue_running = False

backtest_tasks = tasks

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    try:
        df = load_csv_data(filepath)
        return jsonify({
            'filename': filename,
            'rows': len(df),
            'start_date': str(df.index[0].date()) if len(df) > 0 else None,
            'end_date': str(df.index[-1].date()) if len(df) > 0 else None,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest', methods=['POST'])
def submit_backtest():
    data = request.json
    task_id = str(uuid.uuid4())
    client_id = data.get('client_id', 'default')
    print(f"[回测请求] task_id={task_id}, params={data}")

    task = {
        'id': task_id,
        'status': 'pending',
        'params': data,
        'result': None,
        'engine': None,
        'client_id': client_id
    }
    tasks[task_id] = task

    thread = threading.Thread(target=run_backtest, args=(task_id, data, client_id))
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'running'})

@app.route('/api/backtest/<task_id>', methods=['GET'])
def get_backtest_result(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(tasks[task_id])

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    return jsonify([{
        'id': s['id'],
        'name': s['name'],
        'description': s['description'],
        'params': s['params']
    } for s in STRATEGY_REGISTRY])

@app.route('/api/strategies/refresh', methods=['POST'])
def refresh_strategies():
    global STRATEGY_REGISTRY, STRATEGY_MAP
    STRATEGY_REGISTRY = scan_strategies()
    STRATEGY_MAP = {s['id']: s['class'] for s in STRATEGY_REGISTRY}
    return jsonify([{'id': s['id'], 'name': s['name']} for s in STRATEGY_REGISTRY])

@app.route('/api/strategy-manager/list', methods=['GET'])
def get_strategy_manager_list():
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    strategies = manager.get_all_strategies()
    return jsonify(strategies)

@app.route('/api/strategy-manager/<strategy_id>', methods=['GET'])
def get_strategy_manager_detail(strategy_id):
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    strategy = manager.get_strategy_by_id(strategy_id)
    if strategy:
        return jsonify(strategy)
    return jsonify({'error': 'Strategy not found'}), 404

@app.route('/api/strategy-manager', methods=['POST'])
def create_strategy_manager_strategy():
    from strategy_manager import StrategyManager
    try:
        data = request.json
        manager = StrategyManager()
        strategy = manager.create_strategy(data)
        return jsonify({'status': 'created', 'strategy': strategy}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/strategy-manager/<strategy_id>', methods=['PUT'])
def update_strategy_manager_strategy(strategy_id):
    from strategy_manager import StrategyManager
    try:
        data = request.json
        manager = StrategyManager()
        strategy = manager.update_strategy(strategy_id, data)
        if strategy:
            return jsonify({'status': 'updated', 'strategy': strategy})
        return jsonify({'error': 'Strategy not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/strategy-manager/<strategy_id>', methods=['DELETE'])
def delete_strategy_manager_strategy(strategy_id):
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    if manager.delete_strategy(strategy_id):
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Strategy not found'}), 404

@app.route('/api/strategy-manager/templates', methods=['GET'])
def get_strategy_templates():
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    templates = manager.get_templates()
    return jsonify(templates)

@app.route('/api/strategy-manager/template/<template_id>', methods=['GET'])
def get_strategy_template_detail(template_id):
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    template = manager.get_template(template_id)
    if template:
        return jsonify(template)
    return jsonify({'error': 'Template not found'}), 404

@app.route('/api/strategy-manager/<strategy_id>/code', methods=['GET'])
def get_strategy_code(strategy_id):
    from strategy_manager import StrategyManager
    manager = StrategyManager()
    code = manager.export_strategy_code(strategy_id)
    if code:
        return jsonify({'code': code})
    return jsonify({'error': 'Strategy not found'}), 404

@app.route('/api/chart/<filename>')
def serve_chart(filename):
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
    return send_from_directory(results_dir, filename)

def _run_training_task(task_id, stock_list, market, period, model_name, start_date, end_date,
                        model_type, features, horizon, threshold, label_type, vol_window,
                        lower_q, upper_q, mode, use_ensemble, total_stocks, prepare_func,
                        task_index=0, total_tasks=1, data_source='csv', use_gpu=False, fast_mode=False, normalize=False):
    """后台线程执行单个训练任务"""
    from backend.ml import ModelTrainer, ModelRegistry
    from backend.ml.model_naming import generate_model_name
    from backend.pipeline import TrainingPipeline

    def progress_callback(message, progress=None):
        if task_id in training_tasks:
            current = training_tasks[task_id]
            training_tasks[task_id] = {
                'progress': progress if progress is not None else current.get('progress', 65),
                'status': current.get('status', 'running'),
                'message': f'任务 {task_index + 1}/{total_tasks}: {message}',
                'current_task_index': task_index,
                'total_tasks': total_tasks
            }

    trainer = ModelTrainer(progress_callback=progress_callback)
    registry = ModelRegistry()

    # 更新任务状态，包含当前任务序号
    training_tasks[task_id] = {
        'progress': 5,
        'status': 'running',
        'message': f'任务 {task_index + 1}/{total_tasks}: 将处理 {total_stocks} 只股票',
        'current_task_index': task_index,
        'total_tasks': total_tasks
    }
    _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 将处理 {total_stocks} 只股票')

    pipeline = TrainingPipeline(
        stock_list=stock_list,
        task_id=task_id,
        prepare_func=prepare_func,
        features=features,
        horizon=horizon,
        threshold=threshold,
        vol_window=vol_window,
        lower_q=lower_q,
        upper_q=upper_q,
        start_date=start_date,
        end_date=end_date,
        period=period,
        market=market,
        mode=mode,
        training_tasks=training_tasks,
        progress_offset=5,
        progress_scale=0.55,
        data_source=data_source,
        use_gpu=use_gpu,
        fast_mode=fast_mode,
        normalize=normalize
    )

    # 检查任务是否被停止
    if task_id in training_tasks and training_tasks[task_id].get('stopped'):
        _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
        return
    
    try:
        pipeline_result = pipeline.run()
    except Exception as e:
        _log(f'[训练任务] 任务ID: {task_id} - 管道执行失败: {e}', 'ERROR')
        traceback.print_exc()
        if task_id in training_tasks:
            training_tasks[task_id] = {'progress': 0, 'status': 'failed', 'message': str(e)}
        return
    
    # 检查任务是否被停止
    if task_id in training_tasks and training_tasks[task_id].get('stopped'):
        _log(f'[训练任务] 任务ID: {task_id} - 任务已被停止')
        return

    if not pipeline_result:
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 没有足够的有效数据', 'WARN')
        if task_id in training_tasks:
            training_tasks[task_id] = {
                'progress': 0,
                'status': 'failed',
                'message': f'任务 {task_index + 1}/{total_tasks}: 没有足够的有效数据',
                'current_task_index': task_index,
                'total_tasks': total_tasks
            }
        return

    all_X = pipeline_result['all_X']
    all_y = pipeline_result['all_y']
    stock_sample_counts = pipeline_result['stock_sample_counts']
    scaler_params = pipeline_result['scaler_params']

    if not all_X:
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 没有足够的有效数据', 'WARN')
        if task_id in training_tasks:
            training_tasks[task_id] = {
                'progress': 0,
                'status': 'failed',
                'message': f'任务 {task_index + 1}/{total_tasks}: 没有足够的有效数据',
                'current_task_index': task_index,
                'total_tasks': total_tasks
            }
        return

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)

    if task_id in training_tasks:
        training_tasks[task_id] = {
            'progress': 65,
            'status': 'running',
            'message': f'任务 {task_index + 1}/{total_tasks}: 总样本数: {len(X)}，来自 {len(stock_sample_counts)} 只股票',
            'current_task_index': task_index,
            'total_tasks': total_tasks
        }
    _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 开始训练模型, 总样本数: {len(X)}')

    import uuid
    from datetime import datetime
    
    model_id = str(uuid.uuid4())[:8]
    stock_display = f'{len(stock_sample_counts)}只股票'
    
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')

    parent_id = str(uuid.uuid4())

    if use_ensemble:
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 集成训练模式')
        result = trainer.train_ensemble(X, y, mode=mode, use_gpu=use_gpu, fast_mode=fast_mode)
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 集成训练完成')

        training_tasks[task_id] = {
            'progress': 80,
            'status': 'running',
            'message': f'任务 {task_index + 1}/{total_tasks}: 正在保存子模型',
            'current_task_index': task_index,
            'total_tasks': total_tasks
        }
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 正在保存子模型...')

        parent_id = str(uuid.uuid4())[:8]
        trained_models = []
        for i, model_key in enumerate(result['models'].keys()):
            training_tasks[task_id] = {
                'progress': 85 + i*5,
                'status': 'running',
                'message': f'任务 {task_index + 1}/{total_tasks}: 正在保存 {model_key} ({i+1}/{len(result["models"])})',
                'current_task_index': task_index,
                'total_tasks': total_tasks
            }
            _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 保存 {model_key} ({i+1}/{len(result["models"])})')
            model_obj = result['models'][model_key]
            sub_filename = generate_model_name(
                market=market,
                period=period,
                model_type=model_key,
                end_date=end_date,
                feature_count=len(features),
                horizon=horizon,
                label_type=label_type,
                threshold=threshold,
                vol_window=vol_window,
                stock_count=total_stocks,
                is_ensemble=True,
                ensemble_id=parent_id,
                ensemble_index=i
            ) + '.pkl'
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
                is_ensemble=False,
                parent_model_id=parent_id
            )
            trained_models.append(sub_model_info)
        training_tasks[task_id] = {
            'progress': 100,
            'status': 'completed',
            'message': f'任务 {task_index + 1}/{total_tasks}: 训练完成!',
            'current_task_index': task_index,
            'total_tasks': total_tasks
        }
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 集成训练完成, 保存了{len(trained_models)}个子模型')
    else:
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 单模型训练模式, 模型: {model_type}')
        result = trainer.train_with_split(X, y, model_type, mode=mode, use_gpu=use_gpu, fast_mode=fast_mode)
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 模型训练完成')

        training_tasks[task_id] = {
            'progress': 80,
            'status': 'running',
            'message': f'任务 {task_index + 1}/{total_tasks}: 正在保存模型',
            'current_task_index': task_index,
            'total_tasks': total_tasks
        }
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 正在保存模型...')

        if not model_name:
            if mode == 'regression':
                main_metric = result['test_metrics']['r2']
            else:
                main_metric = result['test_metrics']['accuracy']
            model_name = generate_model_name(
                market=market,
                period=period,
                model_type=model_type,
                end_date=end_date,
                feature_count=len(features),
                horizon=horizon,
                label_type=label_type,
                threshold=threshold,
                vol_window=vol_window,
                stock_count=total_stocks,
                metric=main_metric,
                ensemble_id=task_id
            )

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

        training_tasks[task_id] = {
            'progress': 100,
            'status': 'completed',
            'message': f'任务 {task_index + 1}/{total_tasks}: 训练完成!',
            'current_task_index': task_index,
            'total_tasks': total_tasks
        }
        _log(f'[训练任务] 任务ID: {task_id} - 任务 {task_index + 1}/{total_tasks}: 单模型训练完成, 模型已保存: {filename}')


def _run_task_queue():
    """顺序执行任务队列中的所有任务"""
    global queue_running
    import time
    
    queue_running = True
    _log(f'[任务队列] 开始执行任务队列，共 {len(task_queue)} 个任务')
    
    while task_queue:
        task_id = task_queue[0]
        task_data = training_tasks.get(task_id)
        
        if not task_data:
            task_queue.pop(0)
            continue
        
        if task_data.get('status') == 'stopped':
            _log(f'[任务队列] 任务 {task_id} 已停止，跳过')
            task_queue.pop(0)
            continue
        
        _log(f'[任务队列] 开始执行任务: {task_id}')
        training_tasks[task_id]['status'] = 'running'
        training_tasks[task_id]['message'] = '正在训练...'
        
        try:
            _run_single_training_task(task_id, task_data)
        except Exception as e:
            _log(f'[任务队列] 任务 {task_id} 执行失败: {e}', 'ERROR')
            if task_id in training_tasks:
                training_tasks[task_id]['status'] = 'failed'
                training_tasks[task_id]['message'] = str(e)
        
        task_queue.pop(0)
        _log(f'[任务队列] 任务 {task_id} 执行完成，剩余 {len(task_queue)} 个任务')
    
    queue_running = False
    _log(f'[任务队列] 所有任务执行完成')


def _run_single_training_task(task_id, task_data):
    """执行单个训练任务"""
    import time
    start_time = time.time()
    
    stock_list = task_data.get('stock', [])
    if isinstance(stock_list, str):
        stock_list = [stock_list]
    
    market = task_data.get('market', 'SZ')
    period = task_data.get('period', '1d')
    model_name = task_data.get('model_name')
    end_date = task_data.get('end_date')
    model_type = task_data.get('model_type', 'RandomForest')
    features = task_data.get('features', [])
    horizon = task_data.get('horizon', 5)
    threshold = task_data.get('threshold', 0.02)
    label_type = task_data.get('label_type', 'fixed')
    vol_window = task_data.get('vol_window', 20)
    lower_q = task_data.get('lower_q', 0.2)
    upper_q = task_data.get('upper_q', 0.8)
    mode = task_data.get('mode', 'classification')
    use_ensemble = task_data.get('use_ensemble', False)
    train_mode = task_data.get('train_mode', 'thread')
    data_source = task_data.get('data_source', 'csv')
    use_gpu = task_data.get('use_gpu', False)
    fast_mode = task_data.get('fast_mode', False)
    
    if label_type == 'regression' or mode == 'regression':
        prepare_func = 'prepare_data_regression'
        mode = 'regression'
        label_type = 'regression'
    elif label_type == 'volatility':
        prepare_func = 'prepare_data_with_volatility'
    elif label_type == 'multi':
        prepare_func = 'prepare_data_multi'
    else:
        prepare_func = 'prepare_data'
    
    try:
        if train_mode == 'process':
            from backend.parallel_train import parallel_train
            result = parallel_train(
                stock_list=stock_list,
                params={
                    'start_date': None,
                    'end_date': end_date,
                    'period': period,
                    'market': market,
                    'features': features,
                    'horizon': horizon,
                    'threshold': threshold,
                    'prepare_func': prepare_func,
                    'vol_window': vol_window,
                    'lower_q': lower_q,
                    'upper_q': upper_q,
                    'model_type': model_type,
                    'use_ensemble': use_ensemble,
                    'task_id': task_id,
                    'training_tasks': training_tasks,
                    'mode': mode,
                    'model_name': model_name,
                    'data_source': data_source,
                    'use_gpu': use_gpu,
                    'fast_mode': fast_mode,
                    'label_type': label_type,
                    'normalize': task_data.get('normalize', False)
                },
                task_id=task_id,
                training_tasks=training_tasks
            )
        else:
            _run_training_task(
                task_id=task_id,
                stock_list=stock_list,
                market=market,
                period=period,
                model_name=model_name,
                start_date=None,
                end_date=end_date,
                model_type=model_type,
                features=features,
                horizon=horizon,
                threshold=threshold,
                label_type=label_type,
                vol_window=vol_window,
                lower_q=lower_q,
                upper_q=upper_q,
                mode=mode,
                use_ensemble=use_ensemble,
                total_stocks=len(stock_list),
                prepare_func=prepare_func,
                data_source=data_source,
                use_gpu=use_gpu,
                fast_mode=fast_mode,
                normalize=task_data.get('normalize', False)
            )
            return
        
    except Exception as e:
        _log(f'[训练任务] 任务ID: {task_id} - 失败: {e}', 'ERROR')
        traceback.print_exc()
        if task_id in training_tasks:
            training_tasks[task_id]['status'] = 'failed'
            training_tasks[task_id]['message'] = str(e)


def _run_training_tasks(task_id, tasks):
    """顺序执行多个训练任务，支持多线程/多进程模式"""
    import time
    total_tasks = len(tasks)
    start_time = time.time()
    _log(f'[训练队列] 任务ID: {task_id} - 开始执行 {total_tasks} 个训练任务')
    
    # 收集所有股票
    all_stocks = []
    for task in tasks:
        stock_list = task.get('stock', [])
        if isinstance(stock_list, str):
            stock_list = [stock_list]
        all_stocks.extend(stock_list)
    
    # 获取训练模式
    train_mode = tasks[0].get('train_mode', 'thread') if tasks else 'thread'

    training_tasks[task_id] = {
        'progress': 0,
        'status': 'running',
        'message': f'共 {total_tasks} 个任务，准备开始...',
        'current_task_index': 0,
        'total_tasks': total_tasks,
        'start_time': start_time,
        'type': 'batch',
        'train_mode': train_mode,
        'stocks': all_stocks,
        'success_count': 0,
        'fail_count': 0,
        'params': tasks[0] if tasks else {}
    }

    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks):
        _log(f'[训练队列] 任务ID: {task_id} - 开始第 {i + 1}/{total_tasks} 个任务')

        # 提取任务参数
        stock_list = task.get('stock', [])
        if isinstance(stock_list, str):
            stock_list = [stock_list]

        market = task.get('market', 'SZ')
        period = task.get('period', '1d')
        model_name = task.get('model_name')
        end_date = task.get('end_date')
        model_type = task.get('model_type', 'RandomForest')
        features = task.get('features', [])
        horizon = task.get('horizon', 5)
        _log(f'[训练队列] 任务 {i+1}/{total_tasks}: market={market}, horizon={horizon}, model_name={model_name}')
        threshold = task.get('threshold', 0.02)
        label_type = task.get('label_type', 'fixed')
        vol_window = task.get('vol_window', 20)
        lower_q = task.get('lower_q', 0.2)
        upper_q = task.get('upper_q', 0.8)
        mode = task.get('mode', 'classification')
        use_ensemble = task.get('use_ensemble', False)
        train_mode = task.get('train_mode', 'thread')  # 获取训练模式
        data_source = task.get('data_source', 'csv')  # 获取数据源
        use_gpu = task.get('use_gpu', False)  # 获取GPU加速选项
        fast_mode = task.get('fast_mode', False)  # 获取快速训练选项

        # 确定 prepare_func
        if label_type == 'regression' or mode == 'regression':
            prepare_func = 'prepare_data_regression'
            mode = 'regression'
            label_type = 'regression'
        elif label_type == 'volatility':
            prepare_func = 'prepare_data_with_volatility'
        elif label_type == 'multi':
            prepare_func = 'prepare_data_multi'
        else:
            prepare_func = 'prepare_data'

        try:
            if train_mode == 'process':
                # 多进程模式
                _log(f'[训练队列] 任务ID: {task_id} - 第 {i + 1}/{total_tasks} 个任务使用多进程模式')
                from backend.parallel_train import parallel_train
                parallel_train(
                    stock_list=stock_list,
                    params={
                        'start_date': None,
                        'end_date': end_date,
                        'period': period,
                        'market': market,
                        'features': features,
                        'horizon': horizon,
                        'threshold': threshold,
                        'prepare_func': prepare_func,
                        'vol_window': vol_window,
                        'lower_q': lower_q,
                        'upper_q': upper_q,
                        'model_type': model_type,
                        'use_ensemble': use_ensemble,
                        'task_id': task_id,
                        'training_tasks': training_tasks,
                        'mode': mode,
                        'model_name': model_name,
                        'label_type': label_type,
                        'data_source': data_source
                    },
                    task_id=task_id,
                    training_tasks=training_tasks
                )
            else:
                # 多线程模式（默认）
                _run_training_task(
                    task_id=task_id,
                    stock_list=stock_list,
                    market=market,
                    period=period,
                    model_name=model_name,
                    start_date=None,
                    end_date=end_date,
                    model_type=model_type,
                    features=features,
                    horizon=horizon,
                    threshold=threshold,
                    label_type=label_type,
                    vol_window=vol_window,
                    lower_q=lower_q,
                    upper_q=upper_q,
                    mode=mode,
                    use_ensemble=use_ensemble,
                    total_stocks=len(stock_list),
                    prepare_func=prepare_func,
                    task_index=i,
                    total_tasks=total_tasks,
                    data_source=data_source,
                    use_gpu=use_gpu,
                    fast_mode=fast_mode
                )
            success_count += 1
            _log(f'[训练队列] 任务ID: {task_id} - 第 {i + 1}/{total_tasks} 个任务完成')
        except Exception as e:
            fail_count += 1
            _log(f'[训练队列] 任务ID: {task_id} - 第 {i + 1}/{total_tasks} 个任务失败: {e}', 'ERROR')
            traceback.print_exc()

    # 所有任务完成
    final_progress = 100 if fail_count == 0 else int((success_count / total_tasks) * 100)
    training_tasks[task_id] = {
        'progress': final_progress,
        'status': 'completed' if fail_count == 0 else 'partial',
        'message': f'所有任务完成: {success_count}/{total_tasks} 成功, {fail_count}/{total_tasks} 失败',
        'current_task_index': total_tasks - 1,
        'total_tasks': total_tasks
    }
    _log(f'[训练队列] 任务ID: {task_id} - 所有 {total_tasks} 个任务执行完毕: {success_count} 成功, {fail_count} 失败')


@app.route('/api/ml/train', methods=['POST'])
def ml_train():
    task_id = uuid.uuid4().hex[:8]
    training_tasks[task_id] = {'progress': 0, 'status': 'running', 'message': ''}
    _log(f'[训练] 任务ID: {task_id} - 开始训练')

    try:
        from backend.ml.model_naming import generate_model_name
        data = request.json
        stock_param = data.get('stock_code') or data.get('stock') or data.get('stocks')
        market = data.get('market', 'SZ')
        period = data.get('period', '1d')
        model_name = data.get('model_name')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        model_type = data.get('model_type', 'RandomForest')
        features = data.get('features', [])
        horizon = data.get('horizon', 5)
        threshold = data.get('threshold', 0.02)
        label_type = data.get('label_type', 'fixed')
        vol_window = data.get('vol_window', 20)
        lower_q = data.get('lower_q', 0.2)
        upper_q = data.get('upper_q', 0.8)
        mode = data.get('mode', 'classification')
        use_ensemble = data.get('use_ensemble', False)
        train_mode = data.get('train_mode', 'thread')

        _log(f'[训练] 任务ID: {task_id} - 参数: stock={stock_param}, market={market}, period={period}, horizon={horizon}, use_ensemble={use_ensemble}, train_mode={train_mode}')

        is_multiple_stocks = isinstance(stock_param, list)
        stock_list = stock_param if is_multiple_stocks else [stock_param]
        total_stocks = len(stock_list)

        if label_type == 'regression' or mode == 'regression':
            prepare_func = 'prepare_data_regression'
            mode = 'regression'
            label_type = 'regression'
        elif label_type == 'volatility':
            prepare_func = 'prepare_data_with_volatility'
        elif label_type == 'multi':
            prepare_func = 'prepare_data_multi'
        else:
            prepare_func = 'prepare_data'

        training_tasks[task_id] = {'progress': 5, 'status': 'running',
            'message': f'将{"多线程" if train_mode == "thread" else "多进程"}处理 {total_stocks} 只股票，训练统一模型'}
        _log(f'[训练] 任务ID: {task_id} - 将{"多线程" if train_mode == "thread" else "多进程"}处理 {total_stocks} 只股票')

        if train_mode == 'process':
            from backend.parallel_train import parallel_train
            thread = threading.Thread(
                target=parallel_train,
                args=(stock_list, {
                    'start_date': start_date,
                    'end_date': end_date,
                    'period': period,
                    'market': market,
                    'features': features,
                    'horizon': horizon,
                    'threshold': threshold,
                    'prepare_func': prepare_func,
                    'vol_window': vol_window,
                    'lower_q': lower_q,
                    'upper_q': upper_q,
                    'model_type': model_type,
                    'use_ensemble': use_ensemble,
                    'task_id': task_id,
                    'training_tasks': training_tasks,
                    'mode': mode
                }, task_id, training_tasks)
            )
        else:
            thread = threading.Thread(
                target=_run_training_task,
                args=(task_id, stock_list, market, period, model_name, start_date, end_date,
                      model_type, features, horizon, threshold, label_type, vol_window,
                      lower_q, upper_q, mode, use_ensemble, total_stocks, prepare_func)
            )
        thread.daemon = True
        training_threads[task_id] = thread
        thread.start()

        return jsonify({
            'status': 'started',
            'task_id': task_id,
            'message': '训练任务已启动'
        })

    except Exception as e:
        _log(f'[训练] 任务ID: {task_id} - 训练失败: {e}', 'ERROR')
        traceback.print_exc()
        if task_id in training_tasks:
            del training_tasks[task_id]
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/train/batch', methods=['POST'])
def ml_train_batch():
    """批量训练端点 - 接收任务列表，每个任务单独显示，顺序执行"""
    global queue_running
    
    try:
        data = request.json
        tasks = data.get('tasks', [])

        if not tasks or not isinstance(tasks, list):
            return jsonify({'error': '请提供任务列表 (tasks)'}), 400

        if len(tasks) == 0:
            return jsonify({'error': '任务列表不能为空'}), 400

        _log(f'[训练批量] 接收到 {len(tasks)} 个训练任务')
        
        task_ids = []
        for i, task in enumerate(tasks):
            task_id = uuid.uuid4().hex[:8]
            task_ids.append(task_id)
            
            stock_list = task.get('stock', [])
            if isinstance(stock_list, str):
                stock_list = [stock_list]
            
            training_tasks[task_id] = {
                'progress': 0,
                'status': 'pending',
                'message': f'等待中 (队列位置: {len(task_queue) + i + 1})',
                'stock': stock_list,
                'market': task.get('market', 'SZ'),
                'period': task.get('period', '1d'),
                'model_name': task.get('model_name'),
                'end_date': task.get('end_date'),
                'model_type': task.get('model_type', 'RandomForest'),
                'features': task.get('features', []),
                'horizon': task.get('horizon', 5),
                'threshold': task.get('threshold', 0.02),
                'label_type': task.get('label_type', 'fixed'),
                'vol_window': task.get('vol_window', 20),
                'lower_q': task.get('lower_q', 0.2),
                'upper_q': task.get('upper_q', 0.8),
                'mode': task.get('mode', 'classification'),
                'use_ensemble': task.get('use_ensemble', False),
                'train_mode': task.get('train_mode', 'thread'),
                'data_source': task.get('data_source', 'csv'),
                'use_gpu': task.get('use_gpu', False),
                'fast_mode': task.get('fast_mode', False),
                'normalize': task.get('normalize', False),
                'queue_position': len(task_queue) + i + 1
            }
            
            task_queue.append(task_id)
            _log(f'[训练批量] 任务 {i+1}/{len(tasks)} 已添加: {task_id}')
        
        if not queue_running:
            thread = threading.Thread(target=_run_task_queue)
            thread.daemon = True
            thread.start()

        return jsonify({
            'status': 'started',
            'task_ids': task_ids,
            'message': f'已添加 {len(tasks)} 个训练任务到队列'
        })

    except Exception as e:
        _log(f'[训练批量] 启动失败: {e}', 'ERROR')
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/train/incremental', methods=['POST'])
def ml_train_incremental():
    try:
        data = request.json
        base_model_id = data.get('base_model_id') or data.get('base_model')
        new_start_date = data.get('new_start_date')
        new_end_date = data.get('new_end_date')

        from backend.ml import MLDataLoader, FeatureEngineer, ModelTrainer, ModelRegistry

        registry = ModelRegistry()
        base_model_info = registry.get_model_by_id(base_model_id)
        if not base_model_info:
            return jsonify({'error': '基础模型不存在'}), 404

        data_loader = MLDataLoader()
        feature_engineer = FeatureEngineer()
        trainer = ModelTrainer()

        raw_data = data_loader.load_stock_data(
            base_model_info['stock_code'],
            new_start_date,
            new_end_date
        )

        X, y = feature_engineer.prepare_data(
            raw_data,
            base_model_info['features'],
            base_model_info.get('horizon', 5),
            base_model_info.get('threshold', 0.02)
        )

        mode = base_model_info.get('mode', 'classification')

        new_model = trainer.train_incremental(
            base_model_info['file_path'],
            X, y,
            base_model_info['model_type'],
            mode=mode
        )

        filename = f'{base_model_info["model_type"].lower()}_{base_model_info["stock_code"]}_inc_{uuid.uuid4().hex[:8]}.pkl'
        filepath = trainer.save_model(new_model, filename)

        new_incremental_info = {
            'start_date': new_start_date,
            'end_date': new_end_date,
            'trained_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        model_info = registry.register_model(
            stock_code=base_model_info['stock_code'],
            start_date=base_model_info['start_date'],
            end_date=new_end_date,
            model_type=base_model_info['model_type'],
            features=base_model_info['features'],
            file_path=filepath,
            metrics={},
            parent_model_id=base_model_id,
            incremental_data=new_incremental_info,
            scaler_params=base_model_info.get('scaler_params'),
            mode=mode,
            is_ensemble=base_model_info.get('is_ensemble', False)
        )

        return jsonify({
            'status': 'incremental_trained',
            'model': model_info
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/predict', methods=['POST'])
def ml_predict():
    try:
        data = request.json
        stock_codes = data.get('stocks') or [data.get('stock_code') or data.get('stock')]
        model_id = data.get('model_id')
        period = data.get('period', '1d')
        data_source = data.get('data_source', 'akshare')
        predict_date = data.get('predict_date')

        if not model_id:
            return jsonify({'error': '缺少模型ID'}), 400

        if not stock_codes or not stock_codes[0]:
            return jsonify({'error': '缺少股票代码'}), 400

        from backend.ml import FeatureEngineer, ModelTrainer, ModelRegistry
        from backend.ml.model_naming import generate_model_name

        registry = ModelRegistry()
        model_info = registry.get_model_by_id(model_id)
        if not model_info:
            model_info = registry.get_model_by_parent_id(model_id)
        if not model_info:
            sub_models = registry.get_models_by_parent_id(model_id)
            if sub_models:
                model_info = sub_models[0]
        if not model_info:
            return jsonify({'error': '模型不存在'}), 404

        threshold = data.get('threshold', model_info.get('threshold', 0.02))

        trainer = ModelTrainer()
        
        # 检查是否是集成模型
        is_ensemble = model_info.get('is_ensemble', False)
        sub_models_list = model_info.get('sub_models', [])
        
        model = None
        ensemble_models = None
        
        if is_ensemble and sub_models_list:
            # 集成模型：加载所有子模型
            ensemble_models = {}
            for sub in sub_models_list:
                sub_model_info = registry.get_model_by_id(sub['id'])
                if sub_model_info and sub_model_info.get('file_path'):
                    sub_model = trainer.load_model(sub_model_info['file_path'])
                    ensemble_models[sub['model_type']] = sub_model
            print(f'[预测] 集成模型，加载了 {len(ensemble_models)} 个子模型: {list(ensemble_models.keys())}')
        elif model_info.get('file_path'):
            # 单模型：直接加载
            model = trainer.load_model(model_info['file_path'])
        else:
            return jsonify({'error': '模型文件路径不存在'}), 404

        from backend.ml.predictors import Predictor

        mode = model_info.get('mode', 'classification')
        label_type = model_info.get('label_type', 'fixed')

        if mode == 'regression':
            label_type = 'regression'

        feature_engineer = FeatureEngineer()
        print(f'[预测] scaler_params from model: {model_info.get("scaler_params") is not None}')
        if model_info.get('scaler_params'):
            print(f'[预测] 调用set_scaler_params, mean[:3]: {model_info["scaler_params"].get("mean", [])[:3] if model_info["scaler_params"] else None}')
            feature_engineer.set_scaler_params(model_info['scaler_params'])
            print(f'[预测] set_scaler_params后 scaler_fitted: {feature_engineer._scaler_fitted}')

        model_name = model_info.get('model_name', '')

        # 如果前面没有加载集成模型，检查是否需要通过其他方式加载
        if not ensemble_models:
            parent_model_id = model_info.get('parent_model_id')
            
            if parent_model_id:
                all_models = registry.get_all_models()
                ensemble_models = {}
                
                for m in all_models:
                    if m.get('parent_model_id') == parent_model_id:
                        sub_model = trainer.load_model(m['file_path'])
                        ensemble_models[m['model_type']] = sub_model
                
                if len(ensemble_models) > 1:
                    print(f'[预测] 使用集成模式，加载了 {len(ensemble_models)} 个子模型: {list(ensemble_models.keys())}')
                else:
                    ensemble_models = None
            elif '_ENS_' in model_name or '_ensemble_' in model_name.lower():
                all_models = registry.get_all_models()
                ensemble_models = {}
                
                parts = model_name.rsplit('_', 2)
                if len(parts) >= 2:
                    ensemble_prefix = '_'.join(parts[:-2])
                else:
                    ensemble_prefix = model_name.rsplit('_', 1)[0]
                
                for m in all_models:
                    if m.get('parent_model_id') == model_info.get('id'):
                        sub_model = trainer.load_model(m['file_path'])
                        ensemble_models[m['model_type']] = sub_model
                    elif m['model_name'].startswith(ensemble_prefix + '_'):
                        sub_model = trainer.load_model(m['file_path'])
                        ensemble_models[m['model_type']] = sub_model
                
                if len(ensemble_models) > 1:
                    print(f'[预测] 使用集成模式，加载了 {len(ensemble_models)} 个子模型: {list(ensemble_models.keys())}')
                else:
                    ensemble_models = None

        from backend.providers import ProviderFactory
        from backend.config import DataSourceConfig
        
        if data_source == 'factor_cache':
            cache_config = DataSourceConfig.get_config('factor_cache')
            cache_path = cache_config.get('cache_path', './data/factor_cache/')
            raw_data_path = cache_config.get('raw_data_path', './data/')
            factor_library = cache_config.get('factor_library', 'alpha191')
            # 转换为绝对路径
            if not os.path.isabs(cache_path):
                cache_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', cache_path))
            if not os.path.isabs(raw_data_path):
                raw_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', raw_data_path))
            provider = ProviderFactory.create_provider(
                'factor_cache',
                cache_path=cache_path,
                raw_data_path=raw_data_path,
                factor_library=factor_library
            )
        else:
            from backend.akshare_data import get_realtime_data, get_stock_info
            provider = None

        results = []
        for stock_code in stock_codes:
            try:
                if data_source == 'factor_cache' and provider:
                    raw_data = provider.get_stock_data(
                        stock_code, 
                        period=period,
                        end_date=predict_date,
                        latest_only=True,
                        include_raw_data=False
                    )
                    stock_info = provider.get_stock_info(stock_code)
                    
                    if raw_data is None or raw_data.empty:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code),
                            'error': f'无法获取 {stock_code} 的因子数据'
                        })
                        continue
                    
                    import numpy as np
                    model_features = model_info.get('features', [])
                    available_features = [f for f in model_features if f in raw_data.columns]
                    
                    if not available_features:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code),
                            'error': f'{stock_code} 无可用特征'
                        })
                        continue
                    
                    # 从缓存获取的因子值已经是原始值，需要用训练时的全局 scaler 归一化
                    last_row = raw_data.iloc[-1:]
                    features = last_row[available_features].copy()
                    
                    if features.isnull().any().any():
                        features = features.fillna(0)
                    
                    # 用训练时保存的全局 scaler 参数归一化
                    scaler_params = model_info.get('scaler_params')
                    if scaler_params:
                        mean = np.array(scaler_params['mean'])
                        scale = np.array(scaler_params['scale'])
                        feature_order = scaler_params.get('feature_names', model_features)
                        
                        available_in_order = [f for f in feature_order if f in features.columns]
                        if available_in_order and len(mean) == len(feature_order) and len(scale) == len(feature_order):
                            features_ordered = features[available_in_order].values
                            scale_subset = np.array([scale[feature_order.index(f)] for f in available_in_order])
                            mean_subset = np.array([mean[feature_order.index(f)] for f in available_in_order])
                            features_normalized = (features_ordered - mean_subset) / scale_subset
                            features = pd.DataFrame(features_normalized, columns=available_in_order)
                            print(f'[预测-factor_cache] 归一化完成，特征数: {len(available_in_order)}')
                        else:
                            print(f'[预测-factor_cache] 跳过归一化: mean={len(mean)}, scale={len(scale)}, features={len(features.columns)}, order={len(feature_order)}')
                    
                    if ensemble_models:
                        predictor = Predictor(ensemble_models, feature_engineer, label_type)
                    else:
                        predictor = Predictor(model, feature_engineer, label_type)
                    
                    if mode == "regression":
                        prediction = predictor._predict_regression(features, threshold)
                    else:
                        prediction = predictor._predict_classification(features)
                    
                    if prediction is None:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code),
                            'error': '无法生成预测'
                        })
                    else:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code),
                            'prediction': prediction
                        })
                else:
                    if predict_date:
                        raw_data = get_realtime_data(stock_code, period=period, days=300, end_date=predict_date)
                    else:
                        raw_data = get_realtime_data(stock_code, period=period, days=300)
                    stock_info = get_stock_info(stock_code)

                    if raw_data is None or len(raw_data) < 50:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code) if stock_info else stock_code,
                            'error': f'无法获取 {stock_code} 的数据或数据不足'
                        })
                        continue

                    # 使用 FeatureEngineer 计算特征
                    import numpy as np
                    model_features = model_info.get('features', [])
                    
                    # 从原始数据计算特征
                    features = feature_engineer._compute_features(raw_data, model_features, stock_code=stock_code, data_source='csv')
                    
                    if features.empty or features.shape[1] == 0:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code) if stock_info else stock_code,
                            'error': f'{stock_code} 无可用特征'
                        })
                        continue
                    
                    # 取最后一行
                    last_row = features.iloc[-1:]
                    available_features = [f for f in model_features if f in last_row.columns]
                    features = last_row[available_features].copy()
                    
                    if features.isnull().any().any():
                        features = features.fillna(0)
                    
                    # 用训练时保存的全局 scaler 参数归一化（与 factor_cache 一致）
                    scaler_params = model_info.get('scaler_params')
                    if scaler_params:
                        mean = np.array(scaler_params['mean'])
                        scale = np.array(scaler_params['scale'])
                        feature_order = scaler_params.get('feature_names', model_features)
                        
                        available_in_order = [f for f in feature_order if f in features.columns]
                        if available_in_order and len(mean) == len(feature_order) and len(scale) == len(feature_order):
                            features_ordered = features[available_in_order].values
                            scale_subset = np.array([scale[feature_order.index(f)] for f in available_in_order])
                            mean_subset = np.array([mean[feature_order.index(f)] for f in available_in_order])
                            features_normalized = (features_ordered - mean_subset) / scale_subset
                            features = pd.DataFrame(features_normalized, columns=available_in_order)
                            print(f'[预测-akshare] 归一化完成，特征数: {len(available_in_order)}')
                        else:
                            print(f'[预测-akshare] 跳过归一化: mean={len(mean)}, scale={len(scale)}, features={len(features.columns)}, order={len(feature_order)}')

                    if ensemble_models:
                        predictor = Predictor(ensemble_models, None, label_type)
                    else:
                        predictor = Predictor(model, None, label_type)

                    if mode == "regression":
                        prediction = predictor._predict_regression(features, threshold)
                    else:
                        prediction = predictor._predict_classification(features)

                    if prediction is None:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code) if stock_info else stock_code,
                            'error': '无法生成预测'
                        })
                    else:
                        results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_info.get('name', stock_code) if stock_info else stock_code,
                            'prediction': prediction
                        })
            except Exception as e:
                print(f'[预测] {stock_code} 预测失败: {e}')
                results.append({
                    'stock_code': stock_code,
                    'error': str(e)
                })

        return jsonify({
            'model_id': model_id,
            'results': results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# 选股任务存储
advanced_prediction_tasks = {}


@app.route('/api/ml/predict/advanced', methods=['POST'])
def ml_predict_advanced():
    """选股端点 - 支持多股票、多模型、结果排序和融合"""
    import uuid
    import threading

    task_id = uuid.uuid4().hex[:8]

    try:
        data = request.json
        markets = data.get('markets', [])
        stocks = data.get('stocks', [])
        model_ids = data.get('model_ids', [])
        sort_by = data.get('sort_by', 'confidence')
        sort_order = data.get('sort_order', 'desc')
        top_n = data.get('top_n', 100)
        fusion_mode = data.get('fusion_mode', 'intersection')
        period = data.get('period', '1d')
        predict_date = data.get('predict_date', '')
        
        # 数据源配置
        data_source = data.get('data_source', 'akshare')
        
        if not model_ids:
            return jsonify({'error': '请至少选择一个模型'}), 400

        # 根据数据源创建 provider，从后端配置读取路径
        from backend.providers import ProviderFactory
        from backend.config import DataSourceConfig
        
        if data_source == 'local':
            local_config = DataSourceConfig.get_config('local')
            data_path = local_config.get('data_path', './data/stocks/')
            provider = ProviderFactory.create_provider('local', data_path=data_path)
            if not provider.is_available():
                return jsonify({'error': f'本地数据路径不可用: {provider.get_error_message()}'}), 400
        elif data_source == 'factor_cache':
            cache_config = DataSourceConfig.get_config('factor_cache')
            cache_path = cache_config.get('cache_path', './data/factor_cache/')
            raw_data_path = cache_config.get('raw_data_path', './data/')
            factor_library = cache_config.get('factor_library', 'alpha191')
            # 转换为绝对路径
            if not os.path.isabs(cache_path):
                cache_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', cache_path))
            if not os.path.isabs(raw_data_path):
                raw_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', raw_data_path))
            # 写入调试文件（使用绝对路径）
            debug_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'debug_factor_cache.txt'))
            import sys
            with open(debug_path, 'a') as f:
                f.write(f"cwd: {os.getcwd()}, cache_path: {cache_path}, exists: {os.path.exists(cache_path)}\n")
                f.write(f"sys.executable: {sys.executable}\n")
            provider = ProviderFactory.create_provider(
                'factor_cache',
                cache_path=cache_path,
                raw_data_path=raw_data_path,
                factor_library=factor_library
            )
            if not provider.is_available():
                return jsonify({'error': f'因子缓存不可用: {provider.get_error_message()}'}), 400
        else:
            provider = ProviderFactory.create_provider('akshare')

        from backend.advanced_predictor import AdvancedPredictor, register_task, get_task_predictor
        from backend.ml import ModelRegistry
        
        # 获取模型模式（从第一个模型推断）
        model_mode = "classification"
        try:
            registry = ModelRegistry()
            first_model = registry.get_model_by_id(model_ids[0])
            if first_model:
                model_mode = first_model.get('mode', 'classification')
        except:
            pass
        
        predictor = AdvancedPredictor(max_workers=4, data_provider=provider)
        
        task = predictor.create_task(
            task_id=task_id,
            markets=markets,
            stocks=stocks,
            model_ids=model_ids,
            sort_by=sort_by,
            sort_order=sort_order,
            top_n=top_n,
            fusion_mode=fusion_mode,
            period=period,
            predict_date=predict_date,
            mode=model_mode
        )
        
        register_task(task_id, predictor)

        # 启动后台线程执行预测
        thread = threading.Thread(target=predictor.run_prediction, args=(task,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'message': f'选股任务已启动，使用 {len(model_ids)} 个模型预测'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/tasks', methods=['GET'])
def ml_get_advanced_prediction_tasks():
    """获取所有选股任务列表"""
    try:
        from backend.advanced_predictor import get_advanced_predictor, _global_tasks, _global_tasks_lock
        all_tasks = []
        predictor = get_advanced_predictor()
        all_tasks.extend(predictor.get_all_tasks())
        with _global_tasks_lock:
            for tid, pred in _global_tasks.items():
                task = pred.get_task(tid)
                if task:
                    import time
                    elapsed = time.time() - task.start_time if task.start_time > 0 else 0
                    all_tasks.append({
                        'task_id': task.task_id,
                        'status': task.status,
                        'progress': task.progress,
                        'message': task.message,
                        'total_stocks': task.total_stocks,
                        'processed_stocks': task.processed_stocks,
                        'model_count': len(task.model_ids),
                        'elapsed_time': round(elapsed, 1)
                    })
        return jsonify({'tasks': all_tasks})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/<task_id>', methods=['GET'])
def ml_get_advanced_prediction(task_id):
    """获取选股任务状态和结果"""
    try:
        from backend.advanced_predictor import get_task_predictor
        predictor = get_task_predictor(task_id)
        if not predictor:
            from backend.advanced_predictor import get_advanced_predictor
            predictor = get_advanced_predictor()
        task = predictor.get_task(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 转换结果为可JSON序列化的格式
        results_dict = {}
        for model_id, results in task.results.items():
            results_dict[model_id] = [
                {
                    'stock_code': r.stock_code,
                    'stock_name': r.stock_name,
                    'model_id': r.model_id,
                    'model_type': r.model_type,
                    'model_name': r.model_name,
                    'signal': r.signal,
                    'confidence': r.confidence,
                    'buy_probability': r.buy_probability,
                    'sell_probability': r.sell_probability,
                    'hold_probability': r.hold_probability,
                    'predicted_return': r.predicted_return,
                    'rank': r.rank,
                    'error': r.error,
                    'mode': r.mode
                }
                for r in results
            ]

        fused_results = [
            {
                'stock_code': r.stock_code,
                'stock_name': r.stock_name,
                'model_id': r.model_id,
                'model_type': r.model_type,
                'model_name': r.model_name,
                'signal': r.signal,
                'confidence': r.confidence,
                'buy_probability': r.buy_probability,
                'sell_probability': r.sell_probability,
                'hold_probability': r.hold_probability,
                'predicted_return': r.predicted_return,
                'rank': r.rank,
                'mode': r.mode
            }
            for r in task.fused_results
        ]

        # 添加导出文件信息
        export_files = {}
        for key, filepath in task.export_files.items():
            if os.path.exists(filepath):
                filename = os.path.basename(filepath)
                export_files[key] = {
                    'filename': filename,
                    'url': f'/api/ml/predict/advanced/{task_id}/download/{key}'
                }

        return jsonify({
            'task_id': task_id,
            'status': task.status,
            'progress': task.progress,
            'message': task.message,
            'total_stocks': task.total_stocks,
            'processed_stocks': task.processed_stocks,
            'results': results_dict,
            'fused_results': fused_results,
            'export_files': export_files
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/<task_id>/stop', methods=['POST'])
def ml_stop_advanced_prediction(task_id):
    """停止选股任务"""
    try:
        from backend.advanced_predictor import get_task_predictor
        predictor = get_task_predictor(task_id)
        if not predictor:
            from backend.advanced_predictor import get_advanced_predictor
            predictor = get_advanced_predictor()
        success = predictor.stop_task(task_id)
        if success:
            return jsonify({'status': 'stopping', 'message': '正在停止任务...'})
        else:
            return jsonify({'error': '任务不存在或已结束'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/<task_id>', methods=['DELETE'])
def ml_delete_advanced_prediction(task_id):
    """删除选股任务"""
    try:
        from backend.advanced_predictor import get_task_predictor
        predictor = get_task_predictor(task_id)
        if not predictor:
            from backend.advanced_predictor import get_advanced_predictor
            predictor = get_advanced_predictor()
        success = predictor.delete_task(task_id)
        if success:
            return jsonify({'status': 'deleted', 'message': '任务已删除'})
        else:
            return jsonify({'error': '任务不存在'}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/<task_id>/download/<file_key>', methods=['GET'])
def ml_download_prediction_file(task_id, file_key):
    """下载预测结果Excel文件"""
    import glob
    
    try:
        from backend.advanced_predictor import get_task_predictor
        predictor = get_task_predictor(task_id)
        if not predictor:
            from backend.advanced_predictor import get_advanced_predictor
            predictor = get_advanced_predictor()
        task = predictor.get_task(task_id)

        filepath = None
        
        if task and task.export_files and file_key in task.export_files:
            filepath = task.export_files[file_key]
        else:
            export_dir = os.path.join(os.path.dirname(__file__), '..', 'exports')
            if os.path.exists(export_dir):
                if file_key == 'fused':
                    pattern = os.path.join(export_dir, f'*FUSED*{task_id}*.xlsx')
                else:
                    pattern = os.path.join(export_dir, f'*{file_key}*.xlsx')
                
                files = glob.glob(pattern)
                if files:
                    filepath = files[0]
                else:
                    all_files = glob.glob(os.path.join(export_dir, '*.xlsx'))
                    for f in all_files:
                        basename = os.path.basename(f)
                        if task_id in basename and file_key in basename:
                            filepath = f
                            break

        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': '文件不存在或已被删除'}), 404

        filename = os.path.basename(filepath)
        return send_file(
            filepath,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/predict/advanced/<task_id>/download_all', methods=['GET'])
def ml_download_all_advanced_prediction(task_id):
    """打包下载所有选股结果文件"""
    import zipfile
    import io
    import glob
    
    try:
        from backend.advanced_predictor import get_task_predictor
        predictor = get_task_predictor(task_id)
        if not predictor:
            from backend.advanced_predictor import get_advanced_predictor
            predictor = get_advanced_predictor()
        task = predictor.get_task(task_id)

        export_files = {}
        
        if task and task.export_files:
            export_files = task.export_files
        else:
            export_dir = os.path.join(os.path.dirname(__file__), '..', 'exports')
            if os.path.exists(export_dir):
                pattern = os.path.join(export_dir, f'*{task_id}*.xlsx')
                files = glob.glob(pattern)
                if not files:
                    all_files = glob.glob(os.path.join(export_dir, '*.xlsx'))
                    files = [f for f in all_files if task_id in os.path.basename(f)]
                
                for filepath in files:
                    filename = os.path.basename(filepath)
                    key = filename.replace('.xlsx', '')
                    export_files[key] = filepath

        if not export_files:
            return jsonify({'error': '没有可下载的文件，任务可能已过期或不存在'}), 404

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for key, filepath in export_files.items():
                if os.path.exists(filepath):
                    filename = os.path.basename(filepath)
                    zf.write(filepath, filename)
        
        memory_file.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"stock_picking_{task_id}_{timestamp}.zip"
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/models', methods=['GET'])
def ml_get_models():
    try:
        stock_code = request.args.get('stock')
        from backend.ml import ModelRegistry
        registry = ModelRegistry()

        if stock_code:
            models = registry.get_models_by_stock(stock_code)
        else:
            models = registry.get_all_models()

        result_models = []
        processed_ids = set()

        parent_groups = {}
        for m in models:
            parent_id = m.get('parent_model_id')
            if parent_id:
                if parent_id not in parent_groups:
                    parent_groups[parent_id] = []
                parent_groups[parent_id].append(m)

        for m in models:
            model_id = m.get('id')

            if model_id in processed_ids:
                continue

            parent_id = m.get('parent_model_id')
            if parent_id and parent_id in parent_groups:
                siblings = parent_groups[parent_id]
                if len(siblings) > 1:
                    model_types = [x.get('model_type', '') for x in siblings]
                    first_sibling = siblings[0]
                    result_models.append({
                        'id': parent_id,
                        'model_name': first_sibling.get('model_name', '').rsplit('_', 2)[0],
                        'model_type': f'集成({", ".join(model_types)})',
                        'stock_code': first_sibling.get('stock_code', ''),
                        'mode': first_sibling.get('mode', 'classification'),
                        'is_ensemble': True,
                        'sub_models': [{'id': x.get('id'), 'model_type': x.get('model_type', '')} for x in siblings],
                        'created_at': first_sibling.get('created_at', ''),
                        'features': first_sibling.get('features', []),
                        'feature_count': len(first_sibling.get('features', []))
                    })
                    for sib in siblings:
                        processed_ids.add(sib.get('id'))
                    continue

            result_models.append(m)
            processed_ids.add(model_id)

        return jsonify({'models': result_models})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/models/<model_id>', methods=['DELETE'])
def ml_delete_model(model_id):
    try:
        from backend.ml import ModelRegistry
        registry = ModelRegistry()
        success = registry.delete_model(model_id)

        if success:
            return jsonify({'status': 'deleted', 'model_id': model_id})
        else:
            return jsonify({'error': 'Model not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/train/progress/<task_id>', methods=['GET'])
def ml_get_train_progress(task_id):
    if task_id in training_tasks:
        task_info = training_tasks[task_id]
        # 确保返回当前任务序号信息
        response = {
            'progress': task_info.get('progress', 0),
            'status': task_info.get('status', 'unknown'),
            'message': task_info.get('message', ''),
            'current_task_index': task_info.get('current_task_index', 0),
            'total_tasks': task_info.get('total_tasks', 1)
        }
        return jsonify(response)
    return jsonify({'progress': 0, 'status': 'unknown', 'current_task_index': 0, 'total_tasks': 1})

@app.route('/api/ml/train/stop/<task_id>', methods=['POST'])
def ml_stop_train(task_id):
    if task_id in training_tasks:
        training_tasks[task_id]['stopped'] = True
        training_tasks[task_id]['status'] = 'stopped'
        training_tasks[task_id]['message'] = '训练任务已停止'
        return jsonify({'status': 'stopping', 'task_id': task_id})
    return jsonify({'status': 'not_found', 'message': '任务不存在'}), 404

@app.route('/api/ml/train/tasks', methods=['GET'])
def ml_get_train_tasks():
    """获取所有训练任务列表"""
    tasks_list = []
    for task_id, task_info in training_tasks.items():
        task_data = {
            'task_id': task_id,
            'status': task_info.get('status', 'unknown'),
            'progress': task_info.get('progress', 0),
            'message': task_info.get('message', ''),
            'start_time': task_info.get('start_time'),
            'end_time': task_info.get('end_time'),
            'elapsed_time': task_info.get('elapsed_time'),
            'total_count': task_info.get('total_tasks', task_info.get('total_count', 0)),
            'processed_count': task_info.get('current_task_index', task_info.get('processed_count', 0)),
            'success_count': task_info.get('success_count', 0),
            'fail_count': task_info.get('fail_count', 0),
            'current_stock': task_info.get('current_stock'),
            'type': task_info.get('type', 'batch'),
            'mode': task_info.get('train_mode', 'thread'),
            'stocks': task_info.get('stocks', []),
            'params': task_info.get('params', {})
        }
        tasks_list.append(task_data)
    
    # 按创建时间倒序排列
    tasks_list.sort(key=lambda x: x.get('start_time') or '', reverse=True)
    
    return jsonify({'tasks': tasks_list})

@app.route('/api/ml/train/tasks/<task_id>', methods=['DELETE'])
def ml_delete_train_task(task_id):
    """删除训练任务"""
    if task_id in training_tasks:
        task = training_tasks[task_id]
        if task.get('status') == 'running':
            return jsonify({'error': '无法删除运行中的任务'}), 400
        del training_tasks[task_id]
        return jsonify({'status': 'deleted', 'task_id': task_id})
    return jsonify({'error': '任务不存在'}), 404

@app.route('/api/ml/features', methods=['GET'])
def ml_get_features():
    try:
        from backend.ml import FeatureEngineer
        feature_engineer = FeatureEngineer()
        feature_type = request.args.get('type', 'all')
        if feature_type == 'alpha191':
            features = feature_engineer.get_alpha191_features()
        elif feature_type == 'technical':
            features = feature_engineer.get_technical_features()
        else:
            features = feature_engineer.get_technical_features() + feature_engineer.get_alpha191_features()
        return jsonify(features)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/stocks', methods=['GET'])
def ml_get_stocks():
    try:
        market = request.args.get('market')
        period = request.args.get('period', '1d')
        from backend.ml import MLDataLoader
        loader = MLDataLoader()
        stocks = loader.get_available_stocks(market=market, period=period)
        return jsonify(stocks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/markets', methods=['GET'])
def ml_get_markets():
    try:
        from backend.ml import MLDataLoader
        loader = MLDataLoader()
        markets = loader.get_markets()
        return jsonify(markets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/periods', methods=['GET'])
def ml_get_periods():
    try:
        market = request.args.get('market')
        from backend.ml import MLDataLoader
        loader = MLDataLoader()
        periods = loader.get_periods(market=market)
        return jsonify(periods)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/data-tree', methods=['GET'])
def ml_get_data_tree():
    try:
        from backend.ml import MLDataLoader
        loader = MLDataLoader()
        tree = loader.get_data_tree()
        return jsonify(tree)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_backtest(task_id, params, client_id='default'):
    task = tasks[task_id]
    task['status'] = 'running'

    try:
        stock = params.get('stock', '600519')
        start_date = params.get('start_date', '20230101')
        end_date = params.get('end_date', '20231231')
        strategy_name = params.get('strategy', 'sma_cross')
        strategy_params = params.get('params', {})
        period = params.get('period', 'daily')

        socketio.emit('progress', {
            'task_id': task_id,
            'status': 'fetching_data',
            'message': '正在获取数据...'
        }, room=client_id)

        df = get_astock_hist_data(stock, start_date, end_date, period)
        total_bars = len(df)

        if total_bars < 50:
            socketio.emit('backtest_error', {
                'task_id': task_id,
                'error': f'数据不足，至少需要50条数据，当前只有 {total_bars} 条'
            }, room=client_id)
            return

        socketio.emit('progress', {
            'task_id': task_id,
            'status': 'data_loaded',
            'message': f'数据加载完成，共 {total_bars} 条',
            'total_bars': total_bars
        }, room=client_id)

        datafeed = AStockData(dataname=df)
        engine = AStockBacktestEngine(
            initial_cash=params.get('cash', 1000000),
            stake=params.get('stake', 100),
            commission=params.get('commission', 0.001),
            slippage=params.get('slippage', 0.0001),
            stamp_duty=params.get('stamp_duty', 0.0005)
        )
        engine.set_socketio(socketio, task_id, client_id)
        tasks[task_id]['engine'] = engine
        engine.set_speed(params.get('speed', 100))
        engine.add_data(datafeed)

        strategy_class = STRATEGY_MAP.get(strategy_name)

        if not strategy_class:
            socketio.emit('backtest_error', {
                'task_id': task_id,
                'error': f'未找到策略: {strategy_name}'
            }, room=client_id)
            return

        mapped_params = {}
        if 'fast' in strategy_params:
            mapped_params['fast_period'] = strategy_params.pop('fast')
        if 'slow' in strategy_params:
            mapped_params['slow_period'] = strategy_params.pop('slow')

        mapped_params.update(strategy_params)
        engine.add_strategy(strategy_class, **mapped_params)

        socketio.emit('progress', {
            'task_id': task_id,
            'status': 'running',
            'message': '回测进行中...',
            'current_step': 0,
            'total_steps': total_bars,
            'progress': 0
        }, room=client_id)

        try:
            engine.run()
        except Exception as run_err:
            raise Exception(f"回测运行失败: {run_err}")

        final_result = engine.print_results()
        analysis_data = engine.get_analysis_data()

        trades = []
        if engine.results and len(engine.results) > 0:
            strategy_instance = engine.results[0]
            raw_trades = getattr(strategy_instance, 'trades', [])
            timestamps = []
            for idx, row in df.iterrows():
                ts = int(idx.timestamp()) if hasattr(idx, 'timestamp') else int(pd.Timestamp(idx).timestamp())
                timestamps.append(ts)
            for trade in raw_trades:
                bar_idx = trade.get('bar_index', 0)
                if bar_idx < len(timestamps):
                    trade['date'] = timestamps[bar_idx]
                del trade['bar_index']
                trades.append(trade)

        chart_data = []
        for idx, row in df.iterrows():
            ts = int(idx.timestamp()) if hasattr(idx, 'timestamp') else int(pd.Timestamp(idx).timestamp())
            chart_data.append({
                'time': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })

        task['status'] = 'completed'

        chart_image_url = None
        try:
            chart_image_url = engine.save_chart_image(task_id)
        except Exception as plot_err:
            print(f"生成回测图表失败: {plot_err}")

        analysis_data['chart_image_url'] = chart_image_url

        task['result'] = {
            'initial_cash': final_result['initial_cash'],
            'final_cash': final_result['final_cash'],
            'total_return': final_result['total_return'],
            'return_rate': final_result['return_rate'],
            'total_bars': total_bars,
            'chart_data': chart_data,
            'trades': trades,
            'analysis': analysis_data
        }

        socketio.emit('progress', {
            'task_id': task_id,
            'status': 'completed',
            'message': '回测完成',
            'result': task['result']
        }, room=client_id)

    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)
        traceback.print_exc()
        socketio.emit('progress', {
            'task_id': task_id,
            'status': 'failed',
            'message': f'错误: {str(e)}\n{traceback.format_exc()}'
        }, room=client_id)

@socketio.on('connect')
def handle_connect():
    session_id = request.sid
    join_room(session_id)
    print(f'Client connected: {session_id}')

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    leave_room(session_id)
    print(f'Client disconnected: {session_id}')

@socketio.on('pause_backtest')
def handle_pause_backtest(data):
    print(f"[DEBUG] pause_backtest called with data: {data}")
    task_id = data.get('task_id')
    client_id = data.get('client_id', 'default')
    print(f"[暂停请求] task_id={task_id}")
    if task_id and task_id in backtest_tasks:
        engine = backtest_tasks[task_id]['engine']
        if engine:
            engine.pause()
            socketio.emit('backtest_paused', {'task_id': task_id}, room=client_id)
            print(f"[暂停成功] task_id={task_id}")
    else:
        print(f"[暂停失败] task_id not found in backtest_tasks. Available keys: {list(backtest_tasks.keys())}")

@socketio.on('resume_backtest')
def handle_resume_backtest(data):
    task_id = data.get('task_id')
    client_id = data.get('client_id', 'default')
    if task_id and task_id in backtest_tasks:
        engine = backtest_tasks[task_id]['engine']
        if engine:
            engine.resume()
            socketio.emit('backtest_resumed', {'task_id': task_id}, room=client_id)
            print(f"[恢复] task_id={task_id}")

@socketio.on('set_speed')
def handle_set_speed(data):
    task_id = data.get('task_id')
    speed = data.get('speed', 100)
    client_id = data.get('client_id', 'default')
    if task_id and task_id in backtest_tasks:
        engine = backtest_tasks[task_id]['engine']
        if engine:
            engine.set_speed(speed)
            print(f"[速度设置] task_id={task_id}, speed={speed}")

@socketio.on('stop_backtest')
def handle_stop_backtest(data):
    task_id = data.get('task_id')
    client_id = data.get('client_id', 'default')
    print(f"[停止] task_id={task_id}")
    if task_id and task_id in backtest_tasks:
        engine = backtest_tasks[task_id]['engine']
        if engine:
            engine.stop()
            socketio.emit('backtest_stopped', {'task_id': task_id}, room=client_id)
            print(f"[停止成功] task_id={task_id}")


# ==================== 因子缓存管理 API ====================

# 因子缓存任务存储
factor_cache_tasks = {}
factor_cache_threads = {}


def _run_factor_cache_task(task_id, task_type, stock_codes=None, mode='thread'):
    """后台线程执行因子缓存任务
    
    Args:
        task_id: 任务ID
        task_type: 'full' 或 'incremental'
        stock_codes: 股票列表，None表示全部
        mode: 运行模式 - 'single'(单线程) / 'process'(多进程) / 'thread'(多线程)
    """
    import time
    import traceback
    
    # 日志函数
    def log(msg):
        print(f'[因子缓存] {msg}', flush=True)
        # 同时写入文件
        with open('./factor_cache.log', 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {msg}\n')
    
    log(f'任务 {task_id} 启动，类型: {task_type}, 模式: {mode}')
    
    task = factor_cache_tasks.get(task_id)
    if not task:
        log(f'任务 {task_id} 不存在')
        return
    
    task['status'] = 'running'
    task['start_time'] = time.time()
    task['message'] = '初始化数据提供器...'
    
    try:
        log('导入模块...')
        from backend.factor_cache import FactorCacheManager
        from backend.providers import ProviderFactory
        from backend.config import DataSourceConfig
        
        # 创建数据提供器
        log('创建数据提供器...')
        # 获取项目根目录（backend的上级目录）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(project_root, 'data')
        log(f'数据路径: {data_path}')
        
        provider = ProviderFactory.create_provider('local', data_path=data_path)
        
        if not provider.is_available():
            raise Exception(f'数据提供器不可用: {provider.get_error_message()}')
        
        log('数据提供器可用')
        cache_manager = FactorCacheManager()
        
        # 获取股票列表
        log('获取股票列表...')
        if stock_codes is None:
            stock_codes = provider.get_available_stocks()
        
        log(f'找到 {len(stock_codes)} 只股票，运行模式: {mode}')
        
        task['total_count'] = len(stock_codes)
        task['processed_count'] = 0
        task['success_count'] = 0
        task['fail_count'] = 0
        task['mode'] = mode
        
        # 多进程或多线程模式
        if mode in ('process', 'thread'):
            task['message'] = f'使用{mode}模式处理 {len(stock_codes)} 只股票...'
            log(f'使用批量更新模式: {mode}')
            
            # 加载所有股票数据
            stock_data_map = {}
            for stock_code in stock_codes:
                if task.get('stopped'):
                    task['status'] = 'stopped'
                    task['message'] = '任务已停止'
                    return
                try:
                    raw_data = provider.get_stock_data(stock_code)
                    if raw_data is not None and len(raw_data) >= 50:
                        stock_data_map[stock_code] = raw_data
                except Exception as e:
                    log(f'加载 {stock_code} 数据失败: {e}')
            
            log(f'成功加载 {len(stock_data_map)} 只股票数据')
            
            # 处理 technical 库
            task['message'] = '处理 technical 因子库...'
            log('开始处理 technical 库')
            
            # 创建线程停止事件（用于多线程模式）
            from threading import Event
            stop_event = Event()
            
            def progress_callback(completed, total, stock_code, status):
                task['processed_count'] = completed
                task['progress'] = int(completed / total * 100)
                task['current_stock'] = stock_code
                # 返回是否停止
                return task.get('stopped', False)
            
            if mode == 'process':
                result_tech = cache_manager.batch_incremental_update(
                    stock_data_map, 'technical', progress_callback=progress_callback, data_path=data_path,
                    force_full=(task_type == 'full')
                )
            else:  # thread
                result_tech = cache_manager.batch_incremental_update_threaded(
                    stock_data_map, 'technical', progress_callback=progress_callback, stop_event=stop_event,
                    force_full=(task_type == 'full')
                )
            
            # 检查是否停止
            if task.get('stopped'):
                task['status'] = 'stopped'
                task['message'] = '任务已停止'
                return
            
            log(f'technical 库完成: 成功{len(result_tech["success"])}, 失败{len(result_tech["failed"])}')
            
            # 处理 alpha191 库
            task['message'] = '处理 alpha191 因子库...'
            log('开始处理 alpha191 库')
            
            if mode == 'process':
                result_alpha = cache_manager.batch_incremental_update(
                    stock_data_map, 'alpha191', progress_callback=progress_callback, data_path=data_path,
                    force_full=(task_type == 'full')
                )
            else:  # thread
                result_alpha = cache_manager.batch_incremental_update_threaded(
                    stock_data_map, 'alpha191', progress_callback=progress_callback, stop_event=stop_event,
                    force_full=(task_type == 'full')
                )
            
            log(f'alpha191 库完成: 成功{len(result_alpha["success"])}, 失败{len(result_alpha["failed"])}')
            
            task['success_count'] = len(result_tech['success']) + len(result_alpha['success'])
            task['fail_count'] = len(result_tech['failed']) + len(result_alpha['failed'])
            
        else:  # single 单线程模式
            task['message'] = f'单线程模式处理 {len(stock_codes)} 只股票...'
            log('使用单线程模式')
            
            for i, stock_code in enumerate(stock_codes):
                if task.get('stopped'):
                    task['status'] = 'stopped'
                    task['message'] = '任务已停止'
                    return
                
                task['current_stock'] = stock_code
                
                try:
                    # 加载数据
                    raw_data = provider.get_stock_data(stock_code)
                    
                    if raw_data is None or len(raw_data) < 50:
                        task['fail_count'] += 1
                        continue
                    
                    # 判断每个因子库的更新类型
                    update_types = {}
                    for lib in ['technical', 'alpha191']:
                        if task_type == 'full':
                            # 全量模式强制全量更新
                            update_types[lib] = 'full'
                        else:
                            # 智能判断更新类型
                            update_types[lib] = cache_manager.get_cache_update_type(
                                stock_code, raw_data, lib
                            )
                    
                    # 检查是否需要处理
                    if all(t == 'none' for t in update_types.values()):
                        task['success_count'] += 1
                        task['message'] = f'{stock_code} 已最新，跳过 ({i+1}/{len(stock_codes)})'
                        continue
                    
                    task['message'] = f'正在处理 {stock_code} ({i+1}/{len(stock_codes)})...'
                    
                    # 根据更新类型处理
                    for lib in ['technical', 'alpha191']:
                        update_type = update_types[lib]
                        
                        if update_type == 'none':
                            continue  # 跳过
                        elif update_type == 'full':
                            cache_manager.compute_and_save(stock_code, raw_data, lib)
                        else:  # incremental
                            cache_manager.incremental_update(stock_code, raw_data, lib)
                    
                    task['success_count'] += 1
                    
                except Exception as e:
                    print(f'[因子缓存] {stock_code} 处理失败: {e}')
                    task['fail_count'] += 1
                
                task['processed_count'] = i + 1
                task['progress'] = int((i + 1) / len(stock_codes) * 100)
        
        task['status'] = 'completed'
        task['message'] = f'完成！成功: {task["success_count"]}, 失败: {task["fail_count"]}'
        task['end_time'] = time.time()
        task['elapsed_time'] = task['end_time'] - task['start_time']
        
    except Exception as e:
        task['status'] = 'failed'
        task['message'] = f'任务失败: {str(e)}'
        task['error'] = str(e)
        task['end_time'] = time.time()
        traceback.print_exc()


@app.route('/api/factor-cache/status', methods=['GET'])
def factor_cache_status():
    """获取因子缓存状态"""
    try:
        from backend.factor_cache import FactorCacheManager
        
        cache_manager = FactorCacheManager()
        stats = cache_manager.get_global_stats()
        
        return jsonify(stats)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'stock_count': 0,
            'total_size_mb': 0,
            'coverage': 0,
            'libraries': {},
            'last_update': None,
            'error': str(e)
        })


@app.route('/api/factor-cache/tasks', methods=['GET'])
def factor_cache_tasks_list():
    """获取因子缓存任务列表"""
    try:
        tasks_list = []
        for task_id, task in factor_cache_tasks.items():
            task_info = {
                'task_id': task_id,
                'type': task.get('type', 'incremental'),
                'status': task.get('status', 'pending'),
                'mode': task.get('mode', 'thread'),
                'force': task.get('force', False),
                'stocks': task.get('stocks'),
                'progress': task.get('progress', 0),
                'total_count': task.get('total_count', 0),
                'processed_count': task.get('processed_count', 0),
                'success_count': task.get('success_count', 0),
                'fail_count': task.get('fail_count', 0),
                'current_stock': task.get('current_stock', ''),
                'message': task.get('message', ''),
                'start_time': task.get('start_time'),
                'end_time': task.get('end_time'),
                'elapsed_time': task.get('elapsed_time')
            }
            tasks_list.append(task_info)
        
        # 按开始时间倒序排列
        tasks_list.sort(key=lambda x: x.get('start_time') or 0, reverse=True)
        
        return jsonify({'tasks': tasks_list})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'tasks': [], 'error': str(e)})


@app.route('/api/factor-cache/update', methods=['POST'])
def factor_cache_update():
    """启动缓存更新任务（增量/全量统一）
    
    请求参数:
        mode: 运行模式 - 'single'(单线程) / 'process'(多进程) / 'thread'(多线程，默认)
        stocks: 股票代码列表，如 ['000001.SZ', '600000.SH']，不传则更新所有股票
        force: 是否强制重新生成 - true(全量更新) / false(智能增量，默认)
    """
    import uuid
    
    # 检查是否有正在运行的任务
    for task_id, task in factor_cache_tasks.items():
        if task.get('status') == 'running':
            return jsonify({
                'error': '已有正在运行的任务，请先停止或等待完成',
                'running_task_id': task_id
            }), 400
    
    task_id = uuid.uuid4().hex[:8]
    
    try:
        # 获取请求参数
        data = request.get_json() or {}
        mode = data.get('mode', 'thread')
        stocks = data.get('stocks')  # 股票列表
        force = data.get('force', False)  # 是否强制重新生成
        
        # 验证 mode 参数
        if mode not in ('single', 'process', 'thread'):
            return jsonify({
                'error': f'无效的 mode 参数: {mode}，可选值: single, process, thread'
            }), 400
        
        # 验证 stocks 参数
        if stocks is not None and not isinstance(stocks, list):
            return jsonify({
                'error': 'stocks 参数必须是数组格式'
            }), 400
        
        # 确定任务类型
        task_type = 'full' if force else 'incremental'
        
        factor_cache_tasks[task_id] = {
            'task_id': task_id,
            'type': task_type,
            'status': 'pending',
            'mode': mode,
            'stocks': stocks,
            'force': force,
            'progress': 0,
            'message': f'等待开始 ({mode}模式, {task_type})...',
            'created_at': time.time()
        }
        
        # 启动后台线程
        import os
        log_msg = f'[API] 准备启动后台线程，task_id={task_id}, mode={mode}, type={task_type}'
        if stocks:
            log_msg += f', stocks={len(stocks)}只'
        print(log_msg, flush=True)
        with open('./factor_cache.log', 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {log_msg}\n')
        
        thread = threading.Thread(
            target=_run_factor_cache_task,
            args=(task_id, task_type, stocks, mode)
        )
        thread.daemon = True
        factor_cache_threads[task_id] = thread
        thread.start()
        
        log_msg = f'[API] 后台线程已启动，task_id={task_id}'
        print(log_msg, flush=True)
        with open('./factor_cache.log', 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {log_msg}\n')
        
        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'mode': mode,
            'type': task_type,
            'stocks_count': len(stocks) if stocks else 'all',
            'message': f'缓存更新任务已启动 ({mode}模式, {task_type})'
        })
        
    except Exception as e:
        traceback.print_exc()
        if task_id in factor_cache_tasks:
            del factor_cache_tasks[task_id]
        return jsonify({'error': str(e)}), 500


@app.route('/api/factor-cache/tasks/<task_id>', methods=['GET', 'DELETE'])
def factor_cache_task_handler(task_id):
    """处理单个任务 - 获取状态或删除"""
    try:
        if request.method == 'GET':
            # 获取任务状态
            if task_id not in factor_cache_tasks:
                return jsonify({'error': '任务不存在'}), 404
            
            task = factor_cache_tasks[task_id]
            return jsonify({
                'task_id': task_id,
                'status': task.get('status'),
                'progress': task.get('progress', 0),
                'current_stock': task.get('current_stock', ''),
                'message': task.get('message', ''),
                'created_at': task.get('created_at'),
                'updated_at': task.get('updated_at'),
                'success_count': task.get('success_count', 0),
                'fail_count': task.get('fail_count', 0),
                'error': task.get('error')
            })
        
        elif request.method == 'DELETE':
            # 删除任务
            if task_id not in factor_cache_tasks:
                return jsonify({'error': '任务不存在'}), 404
            
            task = factor_cache_tasks[task_id]
            if task.get('status') == 'running':
                return jsonify({'error': '无法删除运行中的任务，请先停止'}), 400
            
            del factor_cache_tasks[task_id]
            if task_id in factor_cache_threads:
                del factor_cache_threads[task_id]
            
            return jsonify({
                'task_id': task_id,
                'status': 'deleted'
            })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/factor-cache/tasks/<task_id>/stop', methods=['POST'])
def factor_cache_stop_task(task_id):
    """停止因子缓存任务"""
    try:
        if task_id not in factor_cache_tasks:
            return jsonify({'error': '任务不存在'}), 404
        
        task = factor_cache_tasks[task_id]
        if task.get('status') != 'running':
            return jsonify({'error': '任务不在运行状态'}), 400
        
        task['stopped'] = True
        
        return jsonify({
            'task_id': task_id,
            'status': 'stopping',
            'message': '任务正在停止...'
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 因子缓存管理 API 结束 ====================


# ==================== 板块数据 API ====================

@app.route('/api/ml/sectors', methods=['GET'])
def ml_get_sectors():
    try:
        import xml.etree.ElementTree as ET
        sector_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sector')
        if not os.path.exists(sector_base):
            return jsonify([])

        result = []
        for category_dir in sorted(os.listdir(sector_base)):
            category_path = os.path.join(sector_base, category_dir)
            if not os.path.isdir(category_path):
                continue

            config_path = os.path.join(category_path, 'sectorConfig.xml')
            children = []

            if os.path.exists(config_path):
                try:
                    tree = ET.parse(config_path)
                    root = tree.getroot()
                    for parent_item in root.findall('.//Item'):
                        if parent_item.get('type') == '0':
                            for child_item in parent_item.findall('Item'):
                                if child_item.get('type') == '2' and child_item.get('visible', '1') == '1':
                                    name = child_item.get('name', '')
                                    sector_file = os.path.join(category_path, name)
                                    if os.path.exists(sector_file):
                                        children.append({
                                            'title': name,
                                            'key': f'{category_dir}/{name}',
                                            'isLeaf': True
                                        })
                except Exception:
                    for f in sorted(os.listdir(category_path)):
                        fpath = os.path.join(category_path, f)
                        if f != 'sectorConfig.xml' and os.path.isfile(fpath):
                            children.append({
                                'title': f,
                                'key': f'{category_dir}/{f}',
                                'isLeaf': True
                            })
            else:
                for f in sorted(os.listdir(category_path)):
                    fpath = os.path.join(category_path, f)
                    if os.path.isfile(fpath):
                        children.append({
                            'title': f,
                            'key': f'{category_dir}/{f}',
                            'isLeaf': True
                        })

            if children:
                result.append({
                    'title': category_dir,
                    'key': category_dir,
                    'children': children
                })

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/sectors/<path:sector_key>/stocks', methods=['GET'])
def ml_get_sector_stocks(sector_key):
    try:
        sector_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sector')
        sector_file = os.path.join(sector_base, sector_key)

        if not os.path.exists(sector_file):
            return jsonify({'error': '板块不存在', 'stocks': []}), 404

        with open(sector_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        stocks = list(set(s.strip() for s in content.split(',') if s.strip()))
        stocks.sort()

        return jsonify({'stocks': stocks, 'count': len(stocks)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 板块数据 API 结束 ====================


# ==================== 模型评估 API ====================

@app.route('/api/ml/evaluate', methods=['POST'])
def ml_evaluate():
    try:
        data = request.json
        model_id = data.get('model_id')
        sectors = data.get('sectors', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        validation_ratio = data.get('validation_ratio', 0.2)

        if not model_id:
            return jsonify({'error': '请选择模型'}), 400
        if not sectors:
            return jsonify({'error': '请选择至少一个板块'}), 400
        if not start_date or not end_date:
            return jsonify({'error': '请选择日期范围'}), 400

        from backend.model_evaluator import ModelEvaluator, register_eval_task

        evaluator = ModelEvaluator()

        try:
            task_id = evaluator.create_task(
                model_id=model_id,
                sectors=sectors,
                start_date=start_date,
                end_date=end_date,
                validation_ratio=validation_ratio
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        register_eval_task(task_id, evaluator)

        thread = threading.Thread(target=evaluator.run_evaluation, args=(task_id,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'message': '评估任务已启动'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/evaluate/<task_id>', methods=['GET'])
def ml_get_evaluation(task_id):
    try:
        from backend.model_evaluator import get_task_evaluator, get_all_evaluators

        evaluator = get_task_evaluator(task_id)
        if not evaluator:
            for ev in get_all_evaluators():
                task = ev.get_task(task_id)
                if task:
                    return jsonify(task)
            return jsonify({'error': '任务不存在'}), 404

        task = evaluator.get_task(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        return jsonify(task)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/evaluate/tasks', methods=['GET'])
def ml_get_evaluation_tasks():
    try:
        from backend.model_evaluator import get_all_evaluators

        all_tasks = []
        for evaluator in get_all_evaluators():
            all_tasks.extend(evaluator.get_all_tasks())

        all_tasks.sort(key=lambda x: x.get('start_time') or 0, reverse=True)

        return jsonify({'tasks': all_tasks})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 模型评估 API 结束 ====================


if __name__ == '__main__':
    print("=" * 50)
    print("Backtrader 回测服务已启动")
    print("API: http://localhost:5000/api/backtest")
    print("WebSocket: ws://localhost:5000")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

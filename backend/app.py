import re
import importlib
import inspect
import time
from flask import Flask, request, jsonify, send_from_directory
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

from data_handler import get_astock_hist_data, load_csv_data, AStockData
from backtest_engine import AStockBacktestEngine

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
                        lower_q, upper_q, mode, use_ensemble, total_stocks, prepare_func):
    """后台线程执行训练任务"""
    from ml import ModelTrainer, ModelRegistry
    from backend.pipeline import TrainingPipeline

    trainer = ModelTrainer()
    registry = ModelRegistry()

    training_tasks[task_id] = {'progress': 5, 'status': '准备训练...',
        'message': f'将按顺序处理 {total_stocks} 只股票，训练统一模型'}
    print(f'[训练] 任务ID: {task_id} - 将按顺序处理 {total_stocks} 只股票')

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
        progress_scale=0.55
    )

    try:
        pipeline_result = pipeline.run()
    except Exception as e:
        print(f'[训练] 任务ID: {task_id} - 管道执行失败: {e}')
        traceback.print_exc()
        if task_id in training_tasks:
            training_tasks[task_id] = {'progress': 0, 'status': '失败', 'message': str(e)}
        return

    if not pipeline_result:
        print(f'[训练] 任务ID: {task_id} - 没有足够的有效数据')
        if task_id in training_tasks:
            training_tasks[task_id] = {'progress': 0, 'status': '失败', 'message': '没有足够的有效数据，所有股票数据量都太少'}
        return

    all_X = pipeline_result['all_X']
    all_y = pipeline_result['all_y']
    stock_sample_counts = pipeline_result['stock_sample_counts']
    scaler_params = pipeline_result['scaler_params']

    if not all_X:
        print(f'[训练] 任务ID: {task_id} - 没有足够的有效数据')
        if task_id in training_tasks:
            training_tasks[task_id] = {'progress': 0, 'status': '失败', 'message': '没有足够的有效数据'}
        return

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)

    if task_id in training_tasks:
        training_tasks[task_id] = {'progress': 65, 'status': '训练模型...',
            'message': f'总样本数: {len(X)}，来自 {len(stock_sample_counts)} 只股票'}
    print(f'[训练] 任务ID: {task_id} - 开始训练模型, 总样本数: {len(X)}, 股票样本分布: {stock_sample_counts}')

    if use_ensemble:
        print(f'[训练] 任务ID: {task_id} - 集成训练模式')
        result = trainer.train_ensemble(X, y, mode=mode)
        print(f'[训练] 任务ID: {task_id} - 集成训练完成, 指标: {result["test_metrics"]}')

        training_tasks[task_id] = {'progress': 80, 'status': '保存模型...',
            'message': '正在保存子模型'}
        print(f'[训练] 任务ID: {task_id} - 正在保存子模型...')

        base_name = model_name or f'unified_ensemble_{len(features)}f_{total_stocks}stocks'
        trained_models = []
        for i, model_key in enumerate(result['models'].keys()):
            training_tasks[task_id] = {'progress': 85 + i*5, 'status': '保存模型...',
                'message': f'正在保存 {model_key} ({i+1}/{len(result["models"])})'}
            print(f'[训练] 任务ID: {task_id} - 保存 {model_key} ({i+1}/{len(result["models"])})')
            model_obj = result['models'][model_key]
            sub_filename = f'{base_name}_{model_key}.pkl'
            sub_filepath = trainer.save_model(model_obj, sub_filename)
            sub_metric = result['test_metrics'].get(model_key, {})
            stock_display = f'{len(stock_sample_counts)}只股票'
            sub_model_info = registry.register_model(
                stock_code=stock_display,
                model_name=f'{base_name}_{model_key}',
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
                is_ensemble=False
            )
            trained_models.append(sub_model_info)

        training_tasks[task_id] = {'progress': 100, 'status': '完成', 'message': '训练完成!'}
        print(f'[训练] 任务ID: {task_id} - 集成训练完成, 保存了{len(trained_models)}个子模型')
    else:
        print(f'[训练] 任务ID: {task_id} - 单模型训练模式, 模型: {model_type}')
        result = trainer.train_with_split(X, y, model_type, mode=mode)
        print(f'[训练] 任务ID: {task_id} - 模型训练完成, 指标: {result["test_metrics"]}')

        training_tasks[task_id] = {'progress': 80, 'status': '保存模型...', 'message': '正在保存模型'}
        print(f'[训练] 任务ID: {task_id} - 正在保存模型...')

        stock_display = f'{len(stock_sample_counts)}只股票'
        if not model_name:
            if mode == 'regression':
                main_metric = result['test_metrics']['r2']
            else:
                main_metric = result['test_metrics']['accuracy']
            model_name = f'unified_{model_type}_{len(features)}f_{total_stocks}stocks_{main_metric:.2f}'

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

        training_tasks[task_id] = {'progress': 100, 'status': '完成', 'message': '训练完成!'}
        print(f'[训练] 任务ID: {task_id} - 单模型训练完成, 模型已保存: {filename}')

@app.route('/api/ml/train', methods=['POST'])
def ml_train():
    task_id = uuid.uuid4().hex[:8]
    training_tasks[task_id] = {'progress': 0, 'status': '初始化...', 'message': ''}
    print(f'[训练] 任务ID: {task_id} - 开始训练')

    try:
        data = request.json
        stock_param = data.get('stock_code') or data.get('stock')
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

        print(f'[训练] 任务ID: {task_id} - 参数: stock={stock_param}, market={market}, period={period}, horizon={horizon}, use_ensemble={use_ensemble}')

        is_multiple_stocks = isinstance(stock_param, list)
        stock_list = stock_param if is_multiple_stocks else [stock_param]
        total_stocks = len(stock_list)

        if label_type == 'regression' or mode == 'regression':
            prepare_func = 'prepare_data_regression'
            mode = 'regression'
        elif label_type == 'volatility':
            prepare_func = 'prepare_data_with_volatility'
        elif label_type == 'multi':
            prepare_func = 'prepare_data_multi'
        else:
            prepare_func = 'prepare_data'

        training_tasks[task_id] = {'progress': 5, 'status': '准备训练...',
            'message': f'将按顺序处理 {total_stocks} 只股票，训练统一模型'}
        print(f'[训练] 任务ID: {task_id} - 将按顺序处理 {total_stocks} 只股票')

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
        print(f'[训练] 任务ID: {task_id} - 训练失败: {e}')
        traceback.print_exc()
        if task_id in training_tasks:
            del training_tasks[task_id]
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/train/incremental', methods=['POST'])
def ml_train_incremental():
    try:
        data = request.json
        base_model_id = data.get('base_model_id') or data.get('base_model')
        new_start_date = data.get('new_start_date')
        new_end_date = data.get('new_end_date')

        from ml import MLDataLoader, FeatureEngineer, ModelTrainer, ModelRegistry

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
        stock_code = data.get('stock_code') or data.get('stock')
        model_id = data.get('model_id')

        from ml import MLDataLoader, FeatureEngineer, ModelTrainer, ModelRegistry

        registry = ModelRegistry()
        model_info = registry.get_model_by_id(model_id)
        if not model_info:
            return jsonify({'error': '模型不存在'}), 404

        threshold = data.get('threshold', model_info.get('threshold', 0.02))

        trainer = ModelTrainer()
        model = trainer.load_model(model_info['file_path'])

        data_loader = MLDataLoader()
        raw_data = data_loader.load_stock_data(stock_code)

        from ml.predictors import Predictor
        mode = model_info.get('mode', 'classification')
        label_type = model_info.get('label_type', 'fixed')

        if mode == 'regression':
            label_type = 'regression'

        feature_engineer = FeatureEngineer()
        if model_info.get('scaler_params'):
            feature_engineer.set_scaler_params(model_info['scaler_params'])

        model_name = model_info.get('model_name', '')

        ensemble_prefix = None
        if '_ensemble_' in model_name or '_Ensemble_' in model_name:
            parts = model_name.rsplit('_', 1)
            if len(parts) > 1:
                ensemble_prefix = parts[0]
        elif 'ensemble' in model_name.lower() and model_info.get('is_ensemble'):
            ensemble_prefix = model_name

        if ensemble_prefix:
            all_models = registry.get_all_models()
            ensemble_models = {}

            for m in all_models:
                if m['model_name'] == model_name or m['model_name'].startswith(ensemble_prefix + '_'):
                    sub_model = trainer.load_model(m['file_path'])
                    ensemble_models[m['model_type']] = sub_model

            if len(ensemble_models) > 1:
                print(f'[预测] 使用集成模式，加载了 {len(ensemble_models)} 个子模型: {list(ensemble_models.keys())}')
                model = ensemble_models

        predictor = Predictor(model, feature_engineer, label_type)
        result = predictor.predict(raw_data, model_info['features'], threshold=threshold)

        if result is None:
            return jsonify({'error': '无法生成预测，数据不足'}), 400

        return jsonify({
            'stock_code': stock_code,
            'model_id': model_id,
            'prediction': result
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/models', methods=['GET'])
def ml_get_models():
    try:
        stock_code = request.args.get('stock')
        from ml import ModelRegistry
        registry = ModelRegistry()

        if stock_code:
            models = registry.get_models_by_stock(stock_code)
        else:
            models = registry.get_all_models()

        return jsonify(models)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/models/<model_id>', methods=['DELETE'])
def ml_delete_model(model_id):
    try:
        from ml import ModelRegistry
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
        return jsonify(training_tasks[task_id])
    return jsonify({'progress': 0, 'status': 'unknown'})

@app.route('/api/ml/train/stop/<task_id>', methods=['POST'])
def ml_stop_train(task_id):
    if task_id in training_threads:
        thread = training_threads[task_id]
        thread_id = thread.ident
        import ctypes
        import inspect
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        training_tasks[task_id] = {'progress': 0, 'status': '已停止', 'message': '用户手动停止'}
        if task_id in training_threads:
            del training_threads[task_id]
        return jsonify({'status': 'stopped', 'task_id': task_id})
    return jsonify({'status': 'not_found', 'message': '任务不存在'}), 404

@app.route('/api/ml/features', methods=['GET'])
def ml_get_features():
    try:
        from ml import FeatureEngineer
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
        from ml import MLDataLoader
        loader = MLDataLoader()
        stocks = loader.get_available_stocks(market=market, period=period)
        return jsonify(stocks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/markets', methods=['GET'])
def ml_get_markets():
    try:
        from ml import MLDataLoader
        loader = MLDataLoader()
        markets = loader.get_markets()
        return jsonify(markets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/periods', methods=['GET'])
def ml_get_periods():
    try:
        market = request.args.get('market')
        from ml import MLDataLoader
        loader = MLDataLoader()
        periods = loader.get_periods(market=market)
        return jsonify(periods)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/data-tree', methods=['GET'])
def ml_get_data_tree():
    try:
        from ml import MLDataLoader
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

if __name__ == '__main__':
    print("=" * 50)
    print("Backtrader 回测服务已启动")
    print("API: http://localhost:5000/api/backtest")
    print("WebSocket: ws://localhost:5000")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

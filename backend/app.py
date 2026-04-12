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

@app.route('/api/chart/<filename>')
def serve_chart(filename):
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
    return send_from_directory(results_dir, filename)

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

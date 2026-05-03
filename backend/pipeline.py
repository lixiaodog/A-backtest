import threading
import queue
import time
from datetime import datetime
import pandas as pd
import numpy as np
from backend.ml import MLDataLoader, FeatureEngineer


def _log(message, level='INFO'):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f'[{timestamp}] [{level}] {message}')

class TrainingPipeline:
    def __init__(self, stock_list, task_id, prepare_func, features, horizon, threshold,
                 vol_window, lower_q, upper_q, start_date, end_date, period, market, mode,
                 training_tasks, progress_offset=0, progress_scale=0.6, num_feature_workers=3,
                 data_source='csv', use_gpu=False, fast_mode=False, normalize=False):
        self.stock_list = stock_list
        self.task_id = task_id
        self.prepare_func = prepare_func
        self.features = features
        self.horizon = horizon
        self.threshold = threshold
        self.vol_window = vol_window
        self.lower_q = lower_q
        self.upper_q = upper_q
        self.start_date = start_date
        self.end_date = end_date
        self.period = period
        self.market = market
        self.mode = mode
        self.training_tasks = training_tasks
        self.progress_offset = progress_offset
        self.progress_scale = progress_scale
        self.num_feature_workers = num_feature_workers
        self.data_source = data_source
        self.use_gpu = use_gpu
        self.fast_mode = fast_mode
        self.normalize = normalize

        self.raw_queue = queue.Queue(maxsize=10)
        self.feature_queue = queue.Queue(maxsize=10)
        self.raw_done_event = threading.Event()
        self.stop_event = threading.Event()
        self.feature_done_event = threading.Event()
        self.training_result = None
        self.error = None
        self.all_X = []
        self.all_y = []
        self.all_stock_codes = []  # 记录股票代码顺序
        self.stock_sample_counts = {}
        self.count_lock = threading.Lock()
        self.workers_finished = 0
        self.workers_lock = threading.Lock()
        self.current_stock = ""
        self.current_stage = "准备中"

    def is_stopped(self):
        """检查是否被停止"""
        if self.task_id in self.training_tasks:
            return self.training_tasks[self.task_id].get('stopped', False)
        return False

    def _update_progress(self, processed, total, stage, current_stock=""):
        stock_progress = int((processed / total) * self.progress_scale * 100)
        progress = int(self.progress_offset + stock_progress)
        self.current_stock = current_stock
        self.current_stage = stage
        self.training_tasks[self.task_id] = {
            'progress': progress,
            'status': f'{stage} ({processed}/{total})',
            'message': f'正在处理 {current_stock}，{stage}...'
        }

    def thread1_data_loader(self):
        _log(f'[数据加载] 开始加载 {len(self.stock_list)} 只股票的数据')
        min_data_count = self.horizon + 1 if self.data_source in ['cache', 'factor_cache'] else 100
        for idx, stock_code in enumerate(self.stock_list):
            if self.is_stopped():
                _log('[数据加载] 收到停止信号，退出', 'WARN')
                break
            try:
                data_loader = MLDataLoader()
                raw_data = data_loader.load_stock_data(
                    stock_code, self.start_date, self.end_date,
                    period=self.period, market=self.market
                )

                if len(raw_data) < min_data_count:
                    _log(f'[数据加载] {stock_code} 原始数据量太少({len(raw_data)}条)，需要至少{min_data_count}条，跳过', 'WARN')
                    continue

                self.raw_queue.put((stock_code, raw_data), timeout=30)
                _log(f'[数据加载] {stock_code} 加载完成({len(raw_data)}条)，待处理 [{idx+1}/{len(self.stock_list)}]')

            except FileNotFoundError:
                _log(f'[数据加载] {stock_code} 文件不存在，跳过', 'WARN')
            except Exception as e:
                _log(f'[数据加载] {stock_code} 加载失败: {e}', 'ERROR')

        self.raw_done_event.set()
        _log('[数据加载] 数据加载完成')

    def thread2_feature_generator(self, worker_id=0):
        _log(f'[特征生成-{worker_id}] 开始处理特征')
        processed = 0
        while not (self.raw_queue.empty() and self.raw_done_event.is_set()):
            if self.is_stopped():
                _log(f'[特征生成-{worker_id}] 收到停止信号，退出', 'WARN')
                break
            try:
                stock_code, raw_data = self.raw_queue.get(timeout=2)

                feature_engineer = FeatureEngineer()

                if self.prepare_func == 'prepare_data_regression':
                    X, y = feature_engineer.prepare_data_regression(raw_data, self.features, self.horizon, normalize=False, stock_code=stock_code, data_source=self.data_source)
                elif self.prepare_func == 'prepare_data_with_volatility':
                    X, y = feature_engineer.prepare_data_with_volatility(
                        raw_data, self.features, self.horizon, self.vol_window, self.lower_q, self.upper_q, normalize=False, stock_code=stock_code, data_source=self.data_source
                    )
                elif self.prepare_func == 'prepare_data_multi':
                    X, y = feature_engineer.prepare_data_multi(
                        raw_data, self.features, self.horizon, self.lower_q, self.upper_q, normalize=False, stock_code=stock_code, data_source=self.data_source
                    )
                else:
                    X, y = feature_engineer.prepare_data(raw_data, self.features, self.horizon, self.threshold, normalize=False, stock_code=stock_code, data_source=self.data_source)

                min_feature_count = 1 if self.data_source in ['cache', 'factor_cache'] else 50
                if len(X) < min_feature_count:
                    _log(f'[特征生成-{worker_id}] {stock_code} 特征数据量太少({len(X)}条)，需要至少{min_feature_count}条，跳过', 'WARN')
                    self.raw_queue.task_done()
                    continue

                self.feature_queue.put((stock_code, X, y), timeout=30)
                processed += 1
                _log(f'[特征生成-{worker_id}] {stock_code} 特征生成完成，样本数: {len(X)}，特征数: {X.shape[1]}')

                self.raw_queue.task_done()

            except queue.Empty:
                if self.raw_done_event.is_set():
                    break
                continue
            except Exception as e:
                _log(f'[特征生成-{worker_id}] {stock_code} 特征生成失败: {e}', 'ERROR')
                if not self.raw_queue.empty():
                    try:
                        self.raw_queue.task_done()
                    except:
                        pass
                continue

        with self.workers_lock:
            self.workers_finished += 1
            if self.workers_finished >= self.num_feature_workers:
                self.feature_done_event.set()
        _log(f'[特征生成-{worker_id}] 完成，共处理 {processed} 只股票')

    def thread3_trainer(self):
        from backend.ml.feature_engineering import FeatureEngineer
        from sklearn.preprocessing import StandardScaler

        _log('[数据处理] 开始收集特征数据')
        collected = 0
        while not (self.feature_queue.empty() and self.feature_done_event.is_set()):
            if self.is_stopped():
                _log('[数据处理] 收到停止信号，退出', 'WARN')
                self.training_result = None
                return
            try:
                stock_code, X, y = self.feature_queue.get(timeout=2)
                self.all_X.append(X)
                self.all_y.append(y)
                self.all_stock_codes.append(stock_code)  # 记录股票代码
                self.stock_sample_counts[stock_code] = len(X)
                collected += 1
                _log(f'[数据处理] {stock_code} 数据已收集，当前共 {len(self.all_X)} 只股票')
                self._update_progress(collected, len(self.stock_list), '收集数据', stock_code)
                self.feature_queue.task_done()

            except queue.Empty:
                if self.feature_done_event.is_set():
                    break
                continue
            except Exception as e:
                _log(f'[数据处理] 收集数据失败: {e}', 'ERROR')
                if not self.feature_queue.empty():
                    try:
                        self.feature_queue.task_done()
                    except:
                        pass
                continue

        if not self.all_X:
            _log('[数据处理] 没有收集到任何数据', 'ERROR')
            self.training_result = None
            return

        _log(f'[数据处理] 数据收集完成，共 {len(self.all_X)} 只股票，开始合并数据...')
        self._update_progress(len(self.stock_list), len(self.stock_list), '合并数据', '')
        start_time = time.time()

        # 按股票代码排序，确保数据顺序一致（多线程收集顺序不确定）
        sorted_indices = sorted(range(len(self.all_stock_codes)), key=lambda i: self.all_stock_codes[i])
        sorted_X = [self.all_X[i] for i in sorted_indices]
        sorted_y = [self.all_y[i] for i in sorted_indices]

        total_rows = sum(len(X) for X in sorted_X)
        n_features = sorted_X[0].shape[1]
        feature_names = sorted_X[0].columns.tolist()

        _log(f'[数据处理] 样本总数: {total_rows}, 特征数: {n_features}')

        combined_X = np.empty((total_rows, n_features), dtype=np.float32)
        combined_y = np.empty(total_rows, dtype=np.float32)

        offset = 0
        for X, y in zip(sorted_X, sorted_y):
            n = len(X)
            combined_X[offset:offset+n] = X.values
            combined_y[offset:offset+n] = y.values
            offset += n

        merge_time = time.time() - start_time
        _log(f'[数据处理] 数据合并完成，耗时 {merge_time:.2f}秒')

        if self.normalize:
            self._update_progress(len(self.stock_list), len(self.stock_list), '归一化', '')
            _log(f'[归一化] 开始归一化 {n_features} 个特征...')
            _log(f'[归一化] 特征列表: {feature_names[:10]}{"..." if len(feature_names) > 10 else ""}')
            normalize_start = time.time()

            if self.use_gpu:
                try:
                    import cupy as cp
                    _log('[归一化] 使用 GPU (cupy) 进行归一化')
                    X_gpu = cp.asarray(combined_X)
                    mean = cp.mean(X_gpu, axis=0)
                    std = cp.std(X_gpu, axis=0)
                    std[std == 0] = 1
                    X_normalized_gpu = (X_gpu - mean) / std
                    combined_X_scaled = cp.asnumpy(X_normalized_gpu)
                    scaler_params = {
                        'mean': cp.asnumpy(mean).tolist(),
                        'scale': cp.asnumpy(std).tolist(),
                        'n_features_in_': n_features,
                        'feature_names': feature_names
                    }
                    del X_gpu, X_normalized_gpu
                    cp.get_default_memory_pool().free_all_blocks()
                except ImportError:
                    _log('[归一化] cupy 未安装，回退到 CPU 归一化', 'WARN')
                    scaler = StandardScaler()
                    combined_X_scaled = scaler.fit_transform(combined_X)
                    scaler_params = {
                        'mean': scaler.mean_.tolist(),
                        'scale': scaler.scale_.tolist(),
                        'n_features_in_': n_features,
                        'feature_names': feature_names
                    }
            else:
                _log('[归一化] 使用 CPU (StandardScaler) 进行归一化')
                scaler = StandardScaler()
                combined_X_scaled = scaler.fit_transform(combined_X)
                scaler_params = {
                    'mean': scaler.mean_.tolist(),
                    'scale': scaler.scale_.tolist(),
                    'n_features_in_': n_features,
                    'feature_names': feature_names
                }

            normalize_time = time.time() - normalize_start
            _log(f'[归一化] 完成，耗时 {normalize_time:.2f}秒')

            combined_X_scaled = pd.DataFrame(combined_X_scaled, columns=feature_names)
            combined_y = pd.Series(combined_y)

            self.all_X = [combined_X_scaled]
            self.all_y = [combined_y]

            total_time = time.time() - start_time
            _log(f'[数据处理] 全部完成，总耗时 {total_time:.2f}秒，最终样本数: {len(combined_X_scaled)}')
            self.training_result = {
                'all_X': self.all_X,
                'all_y': self.all_y,
                'stock_sample_counts': {'统一数据': len(combined_X_scaled)},
                'scaler_params': scaler_params
            }
        else:
            _log('[归一化] 跳过特征归一化')
            combined_X_df = pd.DataFrame(combined_X, columns=feature_names)
            combined_y_series = pd.Series(combined_y)

            self.all_X = [combined_X_df]
            self.all_y = [combined_y_series]

            total_time = time.time() - start_time
            _log(f'[数据处理] 全部完成，总耗时 {total_time:.2f}秒，最终样本数: {len(combined_X_df)}')
            self.training_result = {
                'all_X': self.all_X,
                'all_y': self.all_y,
                'stock_sample_counts': {'统一数据': len(combined_X_df)},
                'scaler_params': None
            }

    def run(self):
        t1 = threading.Thread(target=self.thread1_data_loader, name='DataLoader')
        t2_workers = []
        for i in range(self.num_feature_workers):
            t = threading.Thread(target=self.thread2_feature_generator, name=f'FeatureGen-{i}', args=(i,))
            t2_workers.append(t)
        t3 = threading.Thread(target=self.thread3_trainer, name='Trainer')

        t1.start()
        for t in t2_workers:
            t.start()
        t3.start()

        t1.join()
        for t in t2_workers:
            t.join()
        t3.join()

        if self.error:
            raise self.error

        return self.training_result
import threading
import queue
import time
import pandas as pd
import numpy as np
from ml import MLDataLoader, FeatureEngineer

class TrainingPipeline:
    def __init__(self, stock_list, task_id, prepare_func, features, horizon, threshold,
                 vol_window, lower_q, upper_q, start_date, end_date, period, market, mode,
                 training_tasks, progress_offset=0, progress_scale=0.6, num_feature_workers=3):
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

        self.raw_queue = queue.Queue(maxsize=10)
        self.feature_queue = queue.Queue(maxsize=10)
        self.raw_done_event = threading.Event()
        self.feature_done_event = threading.Event()
        self.training_result = None
        self.error = None
        self.all_X = []
        self.all_y = []
        self.stock_sample_counts = {}
        self.count_lock = threading.Lock()
        self.workers_finished = 0
        self.workers_lock = threading.Lock()
        self.current_stock = ""
        self.current_stage = "准备中"

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
        for idx, stock_code in enumerate(self.stock_list):
            try:
                data_loader = MLDataLoader()
                raw_data = data_loader.load_stock_data(
                    stock_code, self.start_date, self.end_date,
                    period=self.period, market=self.market
                )

                if len(raw_data) < 100:
                    print(f'[线程1] {stock_code} 原始数据量太少({len(raw_data)}条)，跳过')
                    continue

                self.raw_queue.put((stock_code, raw_data), timeout=30)
                print(f'[线程1] {stock_code} 加载完成，待处理')

            except FileNotFoundError:
                print(f'[线程1] {stock_code} 文件不存在，跳过')
            except Exception as e:
                print(f'[线程1] {stock_code} 加载失败: {e}')

        self.raw_done_event.set()
        print('[线程1] 数据加载完成')

    def thread2_feature_generator(self, worker_id=0):
        processed = 0
        while not (self.raw_queue.empty() and self.raw_done_event.is_set()):
            try:
                stock_code, raw_data = self.raw_queue.get(timeout=2)

                feature_engineer = FeatureEngineer()

                if self.prepare_func == 'prepare_data_regression':
                    X, y = feature_engineer.prepare_data_regression(raw_data, self.features, self.horizon)
                elif self.prepare_func == 'prepare_data_with_volatility':
                    X, y = feature_engineer.prepare_data_with_volatility(
                        raw_data, self.features, self.horizon, self.vol_window, self.lower_q, self.upper_q
                    )
                elif self.prepare_func == 'prepare_data_multi':
                    X, y = feature_engineer.prepare_data_multi(
                        raw_data, self.features, self.horizon, self.lower_q, self.upper_q
                    )
                else:
                    X, y = feature_engineer.prepare_data(raw_data, self.features, self.horizon, self.threshold)

                if len(X) < 50:
                    print(f'[线程2-{worker_id}] {stock_code} 特征数据量太少({len(X)}条)，跳过')
                    self.raw_queue.task_done()
                    continue

                self.feature_queue.put((stock_code, X, y), timeout=30)
                processed += 1
                print(f'[线程2-{worker_id}] {stock_code} 特征生成完成，样本数: {len(X)}')

                self.raw_queue.task_done()

            except queue.Empty:
                if self.raw_done_event.is_set():
                    break
                continue
            except Exception as e:
                print(f'[线程2-{worker_id}] {stock_code} 特征生成失败: {e}')
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
        print(f'[线程2-{worker_id}] 特征生成完成，共处理 {processed} 只股票')

    def thread3_trainer(self):
        collected = 0
        while not (self.feature_queue.empty() and self.feature_done_event.is_set()):
            try:
                stock_code, X, y = self.feature_queue.get(timeout=2)
                self.all_X.append(X)
                self.all_y.append(y)
                self.stock_sample_counts[stock_code] = len(X)
                collected += 1
                print(f'[线程3] {stock_code} 数据已收集，当前共 {len(self.all_X)} 只股票')
                self._update_progress(collected, len(self.stock_list), '收集数据', stock_code)
                self.feature_queue.task_done()

            except queue.Empty:
                if self.feature_done_event.is_set():
                    break
                continue
            except Exception as e:
                print(f'[线程3] 收集数据失败: {e}')
                if not self.feature_queue.empty():
                    try:
                        self.feature_queue.task_done()
                    except:
                        pass
                continue

        if not self.all_X:
            print('[线程3] 没有收集到任何数据')
            self.training_result = None
            return

        print(f'[线程3] 数据收集完成，共 {len(self.all_X)} 只股票')
        self.training_result = {
            'all_X': self.all_X,
            'all_y': self.all_y,
            'stock_sample_counts': self.stock_sample_counts,
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
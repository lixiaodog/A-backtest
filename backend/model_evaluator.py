import os
import uuid
import time
import random
import threading
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, mean_absolute_error, r2_score


def _log(message, level='INFO'):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f'[{timestamp}] [{level}] {message}')


class EvaluationTask:
    def __init__(self, task_id, model_id, horizon, sectors, stocks, start_date, end_date,
                 validation_ratio, model_info, mode, label_type, threshold, vol_window,
                 lower_q, upper_q):
        self.task_id = task_id
        self.model_id = model_id
        self.horizon = horizon
        self.sectors = sectors
        self.stocks = stocks
        self.start_date = start_date
        self.end_date = end_date
        self.validation_ratio = validation_ratio
        self.model_info = model_info
        self.mode = mode
        self.label_type = label_type
        self.threshold = threshold
        self.vol_window = vol_window
        self.lower_q = lower_q
        self.upper_q = upper_q
        self.status = 'pending'
        self.progress = 0
        self.message = ''
        self.test_metrics = {}
        self.validation_metrics = {}
        self.details = {}
        self.start_time = 0
        self.end_time = 0

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'model_id': self.model_id,
            'horizon': self.horizon,
            'sectors': self.sectors,
            'stocks': self.stocks,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'validation_ratio': self.validation_ratio,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'test_metrics': self.test_metrics,
            'validation_metrics': self.validation_metrics,
            'details': self.details,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'mode': self.mode,
            'label_type': self.label_type,
            'model_name': self.model_info.get('model_name', ''),
            'model_type': self.model_info.get('model_type', ''),
            'elapsed_time': round(self.end_time - self.start_time, 2) if self.end_time > 0 and self.start_time > 0 else 0
        }


class ModelEvaluator:
    def __init__(self):
        self.tasks = {}
        self._lock = threading.Lock()

    def create_task(self, model_id, sectors, start_date, end_date, validation_ratio=0.2):
        from backend.ml import ModelRegistry

        registry = ModelRegistry()
        model_info = registry.get_model_by_id(model_id)
        if not model_info:
            model_info = registry.get_model_by_parent_id(model_id)
        if not model_info:
            sub_models = registry.get_models_by_parent_id(model_id)
            if sub_models:
                model_info = sub_models[0]
        if not model_info:
            raise ValueError(f'模型不存在: {model_id}')

        stocks = []
        for sector_key in sectors:
            sector_stocks = self._get_sector_stocks(sector_key)
            stocks.extend(sector_stocks)
        stocks = sorted(list(set(stocks)))

        if not stocks:
            raise ValueError('所选板块中没有找到股票')

        horizon = model_info.get('horizon', 5)
        mode = model_info.get('mode', 'classification')
        label_type = model_info.get('label_type', 'fixed')
        threshold = model_info.get('threshold', 0.02)
        vol_window = model_info.get('vol_window', 20)
        lower_q = model_info.get('lower_q', 0.2)
        upper_q = model_info.get('upper_q', 0.8)

        if mode == 'regression':
            label_type = 'regression'

        task_id = uuid.uuid4().hex[:8]
        task = EvaluationTask(
            task_id=task_id,
            model_id=model_id,
            horizon=horizon,
            sectors=sectors,
            stocks=stocks,
            start_date=start_date,
            end_date=end_date,
            validation_ratio=validation_ratio,
            model_info=model_info,
            mode=mode,
            label_type=label_type,
            threshold=threshold,
            vol_window=vol_window,
            lower_q=lower_q,
            upper_q=upper_q
        )

        with self._lock:
            self.tasks[task_id] = task

        _log(f'[评估] 任务创建: task_id={task_id}, model_id={model_id}, stocks={len(stocks)}, '
             f'start_date={start_date}, end_date={end_date}, validation_ratio={validation_ratio}')

        return task_id

    def _get_sector_stocks(self, sector_key):
        sector_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sector')
        sector_file = os.path.join(sector_base, sector_key)

        if not os.path.exists(sector_file):
            _log(f'[评估] 板块文件不存在: {sector_file}', 'WARN')
            return []

        try:
            with open(sector_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            stocks = list(set(s.strip() for s in content.split(',') if s.strip()))
            return stocks
        except Exception as e:
            _log(f'[评估] 读取板块文件失败: {e}', 'ERROR')
            return []

    def run_evaluation(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = 'running'
        task.progress = 0
        task.message = '开始评估...'
        task.start_time = time.time()

        try:
            task.progress = 5
            task.message = f'加载模型...'

            model, ensemble_models = self._load_model(task.model_info)

            task.progress = 10
            task.message = f'加载 {len(task.stocks)} 只股票的数据并计算特征...'

            X_test, y_test, X_val, y_val, details = self._load_and_prepare_data(task)

            task.details = details

            if len(X_test) == 0:
                task.status = 'failed'
                task.message = '测试集数据为空，无法评估'
                task.end_time = time.time()
                return

            task.progress = 70
            task.message = '评估测试集...'

            test_metrics = self._evaluate_model(model, ensemble_models, X_test, y_test, task.mode)
            task.test_metrics = test_metrics

            task.progress = 85
            task.message = '评估验证集...'

            if len(X_val) > 0:
                val_metrics = self._evaluate_model(model, ensemble_models, X_val, y_val, task.mode)
                task.validation_metrics = val_metrics
            else:
                task.validation_metrics = {'message': '验证集数据不足，无法评估'}

            task.progress = 100
            task.status = 'completed'
            task.message = '评估完成'
            task.end_time = time.time()

            _log(f'[评估] 任务完成: task_id={task_id}, '
                 f'测试集样本={len(X_test)}, 验证集样本={len(X_val)}, '
                 f'耗时={task.end_time - task.start_time:.2f}秒')

        except Exception as e:
            task.status = 'failed'
            task.message = f'评估失败: {str(e)}'
            task.end_time = time.time()
            _log(f'[评估] 任务失败: task_id={task_id}, error={e}', 'ERROR')
            traceback.print_exc()

    def _load_model(self, model_info):
        from backend.ml import ModelTrainer, ModelRegistry
        import pickle

        trainer = ModelTrainer()
        ensemble_models = None
        parent_model_id = model_info.get('parent_model_id')

        if parent_model_id:
            registry = ModelRegistry()
            all_models = registry.get_all_models()
            ensemble_models = {}
            for m in all_models:
                if m.get('parent_model_id') == parent_model_id:
                    try:
                        sub_model = trainer.load_model(m['file_path'])
                        ensemble_models[m['model_type']] = sub_model
                    except Exception as e:
                        _log(f'[评估] 加载子模型失败: {m["model_type"]}, error={e}', 'WARN')

            if len(ensemble_models) > 1:
                _log(f'[评估] 使用集成模式，加载了 {len(ensemble_models)} 个子模型')
                model = None
            else:
                ensemble_models = None
                model = trainer.load_model(model_info['file_path'])
        elif model_info.get('is_ensemble'):
            registry = ModelRegistry()
            all_models = registry.get_all_models()
            ensemble_models = {}
            for m in all_models:
                if m.get('parent_model_id') == model_info.get('id'):
                    try:
                        sub_model = trainer.load_model(m['file_path'])
                        ensemble_models[m['model_type']] = sub_model
                    except Exception as e:
                        _log(f'[评估] 加载子模型失败: {m["model_type"]}, error={e}', 'WARN')

            if len(ensemble_models) > 1:
                _log(f'[评估] 使用集成模式，加载了 {len(ensemble_models)} 个子模型')
                model = None
            else:
                ensemble_models = None
                model = trainer.load_model(model_info['file_path'])
        else:
            model = trainer.load_model(model_info['file_path'])

        return model, ensemble_models

    def _load_and_prepare_data(self, task):
        from backend.ml import MLDataLoader, FeatureEngineer

        data_loader = MLDataLoader()
        feature_engineer = FeatureEngineer()

        model_features = task.model_info.get('features', [])
        scaler_params = task.model_info.get('scaler_params')

        start_dt = pd.to_datetime(task.start_date)
        end_dt = pd.to_datetime(task.end_date)

        all_test_features = []
        all_test_labels = []
        all_val_features = []
        all_val_labels = []
        stock_sample_counts = {}
        processed_stocks = 0
        total_stocks = len(task.stocks)

        def process_stock(stock_code):
            try:
                code_only = stock_code.split('.')[0]

                raw_data = data_loader.load_stock_data(
                    code_only, start_date=None, end_date=task.end_date,
                    period='1d'
                )

                if len(raw_data) < 100:
                    return None

                fe = FeatureEngineer()

                if task.label_type == 'regression':
                    X, y = fe.prepare_data_regression(
                        raw_data, model_features, task.horizon,
                        normalize=False, stock_code=stock_code, data_source='csv'
                    )
                elif task.label_type == 'volatility':
                    X, y = fe.prepare_data_with_volatility(
                        raw_data, model_features, task.horizon,
                        task.vol_window, task.lower_q, task.upper_q,
                        normalize=False, stock_code=stock_code, data_source='csv'
                    )
                elif task.label_type == 'multi':
                    X, y = fe.prepare_data_multi(
                        raw_data, model_features, task.horizon,
                        task.lower_q, task.upper_q,
                        normalize=False, stock_code=stock_code, data_source='csv'
                    )
                else:
                    X, y = fe.prepare_data(
                        raw_data, model_features, task.horizon, task.threshold,
                        normalize=False, stock_code=stock_code, data_source='csv'
                    )

                if len(X) == 0:
                    return None

                if scaler_params:
                    mean = np.array(scaler_params['mean'])
                    scale = np.array(scaler_params['scale'])
                    feature_order = scaler_params.get('feature_names', model_features)

                    available_in_order = [f for f in feature_order if f in X.columns]
                    if available_in_order and len(mean) == len(feature_order) and len(scale) == len(feature_order):
                        X_ordered = X[available_in_order].values
                        scale_subset = np.array([scale[feature_order.index(f)] for f in available_in_order])
                        mean_subset = np.array([mean[feature_order.index(f)] for f in available_in_order])
                        X_normalized = (X_ordered - mean_subset) / scale_subset
                        X = pd.DataFrame(X_normalized, index=X.index, columns=available_in_order)

                test_mask = (X.index >= start_dt) & (X.index <= end_dt)
                early_mask = X.index < start_dt

                X_test_stock = X[test_mask]
                y_test_stock = y[test_mask]
                X_early_stock = X[early_mask]
                y_early_stock = y[early_mask]

                val_count = int(len(X_test_stock) * task.validation_ratio)
                X_val_stock = pd.DataFrame()
                y_val_stock = pd.Series()

                if val_count > 0 and len(X_early_stock) > 0:
                    actual_val_count = min(val_count, len(X_early_stock))
                    val_indices = random.sample(range(len(X_early_stock)), actual_val_count)
                    X_val_stock = X_early_stock.iloc[val_indices]
                    y_val_stock = y_early_stock.iloc[val_indices]

                return {
                    'stock_code': stock_code,
                    'X_test': X_test_stock,
                    'y_test': y_test_stock,
                    'X_val': X_val_stock,
                    'y_val': y_val_stock,
                    'test_count': len(X_test_stock),
                    'val_count': len(X_val_stock)
                }

            except FileNotFoundError:
                _log(f'[评估] {stock_code} 数据文件不存在，跳过', 'WARN')
                return None
            except Exception as e:
                _log(f'[评估] {stock_code} 处理失败: {e}', 'WARN')
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_stock, stock): stock for stock in task.stocks}

            for future in as_completed(futures):
                stock_code = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        all_test_features.append(result['X_test'])
                        all_test_labels.append(result['y_test'])
                        all_val_features.append(result['X_val'])
                        all_val_labels.append(result['y_val'])
                        stock_sample_counts[result['stock_code']] = {
                            'test': result['test_count'],
                            'val': result['val_count']
                        }
                except Exception as e:
                    _log(f'[评估] {stock_code} 处理异常: {e}', 'ERROR')

                processed_stocks += 1
                progress = 10 + int((processed_stocks / total_stocks) * 55)
                task.progress = progress
                task.message = f'处理股票数据 ({processed_stocks}/{total_stocks})...'

        sorted_stocks = sorted(stock_sample_counts.keys())
        sorted_test_X = []
        sorted_test_y = []
        sorted_val_X = []
        sorted_val_y = []

        for stock_code in sorted_stocks:
            for i, (X_test, y_test) in enumerate(zip(all_test_features, all_test_labels)):
                if len(X_test) > 0 and stock_sample_counts.get(stock_code, {}).get('test', 0) == len(X_test):
                    sorted_test_X.append(X_test)
                    sorted_test_y.append(y_test)
                    break

        for stock_code in sorted_stocks:
            for i, (X_val, y_val) in enumerate(zip(all_val_features, all_val_labels)):
                if len(X_val) > 0 and stock_sample_counts.get(stock_code, {}).get('val', 0) == len(X_val):
                    sorted_val_X.append(X_val)
                    sorted_val_y.append(y_val)
                    break

        X_test_combined = pd.concat(sorted_test_X, ignore_index=True) if sorted_test_X else pd.DataFrame()
        y_test_combined = pd.concat(sorted_test_y, ignore_index=True) if sorted_test_y else pd.Series()
        X_val_combined = pd.concat(sorted_val_X, ignore_index=True) if sorted_val_X else pd.DataFrame()
        y_val_combined = pd.concat(sorted_val_y, ignore_index=True) if sorted_val_y else pd.Series()

        details = {
            'total_stocks': len(task.stocks),
            'processed_stocks': len(stock_sample_counts),
            'test_samples': len(X_test_combined),
            'validation_samples': len(X_val_combined),
            'stock_sample_counts': stock_sample_counts
        }

        return X_test_combined, y_test_combined, X_val_combined, y_val_combined, details

    def _evaluate_model(self, model, ensemble_models, X, y, mode):
        if len(X) == 0:
            return {'message': '数据为空'}

        try:
            if mode == 'regression':
                return self._evaluate_regression(model, ensemble_models, X, y)
            else:
                return self._evaluate_classification(model, ensemble_models, X, y)
        except Exception as e:
            _log(f'[评估] 评估失败: {e}', 'ERROR')
            traceback.print_exc()
            return {'error': str(e)}

    def _evaluate_classification(self, model, ensemble_models, X, y):
        if ensemble_models and len(ensemble_models) > 1:
            all_probs = []
            predictions = {}
            for name, m in ensemble_models.items():
                try:
                    pred = m.predict(X)
                    probs = m.predict_proba(X)
                    predictions[name] = pred
                    all_probs.append(probs)
                except Exception as e:
                    _log(f'[评估] 子模型 {name} 预测失败: {e}', 'WARN')

            if not all_probs:
                return {'error': '所有子模型预测失败'}

            avg_probs = np.mean(all_probs, axis=0)
            y_pred = np.argmax(avg_probs, axis=1)
        else:
            y_pred = model.predict(X)

        y_true = y.values if hasattr(y, 'values') else y
        y_pred = np.array(y_pred)

        valid_mask = ~(pd.isna(y_true) | pd.isna(y_pred))
        y_true = y_true[valid_mask]
        y_pred = y_pred[valid_mask]

        if len(y_true) == 0:
            return {'message': '无有效预测结果'}

        metrics = {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'precision': float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
            'recall': float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
            'f1': float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
            'total_samples': int(len(y_true))
        }

        unique_labels = sorted(set(y_true) | set(y_pred))
        label_map = {0: '卖出', 1: '持有', 2: '买入'}
        if len(unique_labels) > 3:
            label_map = {0: '强烈卖出', 1: '轻度卖出', 2: '持有', 3: '轻度买入', 4: '强烈买入'}

        per_class = {}
        for label in unique_labels:
            label_name = label_map.get(int(label), f'类别{label}')
            mask_true = (y_true == label)
            mask_pred = (y_pred == label)
            tp = int(np.sum(mask_true & mask_pred))
            fp = int(np.sum(~mask_true & mask_pred))
            fn = int(np.sum(mask_true & ~mask_pred))
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            per_class[label_name] = {
                'precision': float(precision),
                'recall': float(recall),
                'f1': float(f1),
                'support': int(np.sum(mask_true))
            }

        metrics['per_class'] = per_class

        return metrics

    def _evaluate_regression(self, model, ensemble_models, X, y):
        if ensemble_models and len(ensemble_models) > 1:
            predictions = {}
            for name, m in ensemble_models.items():
                try:
                    predictions[name] = m.predict(X)
                except Exception as e:
                    _log(f'[评估] 子模型 {name} 预测失败: {e}', 'WARN')

            if not predictions:
                return {'error': '所有子模型预测失败'}

            pred_array = np.array(list(predictions.values()))
            y_pred = np.mean(pred_array, axis=0)
        else:
            y_pred = model.predict(X)

        y_true = y.values if hasattr(y, 'values') else y
        y_pred = np.array(y_pred)

        valid_mask = ~(pd.isna(y_true) | pd.isna(y_pred))
        y_true = y_true[valid_mask]
        y_pred = y_pred[valid_mask]

        if len(y_true) == 0:
            return {'message': '无有效预测结果'}

        direction_correct = int(np.sum((y_true > 0) == (y_pred > 0)))
        direction_accuracy = direction_correct / len(y_true) if len(y_true) > 0 else 0

        metrics = {
            'mse': float(mean_squared_error(y_true, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
            'mae': float(mean_absolute_error(y_true, y_pred)),
            'r2': float(r2_score(y_true, y_pred)),
            'direction_accuracy': float(direction_accuracy),
            'total_samples': int(len(y_true))
        }

        return metrics

    def get_task(self, task_id):
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                return task.to_dict()
            return None

    def get_all_tasks(self):
        with self._lock:
            return [task.to_dict() for task in self.tasks.values()]


_global_eval_tasks = {}
_global_eval_lock = threading.Lock()


def register_eval_task(task_id, evaluator):
    with _global_eval_lock:
        _global_eval_tasks[task_id] = evaluator


def get_task_evaluator(task_id):
    with _global_eval_lock:
        return _global_eval_tasks.get(task_id)


def get_all_evaluators():
    with _global_eval_lock:
        return list(_global_eval_tasks.values())

import os
import pickle
import uuid
import time
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, mean_absolute_error, r2_score
import lightgbm as lgb


def _log(message, level='INFO'):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f'[{timestamp}] [{level}] {message}')


class ModelTrainer:
    def __init__(self, models_dir=None, progress_callback=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        self.models_dir = models_dir
        self.progress_callback = progress_callback
        os.makedirs(self.models_dir, exist_ok=True)
    
    def _report_progress(self, message, progress=None):
        if self.progress_callback:
            self.progress_callback(message, progress)
        _log(message)

    def train(self, X, y, model_type='RandomForest', mode='classification', use_gpu=False, fast_mode=False, **kwargs):
        if mode == 'regression':
            return self._train_regressor(X, y, model_type, use_gpu=use_gpu, fast_mode=fast_mode, **kwargs)
        return self._train_classifier(X, y, model_type, use_gpu=use_gpu, fast_mode=fast_mode, **kwargs)

    def _train_classifier(self, X, y, model_type='RandomForest', use_gpu=False, fast_mode=False, **kwargs):
        n_estimators = kwargs.get('n_estimators', 50 if fast_mode else 100)
        max_depth = kwargs.get('max_depth', 8 if fast_mode else 10)
        
        self._report_progress(f'[训练] 开始训练分类模型: {model_type}')
        self._report_progress(f'[训练] 参数: n_estimators={n_estimators}, max_depth={max_depth}, use_gpu={use_gpu}')
        self._report_progress(f'[训练] 样本数: {len(X)}, 特征数: {X.shape[1]}')
        train_start = time.time()
        
        if model_type == 'RandomForest':
            if use_gpu:
                try:
                    from cuml.ensemble import RandomForestClassifier as cuRF
                    self._report_progress('[训练] 使用 GPU (cuML) RandomForest 分类器')
                    model = cuRF(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=kwargs.get('random_state', 42)
                    )
                except ImportError:
                    self._report_progress('[训练] cuML 未安装，回退到 CPU RandomForest', 'WARN')
                    model = RandomForestClassifier(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=kwargs.get('random_state', 42),
                        n_jobs=-1
                    )
            else:
                self._report_progress('[训练] 使用 CPU RandomForest 分类器')
                model = RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1
                )
        elif model_type == 'LightGBM':
            self._report_progress(f'[训练] 使用 {"GPU" if use_gpu else "CPU"} LightGBM 分类器')
            model = lgb.LGBMClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=kwargs.get('learning_rate', 0.1),
                num_leaves=kwargs.get('num_leaves', 15 if fast_mode else 31),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1,
                device='gpu' if use_gpu else 'cpu',
                verbose=-1
            )
        else:
            raise ValueError(f'不支持的分类模型类型: {model_type}')

        model.fit(X, y)
        train_time = time.time() - train_start
        self._report_progress(f'[训练] {model_type} 分类模型训练完成，耗时 {train_time:.2f}秒')
        return model

    def _train_regressor(self, X, y, model_type='RandomForest', use_gpu=False, fast_mode=False, **kwargs):
        n_estimators = kwargs.get('n_estimators', 50 if fast_mode else 100)
        max_depth = kwargs.get('max_depth', 8 if fast_mode else 10)
        
        self._report_progress(f'[训练] 开始训练回归模型: {model_type}')
        self._report_progress(f'[训练] 参数: n_estimators={n_estimators}, max_depth={max_depth}, use_gpu={use_gpu}')
        self._report_progress(f'[训练] 样本数: {len(X)}, 特征数: {X.shape[1]}')
        train_start = time.time()
        
        if model_type == 'RandomForest':
            if use_gpu:
                try:
                    from cuml.ensemble import RandomForestRegressor as cuRF
                    self._report_progress('[训练] 使用 GPU (cuML) RandomForest 回归器')
                    model = cuRF(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=kwargs.get('random_state', 42)
                    )
                except ImportError:
                    self._report_progress('[训练] cuML 未安装，回退到 CPU RandomForest', 'WARN')
                    model = RandomForestRegressor(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=kwargs.get('random_state', 42),
                        n_jobs=-1
                    )
            else:
                self._report_progress('[训练] 使用 CPU RandomForest 回归器')
                model = RandomForestRegressor(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1
                )
        elif model_type == 'LightGBM':
            self._report_progress(f'[训练] 使用 {"GPU" if use_gpu else "CPU"} LightGBM 回归器')
            model = lgb.LGBMRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=kwargs.get('learning_rate', 0.1),
                num_leaves=kwargs.get('num_leaves', 15 if fast_mode else 31),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1,
                device='gpu' if use_gpu else 'cpu',
                verbose=-1
            )
        elif model_type == 'Ridge':
            if use_gpu:
                try:
                    from cuml.linear_model import Ridge as cuRidge
                    self._report_progress('[训练] 使用 GPU (cuML) Ridge 回归器')
                    model = cuRidge(alpha=kwargs.get('alpha', 1.0))
                except ImportError:
                    self._report_progress('[训练] cuML 未安装，回退到 CPU Ridge', 'WARN')
                    model = Ridge(alpha=kwargs.get('alpha', 1.0), random_state=kwargs.get('random_state', 42))
            else:
                self._report_progress('[训练] 使用 CPU Ridge 回归器')
                model = Ridge(alpha=kwargs.get('alpha', 1.0), random_state=kwargs.get('random_state', 42))
        else:
            raise ValueError(f'不支持的回归模型类型: {model_type}')

        model.fit(X, y)
        train_time = time.time() - train_start
        self._report_progress(f'[训练] {model_type} 回归模型训练完成，耗时 {train_time:.2f}秒')
        return model

    def evaluate(self, model, X, y, mode='classification'):
        if mode == 'regression':
            y_pred = model.predict(X)
            return {
                'mse': float(mean_squared_error(y, y_pred)),
                'rmse': float(np.sqrt(mean_squared_error(y, y_pred))),
                'mae': float(mean_absolute_error(y, y_pred)),
                'r2': float(r2_score(y, y_pred))
            }
        y_pred = model.predict(X)
        return {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y, y_pred, average='weighted', zero_division=0)
        }

    def train_with_split(self, X, y, model_type='RandomForest', mode='classification', test_size=0.2, use_gpu=False, fast_mode=False, **kwargs):
        self._report_progress(f'[单模型训练] 开始训练，模型: {model_type}, 模式: {mode}')
        self._report_progress(f'[单模型训练] 样本数: {len(X)}, 特征数: {X.shape[1]}')
        split_start = time.time()
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        self._report_progress(f'[单模型训练] 数据分割完成，训练集: {len(X_train)}, 测试集: {len(X_test)}')

        model = self.train(X_train, y_train, model_type, mode=mode, use_gpu=use_gpu, fast_mode=fast_mode, **kwargs)

        self._report_progress('[单模型训练] 开始评估模型...')
        train_metrics = self.evaluate(model, X_train, y_train, mode=mode)
        test_metrics = self.evaluate(model, X_test, y_test, mode=mode)
        
        split_time = time.time() - split_start
        self._report_progress(f'[单模型训练] 完成，总耗时 {split_time:.2f}秒')
        if mode == 'regression':
            self._report_progress(f'[单模型训练] 测试集 R2: {test_metrics["r2"]:.4f}, RMSE: {test_metrics["rmse"]:.4f}')
        else:
            self._report_progress(f'[单模型训练] 测试集 Accuracy: {test_metrics["accuracy"]:.4f}, F1: {test_metrics["f1"]:.4f}')

        return {
            'model': model,
            'train_metrics': train_metrics,
            'test_metrics': test_metrics
        }

    def train_ensemble(self, X, y, mode='regression', test_size=0.2, use_gpu=False, fast_mode=False, **kwargs):
        self._report_progress(f'[集成训练] 开始集成训练，模式: {mode}')
        self._report_progress(f'[集成训练] 样本数: {len(X)}, 特征数: {X.shape[1]}')
        ensemble_start = time.time()
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        self._report_progress(f'[集成训练] 数据分割完成，训练集: {len(X_train)}, 测试集: {len(X_test)}')

        if mode == 'regression':
            model_types = ['RandomForest', 'LightGBM']  # 移除Ridge，因为线性模型不适合预测非线性关系的股票收益
            models = {}
            for i, mt in enumerate(model_types, 1):
                self._report_progress(f'[集成训练] 训练第 {i}/{len(model_types)} 个模型: {mt}')
                models[mt] = self._train_regressor(X_train, y_train, mt, use_gpu=use_gpu, fast_mode=fast_mode, **kwargs)
        else:
            model_types = ['RandomForest', 'LightGBM']
            models = {}
            for i, mt in enumerate(model_types, 1):
                self._report_progress(f'[集成训练] 训练第 {i}/{len(model_types)} 个模型: {mt}')
                models[mt] = self._train_classifier(X_train, y_train, mt, use_gpu=use_gpu, fast_mode=fast_mode, **kwargs)

        self._report_progress('[集成训练] 开始评估模型...')
        train_metrics = {name: self.evaluate(m, X_train, y_train, mode=mode) for name, m in models.items()}
        test_metrics = {name: self.evaluate(m, X_test, y_test, mode=mode) for name, m in models.items()}
        
        ensemble_time = time.time() - ensemble_start
        self._report_progress(f'[集成训练] 完成，总耗时 {ensemble_time:.2f}秒')
        for name, metrics in test_metrics.items():
            if mode == 'regression':
                self._report_progress(f'[集成训练] {name} 测试集 R2: {metrics["r2"]:.4f}, RMSE: {metrics["rmse"]:.4f}')
            else:
                self._report_progress(f'[集成训练] {name} 测试集 Accuracy: {metrics["accuracy"]:.4f}, F1: {metrics["f1"]:.4f}')

        return {
            'models': models,
            'train_metrics': train_metrics,
            'test_metrics': test_metrics
        }

    def train_incremental(self, base_model_path, X_new, y_new, model_type='RandomForest', mode='classification', **kwargs):
        if not os.path.exists(base_model_path):
            raise FileNotFoundError(f'基础模型不存在: {base_model_path}')

        with open(base_model_path, 'rb') as f:
            base_model = pickle.load(f)

        if mode == 'regression':
            if model_type == 'RandomForest':
                n_estimators = kwargs.get('n_estimators', base_model.n_estimators + 20)
                new_model = RandomForestRegressor(
                    n_estimators=n_estimators,
                    max_depth=kwargs.get('max_depth', 10),
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1,
                    warm_start=True
                )
            elif model_type == 'LightGBM':
                n_estimators = kwargs.get('n_estimators', base_model.n_estimators + 20)
                new_model = lgb.LGBMRegressor(
                    n_estimators=n_estimators,
                    max_depth=kwargs.get('max_depth', 10),
                    learning_rate=kwargs.get('learning_rate', 0.1),
                    num_leaves=kwargs.get('num_leaves', 31),
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1,
                    verbose=-1
                )
            else:
                raise ValueError(f'不支持的回归模型类型: {model_type}')
        else:
            if model_type == 'RandomForest':
                n_estimators = kwargs.get('n_estimators', base_model.n_estimators + 20)
                new_model = RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=kwargs.get('max_depth', 10),
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1,
                    warm_start=True
                )
            elif model_type == 'LightGBM':
                n_estimators = kwargs.get('n_estimators', base_model.n_estimators + 20)
                new_model = lgb.LGBMClassifier(
                    n_estimators=n_estimators,
                    max_depth=kwargs.get('max_depth', 10),
                    learning_rate=kwargs.get('learning_rate', 0.1),
                    num_leaves=kwargs.get('num_leaves', 31),
                    random_state=kwargs.get('random_state', 42),
                    n_jobs=-1,
                    verbose=-1
                )
            else:
                raise ValueError(f'不支持的分类模型类型: {model_type}')

        all_X = pd.concat([X_new], ignore_index=True)
        all_y = pd.concat([y_new], ignore_index=True)

        new_model.fit(all_X, all_y)
        return new_model

    def save_model(self, model, filename):
        filepath = os.path.join(self.models_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
        return filepath

    def save_ensemble(self, ensemble_models, filename):
        filepath = os.path.join(self.models_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(ensemble_models, f)
        return filepath

    def load_model(self, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'模型文件不存在: {filepath}')
        with open(filepath, 'rb') as f:
            return pickle.load(f)

import os
import pickle
import uuid
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, mean_absolute_error, r2_score
import lightgbm as lgb


class ModelTrainer:
    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

    def train(self, X, y, model_type='RandomForest', mode='classification', **kwargs):
        if mode == 'regression':
            return self._train_regressor(X, y, model_type, **kwargs)
        return self._train_classifier(X, y, model_type, **kwargs)

    def _train_classifier(self, X, y, model_type='RandomForest', **kwargs):
        if model_type == 'RandomForest':
            model = RandomForestClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1
            )
        elif model_type == 'LightGBM':
            model = lgb.LGBMClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                learning_rate=kwargs.get('learning_rate', 0.1),
                num_leaves=kwargs.get('num_leaves', 31),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1,
                verbose=-1
            )
        else:
            raise ValueError(f'不支持的分类模型类型: {model_type}')

        model.fit(X, y)
        return model

    def _train_regressor(self, X, y, model_type='RandomForest', **kwargs):
        if model_type == 'RandomForest':
            model = RandomForestRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1
            )
        elif model_type == 'LightGBM':
            model = lgb.LGBMRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                learning_rate=kwargs.get('learning_rate', 0.1),
                num_leaves=kwargs.get('num_leaves', 31),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1,
                verbose=-1
            )
        elif model_type == 'Ridge':
            alpha = kwargs.get('alpha', 1.0)
            model = Ridge(alpha=alpha, random_state=kwargs.get('random_state', 42))
        else:
            raise ValueError(f'不支持的回归模型类型: {model_type}')

        model.fit(X, y)
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

    def train_with_split(self, X, y, model_type='RandomForest', mode='classification', test_size=0.2, **kwargs):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

        model = self.train(X_train, y_train, model_type, mode=mode, **kwargs)

        train_metrics = self.evaluate(model, X_train, y_train, mode=mode)
        test_metrics = self.evaluate(model, X_test, y_test, mode=mode)

        return {
            'model': model,
            'train_metrics': train_metrics,
            'test_metrics': test_metrics
        }

    def train_ensemble(self, X, y, mode='regression', test_size=0.2, **kwargs):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

        if mode == 'regression':
            models = {
                'RandomForest': self._train_regressor(X_train, y_train, 'RandomForest', **kwargs),
                'LightGBM': self._train_regressor(X_train, y_train, 'LightGBM', **kwargs),
                'Ridge': self._train_regressor(X_train, y_train, 'Ridge', **kwargs)
            }
        else:
            models = {
                'RandomForest': self._train_classifier(X_train, y_train, 'RandomForest', **kwargs),
                'LightGBM': self._train_classifier(X_train, y_train, 'LightGBM', **kwargs)
            }

        train_metrics = {name: self.evaluate(m, X_train, y_train, mode=mode) for name, m in models.items()}
        test_metrics = {name: self.evaluate(m, X_test, y_test, mode=mode) for name, m in models.items()}

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

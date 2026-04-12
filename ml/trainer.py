import os
import pickle
import uuid
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


class ModelTrainer:
    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

    def train(self, X, y, model_type='RandomForest', **kwargs):
        if model_type == 'RandomForest':
            model = RandomForestClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1
            )
        else:
            raise ValueError(f'不支持的模型类型: {model_type}')

        model.fit(X, y)
        return model

    def evaluate(self, model, X, y):
        y_pred = model.predict(X)
        return {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y, y_pred, average='weighted', zero_division=0)
        }

    def train_with_split(self, X, y, model_type='RandomForest', test_size=0.2, **kwargs):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

        model = self.train(X_train, y_train, model_type, **kwargs)

        train_metrics = self.evaluate(model, X_train, y_train)
        test_metrics = self.evaluate(model, X_test, y_test)

        return {
            'model': model,
            'train_metrics': train_metrics,
            'test_metrics': test_metrics
        }

    def train_incremental(self, base_model_path, X_new, y_new, model_type='RandomForest', **kwargs):
        if not os.path.exists(base_model_path):
            raise FileNotFoundError(f'基础模型不存在: {base_model_path}')

        with open(base_model_path, 'rb') as f:
            base_model = pickle.load(f)

        if model_type == 'RandomForest':
            n_estimators = kwargs.get('n_estimators', base_model.n_estimators + 20)
            new_model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=kwargs.get('max_depth', 10),
                random_state=kwargs.get('random_state', 42),
                n_jobs=-1,
                warm_start=True
            )

            all_X = pd.concat([X_new], ignore_index=True)
            all_y = pd.concat([y_new], ignore_index=True)

            new_model.fit(all_X, all_y)
            return new_model
        else:
            raise ValueError(f'不支持的模型类型: {model_type}')

    def save_model(self, model, filename):
        filepath = os.path.join(self.models_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
        return filepath

    def load_model(self, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'模型文件不存在: {filepath}')
        with open(filepath, 'rb') as f:
            return pickle.load(f)

import os
import json
import uuid
import pickle
from datetime import datetime


class ModelRegistry:
    def __init__(self, registry_path=None, models_dir=None):
        if registry_path is None:
            registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'model_registry.json')
        if models_dir is None:
            models_dir = os.path.dirname(registry_path)
        self.registry_path = registry_path
        self.models_dir = models_dir
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        self._ensure_registry()

    def _ensure_registry(self):
        if not os.path.exists(self.registry_path):
            with open(self.registry_path, 'w') as f:
                json.dump({'models': []}, f, indent=2)

    def _load_registry(self):
        with open(self.registry_path, 'r') as f:
            return json.load(f)

    def _save_registry(self, data):
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def register_model(self, stock_code, start_date, end_date, model_type, features,
                      file_path, metrics, parent_model_id=None, incremental_data=None,
                      scaler_params=None, model_name=None, label_type='fixed',
                      horizon=5, threshold=0.02, vol_window=20, lower_q=0.2, upper_q=0.8,
                      mode='classification', is_ensemble=False):
        data = self._load_registry()

        model_info = {
            'id': str(uuid.uuid4()),
            'stock_code': stock_code,
            'model_name': model_name,
            'start_date': start_date,
            'end_date': end_date,
            'model_type': model_type,
            'features': features,
            'feature_count': len(features),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': metrics,
            'file_path': file_path,
            'parent_model_id': parent_model_id,
            'incremental_data': incremental_data or [],
            'scaler_params': scaler_params,
            'label_type': label_type,
            'horizon': horizon,
            'threshold': threshold,
            'vol_window': vol_window,
            'lower_q': lower_q,
            'upper_q': upper_q,
            'mode': mode,
            'is_ensemble': is_ensemble
        }

        data['models'].append(model_info)
        self._save_registry(data)

        return model_info

    def find_existing_model(self, stock_code, start_date, end_date, model_type, features):
        data = self._load_registry()

        for model in data['models']:
            if (model['stock_code'] == stock_code and
                model['start_date'] == start_date and
                model['end_date'] == end_date and
                model['model_type'] == model_type and
                model['features'] == features):
                return model

        return None

    def get_all_models(self):
        data = self._load_registry()
        models = data.get('models', [])
        return sorted(models, key=lambda x: x.get('created_at', ''), reverse=True)

    def get_models_by_stock(self, stock_code):
        data = self._load_registry()
        return [m for m in data['models'] if m['stock_code'] == stock_code]

    def get_model_by_id(self, model_id):
        data = self._load_registry()
        for model in data['models']:
            if model['id'] == model_id or model['model_name'] == model_id:
                return model

        filepath = os.path.join(self.models_dir, f'{model_id}.pkl')
        if os.path.exists(filepath):
            model_info = {
                'id': model_id,
                'model_name': model_id,
                'file_path': filepath,
                'model_type': 'Unknown',
                'features': [],
                'feature_count': 0,
                'mode': 'classification',
                'threshold': 0.02
            }
            try:
                with open(filepath, 'rb') as f:
                    model = pickle.load(f)
                    model_info['model_type'] = type(model).__name__
                    if hasattr(model, 'feature_names_in_'):
                        model_info['features'] = list(model.feature_names_in_)
                        model_info['feature_count'] = len(model.feature_names_in_)
                    elif hasattr(model, 'features'):
                        model_info['features'] = model.features
                        model_info['feature_count'] = len(model.features)
            except Exception as e:
                print(f'Error loading model {filepath}: {e}')
            return model_info
        return None

    def get_model_by_parent_id(self, parent_id: str):
        """通过 parent_model_id 获取第一个模型信息"""
        data = self._load_registry()
        for m in data['models']:
            if m.get('parent_model_id') == parent_id:
                return m
        return None

    def get_models_by_parent_id(self, parent_id: str):
        """通过 parent_model_id 获取所有子模型"""
        data = self._load_registry()
        return [m for m in data['models'] if m.get('parent_model_id') == parent_id]

    def delete_model(self, model_id):
        data = self._load_registry()
        model_to_delete = None

        for m in data['models']:
            if m['id'] == model_id or m['model_name'] == model_id or m.get('parent_model_id') == model_id:
                model_to_delete = m
                break

        deleted_from_registry = False
        deleted_from_disk = False

        if model_to_delete:
            parent_id = model_to_delete.get('parent_model_id')
            if parent_id:
                models_to_delete = [x for x in data['models'] if x.get('parent_model_id') == parent_id]
            else:
                models_to_delete = [model_to_delete]

            for m in models_to_delete:
                filepath = m.get('file_path')
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        print(f'Deleted model file: {filepath}')
                        deleted_from_disk = True
                    except Exception as e:
                        print(f'Error deleting model file {filepath}: {e}')

            model_ids_to_remove = set(x['id'] for x in models_to_delete)
            model_names_to_remove = set(x.get('model_name', '') for x in models_to_delete)
            data['models'] = [m for m in data['models'] if m['id'] not in model_ids_to_remove and m.get('model_name', '') not in model_names_to_remove]
            deleted_from_registry = True
            self._save_registry(data)
        else:
            filepath = os.path.join(self.models_dir, f'{model_id}.pkl')
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted_from_disk = True
                    print(f'Deleted orphaned model file: {filepath}')
                except Exception as e:
                    print(f'Error deleting orphaned model file {filepath}: {e}')

        return deleted_from_registry or deleted_from_disk

    def update_incremental_data(self, model_id, new_incremental_data):
        data = self._load_registry()

        for model in data['models']:
            if model['id'] == model_id:
                model['incremental_data'].append(new_incremental_data)
                self._save_registry(data)
                return model

        return None

    def get_feature_importance(self, model_id):
        model_info = self.get_model_by_id(model_id)
        if not model_info:
            return None

        return {
            'features': model_info.get('features', []),
            'feature_count': model_info.get('feature_count', 0)
        }
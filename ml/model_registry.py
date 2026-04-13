import os
import json
import uuid
from datetime import datetime


class ModelRegistry:
    def __init__(self, registry_path=None):
        if registry_path is None:
            registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'model_registry.json')
        self.registry_path = registry_path
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
                      scaler_params=None):
        data = self._load_registry()

        model_info = {
            'id': str(uuid.uuid4()),
            'stock_code': stock_code,
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
            'scaler_params': scaler_params
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
        return data.get('models', [])

    def get_models_by_stock(self, stock_code):
        data = self._load_registry()
        return [m for m in data['models'] if m['stock_code'] == stock_code]

    def get_model_by_id(self, model_id):
        data = self._load_registry()
        for model in data['models']:
            if model['id'] == model_id:
                return model
        return None

    def delete_model(self, model_id):
        data = self._load_registry()
        original_count = len(data['models'])
        data['models'] = [m for m in data['models'] if m['id'] != model_id]

        if len(data['models']) < original_count:
            self._save_registry(data)
            return True
        return False

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
            'features': model_info['features'],
            'feature_count': model_info['feature_count']
        }

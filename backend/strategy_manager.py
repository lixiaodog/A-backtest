import os
import json
import uuid
from datetime import datetime

class StrategyManager:
    def __init__(self, metadata_path=None):
        if metadata_path is None:
            metadata_path = os.path.join(
                os.path.dirname(__file__),
                'strategies',
                'strategy_metadata.json'
            )
        self.metadata_path = metadata_path
        self._ensure_metadata()

    def _ensure_metadata(self):
        if not os.path.exists(self.metadata_path):
            os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump({'strategies': [], 'custom_strategies': []}, f, indent=2, ensure_ascii=False)

    def _load_metadata(self):
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_metadata(self, data):
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all_strategies(self):
        data = self._load_metadata()
        return data.get('strategies', []) + data.get('custom_strategies', [])

    def get_strategy_by_id(self, strategy_id):
        strategies = self.get_all_strategies()
        for s in strategies:
            if s['id'] == strategy_id:
                return s
        return None

    def create_strategy(self, strategy_data):
        data = self._load_metadata()

        strategy_id = strategy_data.get('id') or strategy_data.get('name', '').lower().replace(' ', '_')
        strategy_id = f"custom_{strategy_id}_{uuid.uuid4().hex[:8]}"

        new_strategy = {
            'id': strategy_id,
            'name': strategy_data.get('name', '自定义策略'),
            'description': strategy_data.get('description', ''),
            'params': strategy_data.get('params', []),
            'source_code': strategy_data.get('source_code', ''),
            'is_custom': True,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if 'custom_strategies' not in data:
            data['custom_strategies'] = []
        data['custom_strategies'].append(new_strategy)
        self._save_metadata(data)

        return new_strategy

    def update_strategy(self, strategy_id, strategy_data):
        data = self._load_metadata()

        custom_strategies = data.get('custom_strategies', [])
        for i, s in enumerate(custom_strategies):
            if s['id'] == strategy_id:
                custom_strategies[i].update({
                    'name': strategy_data.get('name', s['name']),
                    'description': strategy_data.get('description', s['description']),
                    'params': strategy_data.get('params', s['params']),
                    'source_code': strategy_data.get('source_code', s.get('source_code', '')),
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                data['custom_strategies'] = custom_strategies
                self._save_metadata(data)
                return custom_strategies[i]

        return None

    def delete_strategy(self, strategy_id):
        data = self._load_metadata()

        custom_strategies = data.get('custom_strategies', [])
        original_count = len(custom_strategies)
        data['custom_strategies'] = [s for s in custom_strategies if s['id'] != strategy_id]

        if len(data['custom_strategies']) < original_count:
            self._save_metadata(data)
            return True
        return False

    def get_templates(self):
        templates_dir = os.path.join(os.path.dirname(__file__), 'strategies', 'templates')
        templates = []

        if os.path.exists(templates_dir):
            for filename in os.listdir(templates_dir):
                if filename.endswith('_template.py'):
                    template_path = os.path.join(templates_dir, filename)
                    with open(template_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    template_name = filename.replace('_template.py', '').replace('_', ' ').title()
                    templates.append({
                        'id': filename[:-3],
                        'name': template_name,
                        'filename': filename,
                        'source_code': content
                    })

        return templates

    def get_template(self, template_id):
        templates = self.get_templates()
        for t in templates:
            if t['id'] == template_id:
                return t
        return None

    def export_strategy_code(self, strategy_id):
        strategy = self.get_strategy_by_id(strategy_id)
        if not strategy:
            return None

        if strategy.get('source_code'):
            return strategy['source_code']

        template = self.get_template(f"{strategy_id}_template")
        if template:
            return template['source_code']

        return self._generate_default_code(strategy)

    def _generate_default_code(self, strategy):
        params_str = ',\n        '.join([
            f"('{p['name']}', {p.get('default', 0)})" for p in strategy.get('params', [])
        ])

        code = f'''
import backtrader as bt
from strategies.base_strategy import BaseStrategy

class {strategy['name'].replace(' ', '')}(BaseStrategy):
    params = (
        {params_str}
    )

    name = '{strategy['name']}'
    description = '{strategy['description']}'

    def __init__(self):
        super().__init__()

    def next(self):
        if self.order:
            return
'''
        return code

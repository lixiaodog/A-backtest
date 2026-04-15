import sys
sys.path.insert(0, r'c:\work\backtrader')
from ml.model_registry import ModelRegistry

registry = ModelRegistry()
models = registry.get_all_models()
print(f'Total models: {len(models)}')
for m in models:
    print(f"  - {m['model_name']} (id: {m['id'][:8]}..., is_ensemble: {m.get('is_ensemble', False)})")

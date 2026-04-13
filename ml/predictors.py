import pandas as pd
import numpy as np


class Predictor:
    def __init__(self, model, feature_engineer, label_type='fixed'):
        self.model = model
        self.feature_engineer = feature_engineer
        self.label_type = label_type

    def _get_signal_map(self):
        if self.label_type == 'multi':
            return {0: '强烈卖出', 1: '轻度卖出', 2: '持有', 3: '轻度买入', 4: '强烈买入'}
        return {0: '卖出', 1: '持有', 2: '买入'}

    def predict(self, df: pd.DataFrame, feature_names: list = None):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        last_features = features.iloc[-1:]

        prediction = self.model.predict(last_features)[0]
        probabilities = self.model.predict_proba(last_features)[0]

        signal_map = self._get_signal_map()
        signal = signal_map.get(prediction, '持有')

        confidence = float(max(probabilities))

        prob_dict = {}
        for i, prob in enumerate(probabilities):
            prob_dict[signal_map.get(i, str(i))] = float(prob)

        return {
            'signal': signal,
            'confidence': confidence,
            'probabilities': prob_dict,
            'label_type': self.label_type
        }

    def predict_batch(self, df: pd.DataFrame, feature_names: list = None):
        features = self.feature_engineer.calculate_features(df, feature_names)
        if len(features) == 0:
            return None

        predictions = self.model.predict(features)
        probabilities = self.model.predict_proba(features)

        signal_map = self._get_signal_map()
        signals = [signal_map.get(p, '持有') for p in predictions]

        return {
            'signals': signals,
            'probabilities': probabilities.tolist(),
            'dates': features.index.tolist()
        }

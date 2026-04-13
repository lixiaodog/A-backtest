import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from .alpha191 import Alpha191


class FeatureEngineer:
    def __init__(self):
        self._alpha191 = Alpha191()
        self._alpha191_features = [f'alpha_{i:03d}' for i in range(1, 192)]
        self._technical_features = self._get_technical_features()
        self.available_features = self._technical_features.copy()
        self._scaler = StandardScaler()
        self._scaler_fitted = False

    def _get_technical_features(self):
        return {
            'ma5': self._ma(5),
            'ma10': self._ma(10),
            'ma20': self._ma(20),
            'ma30': self._ma(30),
            'ma60': self._ma(60),
            'ma120': self._ma(120),
            'ma250': self._ma(250),
            'ema12': self._ema(12),
            'ema26': self._ema(26),
            'macd': self._macd,
            'macd_signal': self._macd_signal,
            'macd_diff': self._macd_diff,
            'rsi6': self._rsi(6),
            'rsi12': self._rsi(12),
            'rsi24': self._rsi(24),
            'bollinger_upper': self._bollinger(20, 2, 'upper'),
            'bollinger_middle': self._bollinger(20, 2, 'middle'),
            'bollinger_lower': self._bollinger(20, 2, 'lower'),
            'kdj_k': self._kdj_k,
            'kdj_d': self._kdj_d,
            'kdj_j': self._kdj_j,
            'atr': self._atr(14),
            'volume_ratio': self._volume_ratio,
            'return_1d': self._return(1),
            'return_5d': self._return(5),
            'return_10d': self._return(10),
            'volatility_5d': self._volatility(5),
            'volatility_20d': self._volatility(20),
            'high_low_ratio': self._high_low_ratio,
        }

    def get_available_features(self):
        return list(self.available_features.keys())

    def get_technical_features(self):
        return list(self._technical_features.keys())

    def get_alpha191_features(self):
        return self._alpha191_features

    def get_all_features(self):
        return list(self.available_features.keys())

    def get_scaler_params(self):
        if not self._scaler_fitted:
            return None
        return {
            'mean': self._scaler.mean_.tolist() if hasattr(self._scaler, 'mean_') else None,
            'scale': self._scaler.scale_.tolist() if hasattr(self._scaler, 'scale_') else None,
            'n_features_in_': self._scaler.n_features_in_ if hasattr(self._scaler, 'n_features_in_') else None
        }

    def set_scaler_params(self, params):
        if params is None:
            return
        self._scaler.mean_ = np.array(params['mean'])
        self._scaler.scale_ = np.array(params['scale'])
        self._scaler.n_features_in_ = params['n_features_in_']
        self._scaler_fitted = True

    def _compute_features(self, df: pd.DataFrame, feature_names: list) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        alpha_features = []
        technical_features = []

        for name in feature_names:
            if name in self._alpha191_features:
                alpha_features.append(name)
            elif name in self.available_features:
                technical_features.append(name)

        for name in technical_features:
            result[name] = self.available_features[name](df)

        if alpha_features:
            alpha_df = self._alpha191.get_all_alphas(df)
            for name in alpha_features:
                if name in alpha_df.columns:
                    result[name] = alpha_df[name]

        result = result.replace([np.inf, -np.inf], np.nan)
        result = result.dropna()
        result = result.astype(np.float32)
        result = result.clip(-1e10, 1e10)

        return result

    def fit_transform(self, df: pd.DataFrame, feature_names: list = None) -> pd.DataFrame:
        if feature_names is None:
            feature_names = self.get_available_features()

        result = self._compute_features(df, feature_names)

        scaled_values = self._scaler.fit_transform(result)
        self._scaler_fitted = True
        result = pd.DataFrame(scaled_values, index=result.index, columns=result.columns)

        return result

    def transform(self, df: pd.DataFrame, feature_names: list = None) -> pd.DataFrame:
        if feature_names is None:
            feature_names = self.get_available_features()

        result = self._compute_features(df, feature_names)

        if self._scaler_fitted:
            scaled_values = self._scaler.transform(result)
            result = pd.DataFrame(scaled_values, index=result.index, columns=result.columns)

        return result

    def calculate_features(self, df: pd.DataFrame, feature_names: list = None) -> pd.DataFrame:
        if self._scaler_fitted:
            return self.transform(df, feature_names)
        return self.fit_transform(df, feature_names)

    def generate_labels(self, df: pd.DataFrame, horizon: int = 5, threshold: float = 0.02) -> pd.Series:
        future_returns = df['close'].shift(-horizon) / df['close'] - 1
        labels = pd.cut(future_returns, bins=[-np.inf, -threshold, threshold, np.inf], labels=[0, 1, 2])
        return labels

    def prepare_data(self, df: pd.DataFrame, feature_names: list = None, horizon: int = 5, threshold: float = 0.02):
        features = self.fit_transform(df, feature_names)
        labels = self.generate_labels(df, horizon, threshold)

        aligned_labels = labels.loc[features.index]

        valid_mask = ~aligned_labels.isna()
        X = features.loc[valid_mask]
        y = aligned_labels.loc[valid_mask]

        return X, y

    def _ma(self, period):
        def func(df):
            return df['close'].rolling(window=period).mean()
        return func

    def _ema(self, period):
        def func(df):
            return df['close'].ewm(span=period, adjust=False).mean()
        return func

    @property
    def _macd(self):
        ema12 = self._ema(12)
        ema26 = self._ema(26)
        def func(df):
            return ema12(df) - ema26(df)
        return func

    @property
    def _macd_signal(self):
        ema12 = self._ema(12)
        ema26 = self._ema(26)
        def func(df):
            macd = ema12(df) - ema26(df)
            return macd.ewm(span=9, adjust=False).mean()
        return func

    @property
    def _macd_diff(self):
        ema12 = self._ema(12)
        ema26 = self._ema(26)
        def func(df):
            macd = ema12(df) - ema26(df)
            signal = macd.ewm(span=9, adjust=False).mean()
            return macd - signal
        return func

    def _rsi(self, period):
        def func(df):
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        return func

    def _bollinger_bands(self, period, std_dev):
        middle = self._ma(period)
        std = lambda df: df['close'].rolling(window=period).std()
        def func(df):
            mid = middle(df)
            s = std(df)
            return mid + std_dev * s, mid, mid - std_dev * s
        return func

    def _bollinger(self, period, std_dev, band):
        middle = self._ma(period)
        std = lambda df: df['close'].rolling(window=period).std()
        def func(df):
            mid = middle(df)
            s = std(df)
            if band == 'upper':
                return mid + std_dev * s
            elif band == 'middle':
                return mid
            else:
                return mid - std_dev * s
        return func

    @property
    def _kdj_k(self):
        def func(df):
            low_n = df['low'].rolling(window=9).min()
            high_n = df['high'].rolling(window=9).max()
            rsv = (df['close'] - low_n) / (high_n - low_n) * 100
            return rsv.ewm(com=2, adjust=False).mean()
        return func

    @property
    def _kdj_d(self):
        k = self._kdj_k
        def func(df):
            return k(df).ewm(com=2, adjust=False).mean()
        return func

    @property
    def _kdj_j(self):
        k = self._kdj_k
        d = self._kdj_d
        def func(df):
            return 3 * k(df) - 2 * d(df)
        return func

    def _atr(self, period):
        def func(df):
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(window=period).mean()
        return func

    @property
    def _volume_ratio(self):
        def func(df):
            return df['volume'] / df['volume'].rolling(window=20).mean()
        return func

    def _return(self, period):
        def func(df):
            return df['close'].pct_change(period)
        return func

    def _volatility(self, period):
        def func(df):
            return df['close'].pct_change().rolling(window=period).std()
        return func

    @property
    def _high_low_ratio(self):
        def func(df):
            return (df['high'] - df['low']) / df['close']
        return func
import pandas as pd
import numpy as np


class Alpha191:
    def __init__(self):
        pass

    def _get_vwap(self, df):
        if 'vwap' in df.columns:
            return df['vwap']
        if 'amount' in df.columns and 'volume' in df.columns:
            return df['amount'] / df['volume']
        return (df['high'] + df['low'] + df['close']) / 3

    def _rank(self, s):
        return s.rank(pct=True)

    def _delay(self, s, n=1):
        return s.shift(n)

    def _delta(self, s, n=1):
        return s.diff(n)

    def _sum(self, s, n):
        return s.rolling(window=n).sum()

    def _std(self, s, n):
        return s.rolling(window=n).std()

    def _mean(self, s, n):
        return s.rolling(window=n).mean()

    def _corr(self, a, b, n):
        result = a.rolling(window=n).corr(b)
        return result.replace([np.inf, -np.inf], np.nan)

    def _ts_rank(self, s, n):
        def func(x):
            if len(x) < n:
                return np.nan
            return pd.Series(x).rank(pct=True).iloc[-1]
        return s.rolling(window=n).apply(func, raw=False)

    def _ts_min(self, s, n):
        return s.rolling(window=n).min()

    def _ts_max(self, s, n):
        return s.rolling(window=n).max()

    def _min(self, a, b):
        return np.minimum(a, b)

    def _max(self, a, b):
        return np.maximum(a, b)

    def _abs(self, s):
        return s.abs()

    def _log(self, s):
        return np.log(s)

    def _sign(self, s):
        return np.sign(s)

    def _cov(self, a, b, n):
        result = a.rolling(window=n).cov(b)
        return result.replace([np.inf, -np.inf], np.nan)

    def _prod(self, s, n):
        return s.rolling(window=n).apply(lambda x: np.prod(x), raw=False)

    def _count(self, cond, n):
        return cond.rolling(window=n).sum()

    def _decay_linear(self, s, d):
        weights = np.arange(1, d + 1)
        return s.rolling(window=d).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=False)

    def _scale(self, s, k=1):
        return s * k / self._abs(s).rolling(window=20).mean()

    def _ts_arg_max(self, s, n):
        return s.rolling(window=n).apply(lambda x: np.argmax(x) + 1, raw=False)

    def _ts_arg_min(self, s, n):
        return s.rolling(window=n).apply(lambda x: np.argmin(x) + 1, raw=False)

    def _where(self, cond, val_true, val_false):
        result = np.where(cond, val_true, val_false)
        if isinstance(result, np.ndarray):
            return pd.Series(result, index=cond.index if hasattr(cond, 'index') else None)
        return result

    def alpha_001(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        cond = returns < 0
        std20 = self._std(returns, 20)
        signed_power = self._sign(cond.astype(float) * std20) * (self._abs(cond.astype(float) * std20) ** 2)
        result = self._rank(self._ts_arg_max(signed_power.fillna(close), 5)) - 0.5
        return result

    def alpha_002(self, df):
        volume = df['volume']
        close = df['close']
        open_price = df['open']
        return -1 * self._corr(
            self._rank(self._delta(self._log(volume), 2)),
            self._rank((close - open_price) / open_price), 6)

    def alpha_003(self, df):
        volume = df['volume']
        open_price = df['open']
        return -1 * self._corr(self._rank(open_price), self._rank(volume), 10)

    def alpha_004(self, df):
        low = df['low']
        return -1 * self._ts_rank(self._rank(low), 9)

    def alpha_005(self, df):
        close = df['close']
        open_price = df['open']
        vwap = self._get_vwap(df)
        return self._rank(open_price - self._mean(vwap, 10)) * -1 * self._abs(self._rank(close - vwap))

    def alpha_006(self, df):
        volume = df['volume']
        open_price = df['open']
        return -1 * self._corr(open_price, volume, 10)

    def alpha_007(self, df):
        volume = df['volume']
        close = df['close']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        cond = adv20 < volume
        delta7 = self._delta(close, 7)
        return self._where(cond,
                          -1 * self._ts_rank(self._abs(delta7), 60) * self._sign(delta7),
                          -1)

    def alpha_008(self, df):
        open_price = df['open']
        returns = df['close'].pct_change()
        val = self._sum(open_price, 5) * self._sum(returns, 5)
        return -1 * self._rank(val - self._delay(val, 10))

    def alpha_009(self, df):
        close = df['close']
        delta_close = self._delta(close, 1)
        cond1 = delta_close > 0
        cond2 = delta_close < 0
        return self._where(cond1, delta_close,
                          self._where(cond2, delta_close, -delta_close))

    def alpha_010(self, df):
        close = df['close']
        delta_close = self._delta(close, 1)
        cond1 = delta_close > 0
        cond2 = delta_close < 0
        inner = self._where(cond1, delta_close, self._where(cond2, delta_close, -delta_close))
        return self._rank(inner)

    def alpha_011(self, df):
        close = df['close']
        vwap = self._get_vwap(df)
        volume = df['volume']
        return (self._rank(self._ts_max(vwap - close, 3)) +
                self._rank(self._ts_min(vwap - close, 3))) * self._rank(self._delta(volume, 3))

    def alpha_012(self, df):
        volume = df['volume']
        close = df['close']
        return self._sign(self._delta(volume, 1)) * -1 * self._delta(close, 1)

    def alpha_013(self, df):
        volume = df['volume']
        close = df['close']
        return -1 * self._rank(self._cov(self._rank(close), self._rank(volume), 5))

    def alpha_014(self, df):
        volume = df['volume']
        open_price = df['open']
        returns = df['close'].pct_change()
        return -1 * self._rank(self._delta(returns, 3)) * self._corr(open_price, volume, 10)

    def alpha_015(self, df):
        volume = df['volume']
        high = df['high']
        return -1 * self._sum(self._rank(self._corr(self._rank(high), self._rank(volume), 3)), 3)

    def alpha_016(self, df):
        volume = df['volume']
        high = df['high']
        return -1 * self._rank(self._cov(self._rank(high), self._rank(volume), 5))

    def alpha_017(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        return (-1 * self._rank(self._ts_rank(close, 10)) *
                self._rank(self._delta(self._delta(close, 1), 1)) *
                self._rank(self._ts_rank(volume / adv20, 5)))

    def alpha_018(self, df):
        close = df['close']
        open_price = df['open']
        return (-1 * (self._rank(self._std(self._abs(close - open_price), 5)) +
                      self._rank(close - open_price) +
                      self._rank(self._corr(close, open_price, 10))))

    def alpha_019(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        val = self._sum(returns, 250)
        return (-1 * self._sign(close - self._delay(close, 7) + self._delta(close, 7)) *
                (1 + self._rank(1 + val)))

    def alpha_020(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        open_price = df['open']
        return (-1 * self._rank(open_price - self._delay(high, 1)) *
                self._rank(open_price - self._delay(close, 1)) *
                self._rank(open_price - self._delay(low, 1)))

    def alpha_021(self, df):
        close = df['close']
        volume = df['volume']
        adv20 = self._mean(volume, 20)
        cond1 = (self._mean(close, 8) + self._std(close, 8)) < self._mean(close, 2)
        cond2 = self._mean(close, 2) < (self._mean(close, 8) - self._std(close, 8))
        cond3 = volume / adv20 <= 1
        return self._where(cond1, -1,
                          self._where(cond2, 1, self._where(cond3, 1, -1)))

    def alpha_022(self, df):
        close = df['close']
        high = df['high']
        volume = df['volume']
        return -1 * self._delta(self._corr(high, volume, 5), 5) * self._rank(self._std(close, 20))

    def alpha_023(self, df):
        close = df['close']
        high = df['high']
        cond = self._mean(high, 20) < high
        return self._where(cond, -1 * self._delta(high, 2), 0)

    def alpha_024(self, df):
        close = df['close']
        mean100 = self._mean(close, 100)
        delta100 = self._delta(mean100, 100)
        delay100 = self._delay(close, 100)
        cond = ((delta100 / delay100) < 0.05) | ((delta100 / delay100) == 0.05)
        return self._where(cond, -1 * (close - self._ts_min(close, 100)), -1 * self._delta(close, 3))

    def alpha_025(self, df):
        close = df['close']
        volume = df['volume']
        vwap = self._get_vwap(df)
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        return (self._rank(-1 * returns) * self._rank(adv20) * self._rank(vwap) * self._rank(close - vwap))

    def alpha_026(self, df):
        close = df['close']
        high = df['high']
        volume = df['volume']
        return -1 * self._ts_max(self._corr(self._ts_rank(volume, 5), self._ts_rank(high, 5), 5), 3)

    def alpha_027(self, df):
        volume = df['volume']
        vwap = self._get_vwap(df)
        val = self._rank(self._mean(self._corr(self._rank(volume), self._rank(vwap), 6), 2))
        return self._where(val > 0.5, -1, 1)

    def alpha_028(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        adv20 = self._mean(volume, 20)
        return self._scale(self._corr(adv20, low, 5) + (high + low) / 2 - close)

    def alpha_029(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        r1 = self._rank(self._delta(close - 1, 5))
        r2 = self._rank(-1 * r1)
        r3 = self._rank(r2)
        r4 = self._rank(self._scale(self._log(self._sum(r3, 2))))
        r5 = self._prod(r4, 1)
        r6 = self._ts_rank(self._delay(-1 * returns, 6), 5)
        return self._min(r5, 5) + r6

    def alpha_030(self, df):
        close = df['close']
        volume = df['volume']
        s1 = self._sign(self._delta(close, 1))
        s2 = self._sign(self._delay(close, 1) - self._delay(close, 2))
        s3 = self._sign(self._delay(close, 2) - self._delay(close, 3))
        numerator = (1 - self._rank(s1 + s2 + s3)) * self._sum(volume, 5)
        return numerator / self._sum(volume, 20)

    def alpha_031(self, df):
        close = df['close']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        r1 = self._rank(self._decay_linear(-1 * self._rank(self._rank(self._delta(close, 10))), 10))
        r2 = self._rank(-1 * self._delta(close, 3))
        r3 = self._sign(self._scale(self._corr(adv20, low, 12)))
        return self._rank(r1) + self._rank(r2) + r3

    def alpha_032(self, df):
        close = df['close']
        vwap = self._get_vwap(df)
        return self._scale(self._mean(close, 7) - close) + 20 * self._scale(self._corr(vwap, self._delay(close, 5), 230))

    def alpha_033(self, df):
        close = df['close']
        open_price = df['open']
        return self._rank(-1 * (1 - open_price / close))

    def alpha_034(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        r1 = 1 - self._rank(self._std(returns, 2) / self._std(returns, 5))
        r2 = 1 - self._rank(self._delta(close, 1))
        return self._rank(r1) + self._rank(r2)

    def alpha_035(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        return (self._ts_rank(volume, 32) *
                (1 - self._ts_rank(close + high - low, 16)) *
                (1 - self._ts_rank(returns, 32)))

    def alpha_036(self, df):
        close = df['close']
        open_price = df['open']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(volume, 20)
        r1 = 2.21 * self._rank(self._corr(close - open_price, self._delay(volume, 1), 15))
        r2 = 0.7 * self._rank(open_price - close)
        r3 = 0.73 * self._rank(self._ts_rank(self._delay(-1 * returns, 6), 5))
        r4 = self._rank(self._abs(self._corr(vwap, adv20, 6)))
        r5 = 0.6 * self._rank(((self._mean(close, 200) / 200 - open_price) * (close - open_price)))
        return r1 + r2 + r3 + r4 + r5

    def alpha_037(self, df):
        close = df['close']
        open_price = df['open']
        r1 = self._rank(self._corr(self._delay(open_price - close, 1), close, 200))
        r2 = self._rank(open_price - close)
        return self._rank(r1 + r2)

    def alpha_038(self, df):
        close = df['close']
        open_price = df['open']
        return -1 * self._rank(self._ts_rank(close, 10)) * self._rank(close / open_price)

    def alpha_039(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        r1 = -1 * self._rank(self._delta(close, 7)) * (1 - self._rank(self._decay_linear(volume / adv20, 9)))
        r2 = 1 + self._rank(self._sum(returns, 250))
        return r1 * r2

    def alpha_040(self, df):
        high = df['high']
        volume = df['volume']
        return -1 * self._rank(self._std(high, 10)) * self._corr(high, volume, 10)

    def alpha_041(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        vwap = self._get_vwap(df)
        return self._rank((vwap - close) ** 0.5) - vwap

    def alpha_042(self, df):
        close = df['close']
        vwap = self._get_vwap(df)
        return self._rank(vwap - close) / self._rank(vwap + close)

    def alpha_043(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        return self._ts_rank(volume / adv20, 20) * self._ts_rank(-1 * self._delta(close, 7), 8)

    def alpha_044(self, df):
        high = df['high']
        volume = df['volume']
        return -1 * self._corr(high, self._rank(volume), 5)

    def alpha_045(self, df):
        close = df['close']
        volume = df['volume']
        r1 = self._rank(self._mean(self._delay(close, 5), 20))
        r2 = self._corr(close, volume, 2)
        r3 = self._rank(self._corr(self._sum(close, 5), self._sum(close, 20), 2))
        return -1 * r1 * r2 * r3

    def alpha_046(self, df):
        close = df['close']
        cond = 0.25 < (((self._delay(close, 20) - self._delay(close, 10)) / 10) -
                      ((self._delay(close, 10) - close) / 10))
        return self._where(cond, -1 * (close - self._ts_min(close, 20)), -1 * self._delta(close, 3))

    def alpha_047(self, df):
        close = df['close']
        volume = df['volume']
        vwap = self._get_vwap(df)
        r1 = self._rank(self._max(self._abs(self._corr(self._rank(vwap), self._rank(volume), 5)), 5))
        r2 = self._sign(self._corr(self._rank(vwap), self._rank(volume), 5))
        return r1 * r2

    def alpha_048(self, df):
        close = df['close']
        cond = (self._delay(close, 1) / self._mean(close, 100)) - 1
        return self._where(cond > 0.25, -1 * self._delta(close, 2), -1 * self._ts_min(close, 20))

    def alpha_049(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        open_price = df['open']
        dtm = self._where(open_price <= self._delay(open_price, 1), 0,
                         self._max(high - open_price, open_price - self._delay(open_price, 1)))
        dbm = self._where(open_price >= self._delay(open_price, 1), 0,
                         self._max(open_price - low, open_price - self._delay(open_price, 1)))
        tr = self._max(high - low, self._max(self._abs(high - self._delay(close, 1)),
                                              self._abs(low - self._delay(close, 1))))
        return self._rank(self._sign(dtm) - self._sign(dbm)) * -1 * self._delta(close, 3)

    def alpha_050(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        high = df['high']
        low = df['low']
        val1 = (high - close) / (close - low)
        r1 = self._ts_max(self._rank(val1), 5)
        r2 = self._rank(self._rank(returns / vwap))
        return -1 * r1 * r2

    def alpha_051(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        val = self._sum(returns, 12) - self._sum(returns, 24)
        return -1 * self._ts_max(self._corr(self._rank(val), self._rank(self._sum(returns, 12)), 18), 3)

    def alpha_052(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        val = self._sum(returns, 12) - self._sum(returns, 24)
        return -1 * self._ts_max(self._rank(self._corr(self._rank(val), self._rank(self._sum(returns, 12)), 18)), 3)

    def alpha_053(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        return -1 * self._rank(self._delta(close, 3)) * self._corr(self._rank(close), self._rank(returns), 10)

    def alpha_054(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        adv20 = self._mean(volume, 20)
        cond = self._delta(self._corr(close, adv20, 5), 5) < 0
        return self._where(cond, -1 * (close - self._ts_min(close, 16)), -1 * self._delta(close, 3))

    def alpha_055(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        vwap = self._get_vwap(df)
        r1 = self._decay_linear(self._max(vwap - close, 3), 16)
        r2 = self._rank(r1)
        return -1 * self._max(r2, 4)

    def alpha_056(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        val = self._scale(self._sum(returns, 10) - self._sum(returns, 30)) - self._mean(close, 20)
        return -1 * self._rank(val)

    def alpha_057(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(vwap - self._ts_min(vwap, 16))
        r2 = self._sign(self._rank(self._sum(returns, 10)))
        r3 = self._rank(vwap) / self._rank(close)
        return -1 * r1 * r2 * r3

    def alpha_058(self, df):
        close = df['close']
        open_price = df['open']
        returns = df['close'].pct_change()
        return -1 * self._rank(self._delta(returns, 3)) * self._corr(self._rank(open_price), self._rank(close), 10)

    def alpha_059(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        vwap = self._get_vwap(df)
        delta_close = self._delta(close, 1)
        r1 = self._ts_min(delta_close, 4)
        r2 = self._rank(delta_close) / self._rank(self._ts_max(delta_close, 4))
        r3 = self._rank(self._delta(vwap, 1))
        return self._rank(r1) * r2 * r3

    def alpha_060(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._ts_min(self._delta(close, 2), 3))
        r2 = self._rank(self._sum(returns, 10))
        return -1 * self._corr(r1, r2, 6)

    def alpha_061(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(vwap, 2)) * self._corr(vwap, self._rank(volume), 6)

    def alpha_062(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        r1 = self._rank(self._delta(close, 10))
        r2 = self._rank(self._delta(returns, 10))
        return -1 * r1 * r2

    def alpha_063(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(close, 3)) * self._corr(self._rank(close), self._rank(vwap), 10)

    def alpha_064(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(df['volume'], 20)
        corr_val = self._rank(self._corr(self._rank(close), self._rank(vwap), 5))
        ts_min_val = self._ts_min(corr_val, 9)
        return -1 * self._max(ts_min_val, self._rank(-1 * self._delta(close, 3)))

    def alpha_065(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._delta(vwap, 4), 8))
        r2 = self._rank(self._decay_linear(self._delta(returns * 100, 6), 2))
        return -1 * (r1 - r2)

    def alpha_066(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._delta(vwap, 2), 8))
        r2 = self._rank(self._decay_linear(self._delta(returns * 100, 6), 2))
        return -1 * self._corr(r1, r2, 8)

    def alpha_067(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._delta(vwap, 1), 12))
        r2 = self._rank(self._decay_linear(self._delta(returns * 100, 3), 10))
        alpha = r1 - r2
        return -1 * self._max(self._abs(alpha), 5)

    def alpha_068(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._delta(vwap, 1), 12))
        r2 = self._rank(self._decay_linear(self._delta(returns * 100, 3), 10))
        alpha = r1 - r2
        return self._where(self._abs(alpha) < 0.5, -1 * returns, self._rank(-1 * alpha))

    def alpha_069(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        corr_val = self._ts_min(self._rank(self._corr(self._rank(close), self._rank(vwap), 5)), 4)
        cond = (corr_val < 5) & (corr_val > -1)
        return self._where(cond, -1 * self._delta(close, 2), -1 * self._delta(close, 1))

    def alpha_070(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        corr_val = self._ts_min(self._rank(self._corr(self._rank(close), self._rank(vwap), 5)), 4)
        cond = corr_val < 5
        return self._where(cond, -1 * self._delta(close, 2), -1 * self._delta(close, 1))

    def alpha_071(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(volume, 20)
        r1 = self._corr(vwap, self._sum(self._mean(volume, 5), 26), 7)
        return -1 * self._rank(self._decay_linear(r1, 7))

    def alpha_072(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._sum(self._delay(close, 1), 26) / close)
        r2 = self._rank(self._corr(vwap, self._sum(volume, 8), 7))
        r3 = self._rank(self._delta(returns, 3))
        return -1 * r1 * r2 * r3

    def alpha_073(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._corr(self._rank(self._delay(close, 1)), self._rank(returns), 15)
        r2 = self._corr(self._rank(close), self._rank(vwap), 6)
        return -1 * r1 * r2

    def alpha_074(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(close), self._rank(vwap), 6))
        r2 = self._rank(self._ts_rank(self._delay(close, 1), 7))
        return -1 * (r1 - r2)

    def alpha_075(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(close), self._rank(vwap), 6))
        r2 = self._rank(self._corr(self._rank(self._ts_rank(self._delay(close, 1), 7)), self._rank(self._ts_rank(returns, 9)), 6))
        return -1 * r1 * r2

    def alpha_076(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(close), self._rank(vwap), 6))
        r2 = self._rank(self._corr(self._rank(self._ts_min(close, 2)), self._rank(returns), 9))
        return -1 * r1 * r2

    def alpha_077(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._delay(close, 1)), self._rank(close), 12))
        return -1 * r1 * r2

    def alpha_078(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._delay(close, 1)), self._rank(close), 12))
        return -1 * r1 * r2

    def alpha_079(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(close, self._sum(self._mean(close, 30), 37), 15))
        r2 = self._rank(close - vwap)
        r3 = self._rank(self._delta(returns, 3))
        return -1 * (r1 + r2 + r3)

    def alpha_080(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(volume, 20)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 5))
        r2 = self._rank(self._delta(close / self._mean(close, 20), 2))
        return -1 * r1 * r2

    def alpha_081(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._ts_max(self._corr(self._rank(vwap), self._rank(df['volume']), 3), 15))
        r2 = self._rank(self._delta(close / self._mean(close, 20), 2))
        return -1 * r1 * r2

    def alpha_082(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._delay(close, 1)), self._rank(close), 12))
        return -1 * r1 * r2

    def alpha_083(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(df['volume']), 6))
        r2 = self._rank(self._ts_rank(self._delay(close, 1), 7))
        return -1 * (r1 - r2)

    def alpha_084(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._delay(close, 1)), self._rank(close), 12))
        return -1 * r1 * r2

    def alpha_085(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._ts_min(close, 2)), self._rank(returns), 9))
        return -1 * r1 * r2

    def alpha_086(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        r2 = self._rank(self._corr(self._rank(self._ts_min(close, 2)), self._rank(returns), 9))
        return -1 * r1 * r2

    def alpha_087(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        cond = r1 < 0.4
        return self._where(cond, -1 * self._mean(close, 3), -1 * self._delta(close, 3))

    def alpha_088(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        cond = r1 < 0.4
        return self._where(cond, -1 * self._mean(close, 3), -1 * self._delta(close, 3))

    def alpha_089(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._corr(self._rank(vwap), self._rank(volume), 6))
        cond = r1 < 0.5
        return self._where(cond, -1 * self._delta(close, 3), -1 * self._mean(close, 3))

    def alpha_090(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._delta(vwap, 1))
        r2 = self._rank(self._corr(self._rank(close), self._rank(vwap), 5))
        return -1 * r1 * r2

    def alpha_091(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._delta(vwap, 1))
        r2 = self._rank(self._corr(self._rank(close), self._rank(vwap), 10))
        return -1 * r1 * r2

    def alpha_092(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._delta(vwap, 1))
        r2 = self._rank(self._corr(self._rank(close), self._rank(vwap), 20))
        return -1 * r1 * r2

    def alpha_093(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._delta(vwap, 1))
        r2 = self._rank(self._corr(self._rank(close), self._rank(vwap), 15))
        return -1 * r1 * r2

    def alpha_094(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(volume, 20)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 3))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 4), 3))
        return -1 * r1 * r2

    def alpha_095(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 5))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 4), 5))
        return -1 * r1 * r2

    def alpha_096(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 4))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 6), 4))
        return -1 * r1 * r2

    def alpha_097(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 6))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 5), 5))
        return -1 * r1 * r2

    def alpha_098(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 8))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 6), 6))
        return -1 * r1 * r2

    def alpha_099(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 9))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 7), 7))
        return -1 * r1 * r2

    def alpha_100(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        r1 = self._rank(self._decay_linear(self._corr(self._rank(close), self._rank(vwap), 7), 10))
        r2 = self._rank(self._decay_linear(self._delta(close * volume, 8), 8))
        return -1 * r1 * r2

    def alpha_101(self, df):
        close = df['close']
        open_price = df['open']
        vwap = self._get_vwap(df)
        return self._rank(self._delta(vwap, 5)) - self._rank(vwap - open_price)

    def alpha_102(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._corr(self._rank(self._delta(vwap, 5)), self._rank(close - vwap), 5)

    def alpha_103(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(close, 10)) * self._rank(close - vwap)

    def alpha_104(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(close, 10)) * self._rank(close / vwap)

    def alpha_105(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(close, 10)) * self._rank(close - vwap)

    def alpha_106(self, df):
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(vwap, 5)) * self._rank(close - vwap)

    def alpha_107(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(vwap, 5)) * self._rank(vwap - close)

    def alpha_108(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(vwap, 5)) * self._rank(vwap / close)

    def alpha_109(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(self._delta(vwap, 5)) * self._rank(close - vwap)

    def alpha_110(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(close / vwap)

    def alpha_111(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(close, 5))

    def alpha_112(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(vwap, 5))

    def alpha_113(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(returns)

    def alpha_114(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(vwap / close)

    def alpha_115(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        adv20 = self._mean(volume, 20)
        return -1 * self._rank(close - vwap) * self._rank(volume / adv20)

    def alpha_116(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(volume, 5))

    def alpha_117(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(close, 5))

    def alpha_118(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(close / vwap)

    def alpha_119(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(returns, 10))

    def alpha_120(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(volume, 5))

    def alpha_121(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(returns, 20))

    def alpha_122(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(close, volume, 5))

    def alpha_123(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(close, volume, 10))

    def alpha_124(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, volume, 5))

    def alpha_125(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, volume, 10))

    def alpha_126(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(close, 10))

    def alpha_127(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(volume, 10))

    def alpha_128(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(returns, 10))

    def alpha_129(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(vwap / close, 10))

    def alpha_130(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(returns, 10))

    def alpha_131(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(volume, 10))

    def alpha_132(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, self._sum(volume, 5), 5))

    def alpha_133(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, self._sum(volume, 10), 10))

    def alpha_134(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 5), self._sum(volume, 10), 10))

    def alpha_135(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 5), self._sum(close, 20), 10))

    def alpha_136(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(close, 10))

    def alpha_137(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(vwap, 10))

    def alpha_138(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(volume, 10))

    def alpha_139(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(returns, 10))

    def alpha_140(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(vwap / close, 10))

    def alpha_141(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(close, 5))

    def alpha_142(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(close, 10))

    def alpha_143(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(close, 20))

    def alpha_144(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(volume, 5))

    def alpha_145(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(volume, 10))

    def alpha_146(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._sum(volume, 20))

    def alpha_147(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(close, 5))

    def alpha_148(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(close, 10))

    def alpha_149(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(close, 20))

    def alpha_150(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(volume, 5))

    def alpha_151(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(volume, 10))

    def alpha_152(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._mean(volume, 20))

    def alpha_153(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_min(close, 5))

    def alpha_154(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_min(close, 10))

    def alpha_155(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_min(close, 20))

    def alpha_156(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_max(close, 5))

    def alpha_157(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_max(close, 10))

    def alpha_158(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_max(close, 20))

    def alpha_159(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(close, volume, 5))

    def alpha_160(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(close, volume, 10))

    def alpha_161(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(close, volume, 20))

    def alpha_162(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, volume, 5))

    def alpha_163(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, volume, 10))

    def alpha_164(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, volume, 20))

    def alpha_165(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(close, 5))

    def alpha_166(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(close, 10))

    def alpha_167(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(close, 20))

    def alpha_168(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(volume, 5))

    def alpha_169(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(volume, 10))

    def alpha_170(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(volume, 20))

    def alpha_171(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(returns, 5))

    def alpha_172(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(returns, 10))

    def alpha_173(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(returns, 20))

    def alpha_174(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(vwap / close, 5))

    def alpha_175(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(vwap / close, 10))

    def alpha_176(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._ts_rank(vwap / close, 20))

    def alpha_177(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(returns, 5))

    def alpha_178(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(returns, 10))

    def alpha_179(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(returns, 20))

    def alpha_180(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(volume, 5))

    def alpha_181(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(volume, 10))

    def alpha_182(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._std(volume, 20))

    def alpha_183(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, self._sum(volume, 5), 5))

    def alpha_184(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, self._sum(volume, 10), 10))

    def alpha_185(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(vwap, self._sum(volume, 20), 20))

    def alpha_186(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 5), self._sum(volume, 5), 5))

    def alpha_187(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 5), self._sum(volume, 10), 10))

    def alpha_188(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 10), self._sum(volume, 10), 10))

    def alpha_189(self, df):
        close = df['close']
        volume = df['volume']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._corr(self._sum(close, 20), self._sum(volume, 20), 20))

    def alpha_190(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(close, 5))

    def alpha_191(self, df):
        close = df['close']
        returns = df['close'].pct_change()
        vwap = self._get_vwap(df)
        return -1 * self._rank(close - vwap) * self._rank(self._delta(close, 10))

    def get_all_alphas(self, df):
        result = pd.DataFrame(index=df.index)
        for i in range(1, 192):
            try:
                alpha_method = getattr(self, f'alpha_{i:03d}', None)
                if alpha_method:
                    result[f'alpha_{i:03d}'] = alpha_method(df)
            except Exception:
                pass
        return result
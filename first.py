import pandas as pd
from datetime import datetime
import backtrader as bt
import matplotlib.pyplot as plt
from pytdx.hq import TdxHq_API
api = TdxHq_API()
if api.connect('119.147.212.81', 7701):
    data = api.get_security_bars(9, 0, '000001', 0, 10) #返回普通list
    print(data)
    data = api.to_df(api.get_security_bars(9, 0, '000001', 0, 10)) # 返回DataFrame
    print(data)
    api.disconnect()
else:
    print("can't connet")
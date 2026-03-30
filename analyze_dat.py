import struct
import datetime

file_path = r'C:\国信iQuant策略交易平台\datadir\SZ\60\000001.dat'

with open(file_path, 'rb') as f:
    data = f.read()

num_records = (len(data) - 68) // 64

print('=' * 90)
print('修正后的行情数据 (价格单位: 厘 -> 除以1000得元)')
print('=' * 90)
print('{:<4} {:<20} {:<8} {:<8} {:<8} {:<8} {:<12}'.format('序号', '时间', '开盘', '最高', '最低', '收盘', '成交量'))
print('-' * 90)

for idx in range(20):
    rec_start = 68 + idx * 64
    record = data[rec_start:rec_start+64]
    ts = struct.unpack('<I', record[4:8])[0]
    dt = datetime.datetime.fromtimestamp(ts)
    open_p = struct.unpack('<I', record[8:12])[0] / 1000
    high_p = struct.unpack('<I', record[12:16])[0] / 1000
    low_p = struct.unpack('<I', record[16:20])[0] / 1000
    close_p = struct.unpack('<I', record[20:24])[0] / 1000
    vol = struct.unpack('<I', record[28:32])[0]
    print('{:<4} {:<20} {:<8.3f} {:<8.3f} {:<8.3f} {:<8.3f} {:<12}'.format(idx, str(dt), open_p, high_p, low_p, close_p, vol))

print('=' * 90)

import struct
import datetime

file_path = r'C:\国信iQuant策略交易平台\datadir\SZ\0\000007\20260327.dat'
with open(file_path, 'rb') as f:
    data = f.read()

print('=' * 80)
print('TICK数据文件分析报告')
print('=' * 80)
print()
print('【文件信息】')
print(f'  股票: 000007')
print(f'  日期: 2026-03-27')
print(f'  Tick间隔: 3秒')
print(f'  记录数: {len(data)//144}')
print(f'  记录长度: 144字节')
print()

print('【记录结构 144字节】')
print()
print('--- 基础字段 (0-59) ---')
print('偏移  0- 7: 时间戳 (uint64, 毫秒Unix时间)')
print('偏移  8-11: 当天秒数 (uint32)')
print('偏移 12-15: 未知')
print('偏移 16-19: 成交量 (uint32)')
print('偏移 20-23: 成交额 (uint32)')
print('偏移 24-27: 未知')
print('偏移 28-31: 状态 (uint32) - 11=开盘前, 12=交易中, 13=有成交')
print('偏移 32-35: 未知')
print('偏移 36-39: 昨收价 (uint32, 单位: 厘)')
print('偏移 40-43: 开盘价 (uint32, 单位: 厘)')
print('偏移 44-47: 最高价 (uint32, 单位: 厘)')
print('偏移 48-51: 最新价 (uint32, 单位: 厘)')
print('偏移 52-55: 最低价 (uint32, 单位: 厘)')
print('偏移 56-59: 标记 (0x1234)')
print()
print('--- 10档卖盘 (60-139) ---')
print('每档8字节: [价格4字节][委托量4字节]')
print('卖1-卖10，价格从高到低')
print()
print('--- 买盘数据 (140-143) ---')
print('只有4字节，可能存储在下一条记录或格式不同')
print()
print('价格单位: 厘 (除1000 = 元)')
print()

# 显示样本数据
print('【Tick数据样本】')
print('-' * 100)
print('{:<5} {:<20} {:<5} {:<12} {:<10} {:<8} {:<8} {:<8}'.format(
    '序号', '时间', '状态', '成交量', '最新价', '最高', '最低', '卖1'))
print('-' * 100)

count = 0
for idx in range(len(data)//144):
    rec_start = idx * 144
    record = data[rec_start:rec_start+144]
    vol = struct.unpack('<I', record[16:20])[0]
    if vol > 0:
        ts = struct.unpack('<Q', record[0:8])[0]
        dt = datetime.datetime.fromtimestamp(ts / 1000)
        status = struct.unpack('<I', record[28:32])[0]
        price = struct.unpack('<I', record[48:52])[0]
        high = struct.unpack('<I', record[44:48])[0]
        low = struct.unpack('<I', record[52:56])[0]
        ask1 = struct.unpack('<I', record[60:64])[0]

        print('{:<5} {:<20} {:<5} {:<12} {:<10.3f} {:<8.3f} {:<8.3f} {:<8.3f}'.format(
            idx, str(dt), status, vol, price/1000, high/1000, low/1000, ask1/1000))
        count += 1
        if count >= 20:
            break

print('-' * 100)
print()
print('分析完成!')

import sys
import os
import pandas as pd
import numpy as np

PROJECT_DIR = r'c:\work\backtrader'
sys.path.insert(0, PROJECT_DIR)

from ml.alpha191 import Alpha191

def load_sample_data():
    data_path = os.path.join(PROJECT_DIR, 'data', 'SZ', '1d', '000001.csv')
    if os.path.exists(data_path):
        df = pd.read_csv(data_path, index_col='stime', parse_dates=True)
        df = df.head(300)
        df.sort_index(inplace=True)
        return df
    return None

def test_all_alphas():
    df = load_sample_data()
    if df is None:
        print("[错误] 无法加载示例数据")
        return

    print(f"[测试] 加载了 {len(df)} 条数据")
    print("[测试] 开始检测所有 Alpha191 因子...\n")

    alpha = Alpha191()
    errors = []
    warnings = []
    success_count = 0
    fail_count = 0

    for i in range(1, 192):
        alpha_name = f'alpha_{i:03d}'
        try:
            alpha_method = getattr(alpha, alpha_name)
            result = alpha_method(df)

            if result is None:
                errors.append(f"{alpha_name}: 返回 None")
                fail_count += 1
            elif len(result) == 0:
                errors.append(f"{alpha_name}: 返回空序列")
                fail_count += 1
            elif result.isna().all():
                errors.append(f"{alpha_name}: 所有值都是 NaN")
                fail_count += 1
            elif np.isinf(result).any():
                warnings.append(f"{alpha_name}: 包含无穷值")
                success_count += 1
            else:
                valid_count = result.notna().sum()
                print(f"[OK] {alpha_name}: 有效值 {valid_count}/{len(result)}")
                success_count += 1

        except SyntaxError as e:
            errors.append(f"{alpha_name}: 语法错误 - {str(e)}")
            fail_count += 1
        except Exception as e:
            errors.append(f"{alpha_name}: {type(e).__name__} - {str(e)}")
            fail_count += 1

    print("\n" + "="*60)
    print(f"[汇总] 成功: {success_count}, 失败: {fail_count}, 警告: {len(warnings)}")
    print("="*60)

    if errors:
        print(f"\n[错误] 发现 {len(errors)} 个错误:")
        for err in errors:
            print(f"  - {err}")

    if warnings:
        print(f"\n[警告] 发现 {len(warnings)} 个警告:")
        for warn in warnings:
            print(f"  - {warn}")

    return errors, warnings

def test_alpha_syntax():
    print("[语法检测] 检查 Alpha191 源代码语法...\n")
    alpha_source = os.path.join(PROJECT_DIR, 'ml', 'alpha191.py')

    with open(alpha_source, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        compile(source, alpha_source, 'exec')
        print("[OK] 语法检测通过")
        return True
    except SyntaxError as e:
        print(f"[语法错误] 第 {e.lineno} 行: {e.msg}")
        lines = source.split('\n')
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        for i in range(start, end):
            marker = ">>> " if i == e.lineno - 1 else "    "
            print(f"{marker}{i+1}: {lines[i]}")
        return False

def find_double_parentheses():
    print("\n[检测] 查找双右括号 '))' 问题...")
    alpha_source = os.path.join(PROJECT_DIR, 'ml', 'alpha191.py')

    with open(alpha_source, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    issues = []
    for i, line in enumerate(lines, 1):
        if '))' in line and not 'np.inf' in line:
            issues.append((i, line.strip()))

    if issues:
        print(f"[问题] 发现 {len(issues)} 处可疑的双右括号:")
        for lineno, content in issues[:20]:
            print(f"  第{lineno}行: {content}")
        if len(issues) > 20:
            print(f"  ... 还有 {len(issues) - 20} 处")
    else:
        print("[OK] 未发现双右括号问题")

    return issues

if __name__ == '__main__':
    print("="*60)
    print("Alpha191 因子检测脚本")
    print("="*60)

    test_alpha_syntax()
    find_double_parentheses()

    print("\n" + "="*60)
    print("开始运行时测试...")
    print("="*60 + "\n")

    errors, warnings = test_all_alphas()

    if not errors:
        print("\n[结论] 所有 Alpha191 因子检测通过!")
    else:
        print(f"\n[结论] 发现 {len(errors)} 个错误需要修复")
        sys.exit(1)

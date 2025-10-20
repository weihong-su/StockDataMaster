"""
验证lib目录下的内置库安装情况

检查:
1. 必需库: mootdx, baostock, tushare
2. 可选库: xtquant
3. 版本信息
4. 完整性检查
"""

import os
import sys

def verify_library(lib_name, lib_dir):
    """验证单个库的安装"""

    lib_path = os.path.join(lib_dir, lib_name)

    result = {
        'name': lib_name,
        'installed': False,
        'path': lib_path,
        'has_init': False,
        'version': None,
        'importable': False
    }

    # 检查目录是否存在
    if not os.path.exists(lib_path) or not os.path.isdir(lib_path):
        return result

    result['installed'] = True

    # 检查__init__.py
    init_file = os.path.join(lib_path, '__init__.py')
    if os.path.exists(init_file):
        result['has_init'] = True

    # 尝试读取版本
    try:
        # 检查dist-info目录
        dist_info_dirs = [d for d in os.listdir(lib_dir)
                          if d.startswith(f'{lib_name}-') and d.endswith('.dist-info')]

        if dist_info_dirs:
            # 从目录名提取版本
            version_str = dist_info_dirs[0].replace(f'{lib_name}-', '').replace('.dist-info', '')
            result['version'] = version_str

    except Exception:
        pass

    # 尝试导入
    try:
        # 临时添加lib到路径
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)

        module = __import__(lib_name)

        result['importable'] = True

        # 尝试获取版本
        if hasattr(module, '__version__'):
            result['version'] = module.__version__

        # 移除路径
        if lib_dir in sys.path:
            sys.path.remove(lib_dir)

    except Exception as e:
        result['import_error'] = str(e)

    return result


def main():
    """主验证流程"""

    # 获取lib目录
    lib_dir = os.path.dirname(os.path.abspath(__file__))

    print("="*70)
    print("StockDataMaster - 内置库验证工具")
    print("="*70)
    print(f"lib目录: {lib_dir}\n")

    # 必需库
    required_libs = ['mootdx', 'baostock', 'tushare']

    # 可选库
    optional_libs = ['xtquant']

    print("="*70)
    print("必需库检查")
    print("="*70 + "\n")

    required_results = []
    for lib_name in required_libs:
        result = verify_library(lib_name, lib_dir)
        required_results.append(result)

        # 打印结果
        if result['installed']:
            if result['has_init'] and result['importable']:
                status = "✓"
                status_text = "正常"
            elif result['has_init']:
                status = "⚠"
                status_text = "可能有问题(无法导入)"
            else:
                status = "⚠"
                status_text = "缺少__init__.py"
        else:
            status = "✗"
            status_text = "未安装"

        version_text = f"v{result['version']}" if result['version'] else "版本未知"

        print(f"{status} {lib_name:15} {status_text:20} {version_text}")

        if not result['importable'] and result.get('import_error'):
            print(f"  导入错误: {result['import_error']}")

    print("\n" + "="*70)
    print("可选库检查")
    print("="*70 + "\n")

    optional_results = []
    for lib_name in optional_libs:
        result = verify_library(lib_name, lib_dir)
        optional_results.append(result)

        if result['installed']:
            if result['has_init'] and result['importable']:
                status = "✓"
                status_text = "已安装"
            elif result['has_init']:
                status = "⚠"
                status_text = "已安装(可能有问题)"
            else:
                status = "⚠"
                status_text = "已安装(缺少__init__.py)"
        else:
            status = "-"
            status_text = "未安装(可选)"

        version_text = f"v{result['version']}" if result['version'] else ""

        print(f"{status} {lib_name:15} {status_text:20} {version_text}")

    # 总结
    print("\n" + "="*70)
    print("验证总结")
    print("="*70 + "\n")

    required_ok = all(r['installed'] and r['has_init'] and r['importable']
                      for r in required_results)

    if required_ok:
        print("✓ 所有必需库已正确安装!")
    else:
        print("✗ 部分必需库存在问题,请检查:")
        for result in required_results:
            if not (result['installed'] and result['has_init'] and result['importable']):
                print(f"  - {result['name']}")

    optional_ok_count = sum(1 for r in optional_results
                            if r['installed'] and r['has_init'] and r['importable'])

    if optional_ok_count > 0:
        print(f"✓ {optional_ok_count}个可选库已安装")
    else:
        print("- 未安装可选库(不影响核心功能)")

    # 版本信息汇总
    print("\n" + "="*70)
    print("版本信息汇总")
    print("="*70 + "\n")

    all_results = required_results + optional_results

    for result in all_results:
        if result['installed'] and result['version']:
            print(f"{result['name']:15} {result['version']}")

    print("\n" + "="*70)

    # 配置建议
    if required_ok:
        print("\n✅ 内置库已就绪!")
        print("\n下一步:")
        print("1. 确认config.json中的配置:")
        print("   - use_builtin_libs: true")
        print("   - tushare.token: 已配置")
        print("\n2. 运行测试:")
        print("   python test/test_tushare_validation.py")
    else:
        print("\n⚠️ 请解决上述问题后再使用StockDataMaster")

    print("="*70 + "\n")


if __name__ == '__main__':
    main()

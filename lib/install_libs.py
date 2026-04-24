"""
内置库自动安装脚本

自动下载和安装StockDataMaster需要的内置库
"""

import os
import sys
import subprocess
import shutil


def install_builtin_libs(auto_confirm=False):
    """安装内置依赖库到lib目录"""

    # 获取当前脚本所在目录(即lib目录)
    lib_dir = os.path.dirname(os.path.abspath(__file__))

    print("="*70)
    print("StockDataMaster 内置库安装脚本")
    print("="*70)
    print(f"目标目录: {lib_dir}\n")

    # 需要安装的库列表(使用当前环境的实际版本)
    libraries = [
        ('mootdx', '0.11.7'),     # 通达信数据接口(从.conda环境复制的版本)
        ('baostock', '0.8.9'),    # Baostock数据接口(从.conda环境复制的版本)
        ('tushare', '1.4.24'),    # Tushare数据接口(用于日K线数据校核)
        ('tdxpy', '0.2.7'),
        # xtquant需要手动安装或从QMT环境复制(依赖QMT客户端)
    ]

    # 可选库(如果系统没有则安装)
    optional_libs = [
        ('pandas', '1.3.5'),
    ]

    print("将安装以下库:")
    for lib, version in libraries:
        print(f"  - {lib} ({version})")
    print("")

    # 确认安装
    if not auto_confirm:
        try:
            confirm = input("是否继续? (y/n): ")
        except EOFError:
            confirm = ''
        if confirm.lower() != 'y':
            print("取消安装")
            return

    print("\n开始安装...\n")

    # 安装每个库
    for lib, version in libraries:
        print(f"正在安装 {lib} {version}...")

        try:
            # 使用pip下载到lib目录
            cmd = [
                sys.executable, '-m', 'pip', 'install',
                f'{lib}=={version}',
                '--target', lib_dir,
                '--no-deps',  # 不安装依赖(手动控制)
                '--upgrade'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✓ {lib} 安装成功")
            else:
                print(f"✗ {lib} 安装失败: {result.stderr}")

        except Exception as e:
            print(f"✗ {lib} 安装异常: {e}")

    # 清理不需要的文件
    print("\n清理临时文件...")
    cleanup_patterns = [
        '*.dist-info',
        '*.egg-info',
        '__pycache__',
        '*.pyc',
        '*.pyo'
    ]

    for pattern in cleanup_patterns:
        for root, dirs, files in os.walk(lib_dir):
            # 删除匹配的目录
            for d in dirs:
                if pattern.replace('*', '') in d or d == pattern:
                    dir_path = os.path.join(root, d)
                    try:
                        shutil.rmtree(dir_path)
                        print(f"  删除: {dir_path}")
                    except:
                        pass

            # 删除匹配的文件
            for f in files:
                if pattern.replace('*', '') in f and f != 'install_libs.py':
                    file_path = os.path.join(root, f)
                    try:
                        os.remove(file_path)
                    except:
                        pass

    print("\n安装完成!")
    print("="*70)

    # 验证安装
    print("\n验证安装...")
    verify_installation(lib_dir)


def verify_installation(lib_dir):
    """验证内置库安装"""

    required_libs = ['mootdx', 'baostock', 'tushare']  # tushare用于日K线数据校核
    optional_libs = ['xtquant']  # 可选库(依赖QMT客户端)

    print("\n检查已安装的库:")
    print("\n必需库:")

    for lib in required_libs:
        lib_path = os.path.join(lib_dir, lib)

        if os.path.exists(lib_path) and os.path.isdir(lib_path):
            # 检查__init__.py是否存在
            init_file = os.path.join(lib_path, '__init__.py')
            if os.path.exists(init_file):
                print(f"  ✓ {lib}: 已安装")
            else:
                print(f"  ⚠ {lib}: 目录存在但缺少__init__.py")
        else:
            print(f"  ✗ {lib}: 未安装")

    print("\n可选库:")
    for lib in optional_libs:
        lib_path = os.path.join(lib_dir, lib)

        if os.path.exists(lib_path) and os.path.isdir(lib_path):
            init_file = os.path.join(lib_path, '__init__.py')
            if os.path.exists(init_file):
                print(f"  ✓ {lib}: 已安装")
            else:
                print(f"  ⚠ {lib}: 目录存在但缺少__init__.py")
        else:
            print(f"  - {lib}: 未安装(可选)")

    print("\n")


def uninstall_builtin_libs():
    """卸载内置库"""

    lib_dir = os.path.dirname(os.path.abspath(__file__))

    print("="*70)
    print("卸载内置库")
    print("="*70)

    libraries = ['mootdx', 'baostock', 'tushare', 'pandas']

    print("将删除以下库:")
    for lib in libraries:
        lib_path = os.path.join(lib_dir, lib)
        if os.path.exists(lib_path):
            print(f"  - {lib}")

    confirm = input("\n确认删除? (y/n): ")
    if confirm.lower() != 'y':
        print("取消卸载")
        return

    print("\n开始卸载...")

    for lib in libraries:
        lib_path = os.path.join(lib_dir, lib)
        if os.path.exists(lib_path):
            try:
                shutil.rmtree(lib_path)
                print(f"✓ 已删除 {lib}")
            except Exception as e:
                print(f"✗ 删除失败 {lib}: {e}")

    print("\n卸载完成!")


if __name__ == '__main__':
    args = sys.argv[1:]
    if 'uninstall' in args:
        uninstall_builtin_libs()
    else:
        auto_confirm = any(a in ('-y', '--yes', '-Y') for a in args)
        install_builtin_libs(auto_confirm=auto_confirm)

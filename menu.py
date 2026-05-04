"""StockDataMaster 一键操作菜单"""
import os
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = sys.executable


def clear():
    os.system("cls")


def pause():
    input("\n  按 Enter 键返回菜单...")


def header():
    print()
    print("  ================================================================")
    print("   StockDataMaster  v1.2.0")
    print("  ================================================================")


def run_cmd(cmd):
    """在项目根目录执行命令，实时输出到控制台"""
    os.chdir(ROOT)
    os.system(cmd)


# ── 各选项实现 ────────────────────────────────────────────────────────────────

def install_deps():
    clear(); header()
    print("\n  [1] 安装核心依赖\n")
    run_cmd(f'"{PYTHON}" -m pip install pandas numpy mootdx baostock tushare')
    pause()


def install_libs():
    clear(); header()
    print("\n  [2] 安装内置库到 lib/ 目录\n")
    script = ROOT / "lib" / "install_libs.py"
    if not script.exists():
        print(f"  [FAIL] 未找到 {script}")
    else:
        run_cmd(f'"{PYTHON}" "{script}"')
    pause()


def edit_config():
    cfg = ROOT / "config.json"
    if not cfg.exists():
        print("  [FAIL] 未找到 config.json"); pause(); return
    if subprocess.run("where code", shell=True, capture_output=True).returncode == 0:
        os.system(f'start "" code "{cfg}"')
    else:
        os.system(f'start "" notepad "{cfg}"')


def run_unit_tests():
    clear(); header()
    print("\n  [4] 运行单元测试 (marker: unit)\n")
    run_cmd(f'"{PYTHON}" -X utf8 -m pytest test/suite/ -v -m unit')
    pause()


def run_all_tests():
    clear(); header()
    print("\n  [5] 运行全量测试（包含集成测试，需网络）\n")
    run_cmd(f'"{PYTHON}" -X utf8 -m pytest test/suite/ -v')
    pause()


def run_gui():
    clear(); header()
    print("\n  [6] 启动交互式测试 GUI（关闭 GUI 窗口后返回菜单）\n")
    script = ROOT / "test" / "interactive_test_gui.py"
    if not script.exists():
        print(f"  [FAIL] 未找到 {script}"); pause(); return
    run_cmd(f'"{PYTHON}" "{script}"')


def pre_release():
    clear(); header()
    print("\n  [7] 发布前质量检查\n")
    script = ROOT / "scripts" / "pre_release_check.py"
    if not script.exists():
        print(f"  [FAIL] 未找到 {script}")
    else:
        run_cmd(f'"{PYTHON}" -X utf8 "{script}"')
    pause()


def serve_docs():
    clear(); header()
    print("\n  [8] 启动本地文档服务器\n")
    script = ROOT / "serve_docs.py"
    if not script.exists():
        print(f"  [FAIL] 未找到 {script}"); pause(); return
    print("  文档地址: http://localhost:8080")
    print("  服务运行在独立窗口，关闭该窗口即可停止。\n")
    # 在新控制台窗口中运行，不阻塞菜单
    subprocess.Popen(
        [PYTHON, str(script)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=str(ROOT),
    )
    time.sleep(1)
    print("  [OK] 文档服务已启动，浏览器将自动打开")
    pause()


def view_log():
    clear(); header()
    print("\n  [9] 查看运行日志\n")
    log = ROOT / "logs" / "data_master.log"
    if not log.exists():
        print(f"  日志文件不存在: {log}")
        print("  请先运行一次数据获取操作以生成日志")
        pause()
        return
    print(f"  文件: {log}")
    print("  " + "-" * 60)
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-50:]:
            print(" ", line.rstrip())
    except Exception as e:
        print(f"  读取失败: {e}")
    print("  " + "-" * 60)
    choice = input("\n  按 N 用记事本打开完整日志，其他键返回: ").strip().upper()
    if choice == "N":
        os.system(f'start "" notepad "{log}"')


# ── 主菜单循环 ────────────────────────────────────────────────────────────────

ACTIONS = {
    "1": install_deps,
    "2": install_libs,
    "3": edit_config,
    "4": run_unit_tests,
    "5": run_all_tests,
    "6": run_gui,
    "7": pre_release,
    "8": serve_docs,
    "9": view_log,
}


def main():
    while True:
        clear()
        header()
        print()
        print("   安装 / 配置")
        print("   [1] 安装核心依赖")
        print("   [2] 安装内置库 (lib/)")
        print("   [3] 编辑配置文件 (config.json)")
        print()
        print("   开发 / 测试")
        print("   [4] 运行单元测试  （无需网络）")
        print("   [5] 运行全量测试  （需网络）")
        print("   [6] 启动交互式测试 GUI")
        print("   [7] 发布前质量检查")
        print()
        print("   服务 / 工具")
        print("   [8] 启动文档服务器")
        print("   [9] 查看运行日志")
        print()
        print("   [0] 退出")
        print()
        print("  ================================================================")

        choice = input("  请输入选项 [0-9]: ").strip()

        if choice == "0":
            print("\n  再见！\n")
            sys.exit(0)

        action = ACTIONS.get(choice)
        if action:
            action()
        else:
            print("  [!] 无效选项")
            time.sleep(1)


if __name__ == "__main__":
    main()

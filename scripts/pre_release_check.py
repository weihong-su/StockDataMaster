#!/usr/bin/env python
"""
scripts/pre_release_check.py
============================
发布前强制检查脚本 - StockDataMaster 版本发布质量门禁

在新版本发布（打 tag、更新 __version__、发布到 PyPI）之前，
必须运行此脚本并通过所有检查。

检查项目：
  1. 版本号一致性（__init__.py == CHANGELOG.md 最新版本）
  2. CHANGELOG.md 包含新版本记录
  3. pytest 单元测试全部通过（排除集成测试）
  4. 无未提交的修改（git 工作区干净）

使用方法：
  python scripts/pre_release_check.py              # 标准检查
  python scripts/pre_release_check.py --skip-git   # 跳过 git 检查（CI环境）
  python scripts/pre_release_check.py --version 1.2.0  # 指定期望版本

退出码：
  0 - 所有检查通过，可以发布
  1 - 一个或多个检查失败，禁止发布
"""

import sys
import os
import re
import subprocess
import argparse
from datetime import datetime

# ─── 路径设置 ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PYTHON = sys.executable

# ─── 颜色输出 ────────────────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def ok(msg):    print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg):  print(f"  {RED}[FAIL]{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}[WARN]{RESET} {msg}")
def info(msg):  print(f"  {CYAN}[INFO]{RESET} {msg}")


class ReleaseChecker:
    def __init__(self, expected_version=None, skip_git=False):
        self.expected_version = expected_version
        self.skip_git = skip_git
        self.failures = []
        self.warnings = []

    def _fail(self, msg):
        self.failures.append(msg)
        fail(msg)

    def _warn(self, msg):
        self.warnings.append(msg)
        warn(msg)

    # ─── CHECK 1: 版本号一致性 ────────────────────────────────────────────────

    def check_version_consistency(self):
        print(f"\n{BOLD}[1/4] 版本号一致性检查{RESET}")

        # 从 __init__.py 读取版本
        init_path = os.path.join(PROJECT_ROOT, "__init__.py")
        if not os.path.exists(init_path):
            self._fail(f"__init__.py 不存在: {init_path}")
            return None

        with open(init_path, encoding='utf-8') as f:
            content = f.read()

        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if not m:
            self._fail("__init__.py 中未找到 __version__")
            return None
        code_version = m.group(1)
        info(f"代码版本 (__init__.py): {code_version}")

        # 从 CHANGELOG.md 读取最新版本
        changelog_path = os.path.join(PROJECT_ROOT, "CHANGELOG.md")
        if not os.path.exists(changelog_path):
            self._warn("CHANGELOG.md 不存在，跳过版本对比")
            return code_version

        with open(changelog_path, encoding='utf-8') as f:
            changelog = f.read()

        # 查找 ## [x.y.z] 格式的版本头
        versions_in_changelog = re.findall(r'## \[(\d+\.\d+\.\d+)\]', changelog)
        if not versions_in_changelog:
            self._fail("CHANGELOG.md 中未找到版本记录（格式: ## [x.y.z]）")
            return code_version

        latest_changelog_version = versions_in_changelog[0]
        info(f"CHANGELOG 最新版本: {latest_changelog_version}")

        if code_version != latest_changelog_version:
            self._fail(
                f"版本号不一致！代码: {code_version}，CHANGELOG: {latest_changelog_version}\n"
                f"         请同步更新 __init__.py 或 CHANGELOG.md"
            )
        else:
            ok(f"版本号一致: v{code_version}")

        # 检查期望版本（如果指定）
        if self.expected_version and code_version != self.expected_version:
            self._fail(
                f"版本号与期望不符！当前: {code_version}，期望: {self.expected_version}"
            )

        return code_version

    # ─── CHECK 2: CHANGELOG 内容检查 ──────────────────────────────────────────

    def check_changelog(self, version):
        print(f"\n{BOLD}[2/4] CHANGELOG.md 内容检查{RESET}")

        changelog_path = os.path.join(PROJECT_ROOT, "CHANGELOG.md")
        if not os.path.exists(changelog_path):
            self._fail("CHANGELOG.md 不存在")
            return

        with open(changelog_path, encoding='utf-8') as f:
            content = f.read()

        # 检查是否有 [Unreleased] 节
        if '[Unreleased]' not in content:
            self._warn("CHANGELOG.md 中未找到 [Unreleased] 节（建议保留）")

        # 检查版本节是否包含具体内容
        if version:
            pattern = rf'## \[{re.escape(version)}\].*?(?=## \[|\Z)'
            m = re.search(pattern, content, re.DOTALL)
            if m:
                section = m.group(0)
                # 简单验证：节中至少有 10 个非空白字符（除了标题本身）
                non_header = re.sub(r'## \[.*?\].*\n', '', section).strip()
                if len(non_header) > 10:
                    ok(f"v{version} 版本节包含变更记录（{len(non_header)} 字符）")
                else:
                    self._warn(f"v{version} 版本节内容过少，请补充变更说明")
            else:
                self._fail(f"CHANGELOG.md 中未找到 v{version} 的版本节")

    # ─── CHECK 3: pytest 单元测试 ──────────────────────────────────────────────

    def check_unit_tests(self):
        print(f"\n{BOLD}[3/4] 单元测试检查（pytest -m unit）{RESET}")

        suite_dir = os.path.join(PROJECT_ROOT, "test", "suite")
        if not os.path.exists(suite_dir):
            self._fail(f"测试套件目录不存在: {suite_dir}")
            return

        cmd = [
            PYTHON, "-X", "utf8", "-m", "pytest",
            "test/suite",
            "-m", "unit",
            "--tb=short",
            "-q",
            "--no-header",
            "-x",  # 首次失败即停止
        ]

        info(f"运行命令: {' '.join(cmd)}")
        info(f"工作目录: {PROJECT_ROOT}")

        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5分钟超时
            )

            # 打印输出
            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    print(f"    {line}")
            if result.stderr and result.returncode != 0:
                for line in result.stderr.strip().splitlines()[-20:]:
                    print(f"    {YELLOW}{line}{RESET}")

            if result.returncode == 0:
                ok("所有单元测试通过")
            else:
                self._fail(f"单元测试失败（退出码: {result.returncode}）")

        except subprocess.TimeoutExpired:
            self._fail("单元测试超时（> 5 分钟）")
        except FileNotFoundError:
            self._fail(f"Python 解释器未找到: {PYTHON}")
        except Exception as e:
            self._fail(f"运行测试时出现异常: {e}")

    # ─── CHECK 4: git 工作区 ──────────────────────────────────────────────────

    def check_git_status(self):
        print(f"\n{BOLD}[4/4] Git 工作区状态检查{RESET}")

        if self.skip_git:
            warn("已跳过 git 检查（--skip-git）")
            return

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=30
            )
            if result.returncode != 0:
                self._warn("无法执行 git status，跳过检查")
                return

            dirty_files = [
                line for line in result.stdout.strip().splitlines()
                if line.strip() and not line.startswith("??")  # 忽略未跟踪文件
            ]

            if dirty_files:
                self._fail(
                    f"Git 工作区有未提交的修改（{len(dirty_files)} 个文件）：\n"
                    + "\n".join(f"         {f}" for f in dirty_files[:10])
                )
            else:
                ok("Git 工作区干净，无未提交修改")

            # 检查是否有最新 commit
            log_result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=10
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                info(f"最新提交: {log_result.stdout.strip()}")

        except FileNotFoundError:
            self._warn("git 命令未找到，跳过 git 检查")
        except Exception as e:
            self._warn(f"git 检查异常: {e}")

    # ─── 汇总报告 ─────────────────────────────────────────────────────────────

    def run(self):
        print(f"\n{'=' * 65}")
        print(f"{BOLD}  StockDataMaster 发布前强制检查{RESET}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  项目: {PROJECT_ROOT}")
        print(f"{'=' * 65}")

        version = self.check_version_consistency()
        self.check_changelog(version)
        self.check_unit_tests()
        self.check_git_status()

        # ─── 最终结果 ─────────────────────────────────────────────────────────
        print(f"\n{'=' * 65}")
        print(f"{BOLD}  检查结果汇总{RESET}")
        print(f"{'=' * 65}")

        if self.warnings:
            print(f"\n{YELLOW}警告（{len(self.warnings)} 项）：{RESET}")
            for w in self.warnings:
                print(f"  - {w}")

        if self.failures:
            print(f"\n{RED}{BOLD}❌ 发布被阻止！{len(self.failures)} 项检查失败：{RESET}")
            for i, f in enumerate(self.failures, 1):
                print(f"  {i}. {f}")
            print(f"\n{RED}请修复上述问题后再次运行此脚本。{RESET}")
            print(f"{'=' * 65}\n")
            return 1
        else:
            if version:
                print(f"\n{GREEN}{BOLD}✅ 所有检查通过！版本 v{version} 可以发布。{RESET}")
            else:
                print(f"\n{GREEN}{BOLD}✅ 所有检查通过！{RESET}")
            print(f"\n下一步发布操作：")
            print(f"  1. git tag v{version or 'x.y.z'}")
            print(f"  2. git push origin v{version or 'x.y.z'}")
            print(f"  3. 在 GitHub 创建 Release 并附上 CHANGELOG 记录")
            print(f"{'=' * 65}\n")
            return 0


def main():
    parser = argparse.ArgumentParser(
        description="StockDataMaster 发布前强制检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--version',
        help="期望发布的版本号（如 1.2.0），用于验证代码版本是否匹配"
    )
    parser.add_argument(
        '--skip-git',
        action='store_true',
        help="跳过 git 工作区检查（适用于 CI/CD 环境）"
    )
    args = parser.parse_args()

    checker = ReleaseChecker(
        expected_version=args.version,
        skip_git=args.skip_git
    )
    sys.exit(checker.run())


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告摘要生成工具

用途：
- 解析多个测试报告JSON文件
- 生成汇总的Markdown报告
- 对比历史测试结果
- 生成趋势图表（可选）

使用方法：
python test/generate_test_summary.py --reports-dir test/reports --output docs/测试摘要报告.md
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# 路径设置
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)


class TestSummaryGenerator:
    """测试报告摘要生成器"""

    def __init__(self, reports_dir: str):
        self.reports_dir = reports_dir
        self.reports = []

    def load_reports(self, pattern: str = "*.json"):
        """加载所有测试报告"""
        import glob

        report_files = glob.glob(os.path.join(self.reports_dir, pattern))
        report_files.sort(reverse=True)  # 按时间倒序

        print(f"找到 {len(report_files)} 个测试报告")

        for report_file in report_files:
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                    report['file_path'] = report_file
                    report['file_name'] = os.path.basename(report_file)
                    self.reports.append(report)
            except Exception as e:
                print(f"加载报告失败 {report_file}: {str(e)}")

        return len(self.reports)

    def generate_summary(self, output_file: str, limit: int = 10):
        """生成摘要报告"""

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# StockDataMaster 测试摘要报告\n\n")

            # 总览
            f.write("## 测试总览\n\n")
            f.write(f"- **报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **测试报告数量**: {len(self.reports)}\n")
            f.write(f"- **最新测试**: {self.reports[0]['test_info']['test_time'] if self.reports else 'N/A'}\n\n")

            # 最近测试结果
            f.write("## 最近测试结果\n\n")
            f.write("| 测试时间 | 市场时段 | 总测试数 | 通过 | 失败 | 通过率 | 耗时 |\n")
            f.write("|----------|----------|----------|------|------|--------|------|\n")

            for report in self.reports[:limit]:
                test_info = report['test_info']
                test_results = report['test_results']

                f.write(f"| {test_info['test_time']} | ")
                f.write(f"{test_info.get('market_phase', 'N/A')} | ")
                f.write(f"{test_results['total_tests']} | ")
                f.write(f"{test_results['passed']} | ")
                f.write(f"{test_results['failed']} | ")
                f.write(f"{test_results['pass_rate']}% | ")
                f.write(f"{test_results.get('total_duration', 'N/A')} |\n")

            # 测试类别统计
            f.write("\n## 测试类别统计\n\n")

            if self.reports:
                latest_report = self.reports[0]
                categories = latest_report.get('test_categories', {})

                f.write("### 最新测试（")
                f.write(latest_report['test_info']['test_time'])
                f.write("）\n\n")

                for category, data in categories.items():
                    total = data.get('total', 0)
                    passed = data.get('passed', 0)
                    pass_rate = (passed / total * 100) if total > 0 else 0

                    f.write(f"#### {category}\n\n")
                    f.write(f"- 通过: {passed}/{total} ({pass_rate:.1f}%)\n")

                    if 'metrics' in data and data['metrics']:
                        f.write("\n**性能指标**:\n\n")
                        for key, value in data['metrics'].items():
                            f.write(f"- {key}: {value}\n")
                    f.write("\n")

            # 通过率趋势
            f.write("## 通过率趋势\n\n")

            if len(self.reports) >= 2:
                f.write("| 测试时间 | 通过率 | 变化 |\n")
                f.write("|----------|--------|------|\n")

                for i, report in enumerate(self.reports[:limit]):
                    pass_rate = report['test_results']['pass_rate']
                    test_time = report['test_info']['test_time']

                    if i > 0:
                        prev_rate = self.reports[i-1]['test_results']['pass_rate']
                        change = pass_rate - prev_rate
                        change_str = f"{change:+.1f}%" if change != 0 else "-"
                    else:
                        change_str = "-"

                    f.write(f"| {test_time} | {pass_rate}% | {change_str} |\n")
            else:
                f.write("暂无足够数据生成趋势分析\n")

            # 常见失败测试
            f.write("\n## 常见失败测试\n\n")

            failed_tests = defaultdict(int)

            for report in self.reports[:limit]:
                for result in report.get('detailed_results', []):
                    if not result['passed']:
                        failed_tests[result['test_name']] += 1

            if failed_tests:
                f.write("| 测试项 | 失败次数 |\n")
                f.write("|--------|----------|\n")

                for test_name, count in sorted(failed_tests.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"| {test_name} | {count} |\n")
            else:
                f.write("近期测试全部通过！\n")

            # 性能指标对比
            f.write("\n## 性能指标对比\n\n")

            if len(self.reports) >= 2:
                f.write("### 最新 vs 上次\n\n")

                latest = self.reports[0]
                previous = self.reports[1]

                latest_metrics = latest.get('performance_metrics', {})
                previous_metrics = previous.get('performance_metrics', {})

                if latest_metrics or previous_metrics:
                    f.write("| 指标 | 最新 | 上次 |\n")
                    f.write("|------|------|------|\n")

                    all_keys = set(latest_metrics.keys()) | set(previous_metrics.keys())

                    for key in all_keys:
                        latest_val = latest_metrics.get(key, 'N/A')
                        previous_val = previous_metrics.get(key, 'N/A')
                        f.write(f"| {key} | {latest_val} | {previous_val} |\n")
                else:
                    f.write("暂无性能指标数据\n")
            else:
                f.write("暂无足够数据进行对比\n")

            # 建议
            f.write("\n## 建议\n\n")

            if self.reports:
                latest = self.reports[0]
                pass_rate = latest['test_results']['pass_rate']

                if pass_rate >= 95:
                    f.write("- ✅ 测试通过率优秀 (≥95%)，系统状态良好\n")
                elif pass_rate >= 80:
                    f.write("- ⚠️ 测试通过率良好 (≥80%)，但仍有改进空间\n")
                else:
                    f.write("- ❌ 测试通过率较低 (<80%)，建议优先修复失败测试\n")

                failed_count = latest['test_results']['failed']
                if failed_count > 0:
                    f.write(f"- 当前有 {failed_count} 个测试失败，建议查看详细报告\n")

        print(f"摘要报告已生成: {output_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成测试报告摘要')
    parser.add_argument('--reports-dir', default='test/reports', help='测试报告目录')
    parser.add_argument('--output', default='docs/测试摘要报告.md', help='输出文件路径')
    parser.add_argument('--limit', type=int, default=10, help='最多分析的报告数量')

    args = parser.parse_args()

    generator = TestSummaryGenerator(args.reports_dir)

    count = generator.load_reports("pre_market_test_*.json")

    if count == 0:
        print("未找到测试报告")
        return

    generator.generate_summary(args.output, args.limit)


if __name__ == '__main__':
    main()

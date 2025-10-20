#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
StockDataMaster 交互式测试界面

功能:
1. K线数据测试 - 120天日K线展示和对比
2. 实时数据测试 - Tick数据实时显示
3. 数据源状态 - 健康检查和手动切换
4. 缓存管理 - 统计和清理

使用Tkinter实现图形界面,支持人工交互测试
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
import pandas as pd
import json
from typing import Dict, Any, Optional
import threading
import time
import sqlite3

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

lib_path = os.path.join(project_root, 'StockDataMaster', 'lib')
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# 日志文件路径
LOG_FILE = os.path.join(project_root, 'logs', f'interactive_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log_to_file(message: str):
    """写入日志文件"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")


class InteractiveTestGUI:
    """交互式测试图形界面"""

    def __init__(self, root):
        self.root = root
        self.root.title("StockDataMaster 交互式测试界面 v1.0")
        self.root.geometry("1400x900")

        # 数据
        self.master = None
        self.current_stock_code = "600000"
        self.current_freq = "d"
        self.auto_refresh = False
        self.refresh_interval = 5  # 秒

        # 初始化DataMaster
        self.init_datamaster()

        # 创建界面
        self.create_widgets()

        # 日志记录
        log_to_file("="*80)
        log_to_file("交互式测试界面启动")
        log_to_file(f"Python: {sys.executable}")
        log_to_file(f"项目路径: {project_root}")
        log_to_file("="*80)

    def init_datamaster(self):
        """初始化DataMaster"""
        try:
            from StockDataMaster.data_master import DataMaster
            self.master = DataMaster()
            log_to_file("✓ DataMaster初始化成功")
            log_to_file(f"可用数据源: {list(self.master.adapters.keys())}")
        except Exception as e:
            log_to_file(f"✗ DataMaster初始化失败: {e}")
            import traceback
            log_to_file(traceback.format_exc())
            messagebox.showerror("初始化失败", f"DataMaster初始化失败:\n{e}")
            sys.exit(1)

    def create_widgets(self):
        """创建界面组件"""
        # 创建Notebook (标签页)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 标签页1: 操作日志 (先创建,因为其他标签会用到log_message)
        self.create_log_tab()

        # 标签页2: K线数据测试
        self.create_kline_tab()

        # 标签页3: 实时数据测试
        self.create_realtime_tab()

        # 标签页4: 数据源状态
        self.create_datasource_tab()

        # 标签页5: 缓存管理
        self.create_cache_tab()

    def create_kline_tab(self):
        """创建K线数据测试标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="K线数据测试")

        # 顶部控制区
        control_frame = ttk.LabelFrame(frame, text="查询控制", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # 股票代码输入
        ttk.Label(control_frame, text="股票代码:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.stock_entry = ttk.Entry(control_frame, width=15)
        self.stock_entry.insert(0, "600000")
        self.stock_entry.grid(row=0, column=1, padx=5)

        # 频率选择
        ttk.Label(control_frame, text="频率:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.freq_var = tk.StringVar(value="d")
        freq_combo = ttk.Combobox(control_frame, textvariable=self.freq_var,
                                   values=["d", "5", "15", "30", "60"],
                                   width=8, state="readonly")
        freq_combo.grid(row=0, column=3, padx=5)

        # 数据条数
        ttk.Label(control_frame, text="数据条数:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.count_var = tk.StringVar(value="120")
        count_entry = ttk.Entry(control_frame, textvariable=self.count_var, width=8)
        count_entry.grid(row=0, column=5, padx=5)

        # 使用缓存
        self.use_cache_var = tk.BooleanVar(value=True)
        cache_check = ttk.Checkbutton(control_frame, text="使用缓存",
                                       variable=self.use_cache_var)
        cache_check.grid(row=0, column=6, padx=5)

        # 查询按钮
        query_btn = ttk.Button(control_frame, text="获取数据",
                               command=self.fetch_kline_data)
        query_btn.grid(row=0, column=7, padx=5)

        # 导出按钮
        export_btn = ttk.Button(control_frame, text="导出Excel",
                                command=self.export_kline_data)
        export_btn.grid(row=0, column=8, padx=5)

        # K线图按钮
        chart_btn = ttk.Button(control_frame, text="查看K线图",
                               command=self.show_kline_chart)
        chart_btn.grid(row=0, column=9, padx=5)

        # 数据信息区
        info_frame = ttk.LabelFrame(frame, text="数据信息", padding=10)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.kline_info_text = tk.Text(info_frame, height=4, width=100)
        self.kline_info_text.pack(fill=tk.X)

        # 数据展示区
        data_frame = ttk.LabelFrame(frame, text="K线数据 (双击行查看详情)", padding=5)
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建Treeview
        columns = ("日期", "开盘", "最高", "最低", "收盘", "涨跌幅%", "成交量", "成交额", "来源")
        self.kline_tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=20)

        for col in columns:
            self.kline_tree.heading(col, text=col)
            if col == "日期":
                self.kline_tree.column(col, width=100)
            elif col in ["开盘", "最高", "最低", "收盘"]:
                self.kline_tree.column(col, width=80)
            elif col == "涨跌幅%":
                self.kline_tree.column(col, width=80)
            elif col in ["成交量", "成交额"]:
                self.kline_tree.column(col, width=120)
            else:
                self.kline_tree.column(col, width=80)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.kline_tree.yview)
        self.kline_tree.configure(yscrollcommand=scrollbar.set)

        self.kline_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定双击事件
        self.kline_tree.bind("<Double-1>", self.show_kline_detail)

        # 存储当前数据
        self.current_kline_df = None

    def create_realtime_tab(self):
        """创建实时数据测试标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="实时数据测试")

        # 控制区
        control_frame = ttk.LabelFrame(frame, text="实时数据控制", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="股票代码:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.realtime_stock_entry = ttk.Entry(control_frame, width=15)
        self.realtime_stock_entry.insert(0, "600000")
        self.realtime_stock_entry.grid(row=0, column=1, padx=5)

        # 获取按钮
        get_btn = ttk.Button(control_frame, text="获取Tick",
                            command=self.fetch_tick_data)
        get_btn.grid(row=0, column=2, padx=5)

        # 自动刷新
        self.auto_refresh_var = tk.BooleanVar(value=False)
        auto_check = ttk.Checkbutton(control_frame, text="自动刷新(5秒)",
                                      variable=self.auto_refresh_var,
                                      command=self.toggle_auto_refresh)
        auto_check.grid(row=0, column=3, padx=5)

        # 实时数据展示区
        display_frame = ttk.LabelFrame(frame, text="实时行情", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.realtime_text = scrolledtext.ScrolledText(display_frame, height=30, width=100)
        self.realtime_text.pack(fill=tk.BOTH, expand=True)

        # 配置标签样式
        self.realtime_text.tag_config("header", font=("Courier New", 12, "bold"))
        self.realtime_text.tag_config("up", foreground="red")
        self.realtime_text.tag_config("down", foreground="green")
        self.realtime_text.tag_config("timestamp", foreground="gray")

    def create_datasource_tab(self):
        """创建数据源状态标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="数据源状态")

        # 顶部按钮
        btn_frame = ttk.Frame(frame, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="刷新状态", command=self.refresh_datasource_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="健康检查", command=self.run_health_check).pack(side=tk.LEFT, padx=5)

        # 数据源状态展示
        status_frame = ttk.LabelFrame(frame, text="数据源列表", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建Treeview
        columns = ("数据源", "状态", "优先级", "用途", "响应时间", "成功次数", "失败次数", "操作")
        self.datasource_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.datasource_tree.heading(col, text=col)
            if col == "数据源":
                self.datasource_tree.column(col, width=100)
            elif col == "状态":
                self.datasource_tree.column(col, width=80)
            elif col == "用途":
                self.datasource_tree.column(col, width=200)
            else:
                self.datasource_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.datasource_tree.yview)
        self.datasource_tree.configure(yscrollcommand=scrollbar.set)

        self.datasource_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 操作按钮区
        action_frame = ttk.LabelFrame(frame, text="数据源操作", padding=10)
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        self.datasource_action_text = tk.Text(action_frame, height=5, width=100)
        self.datasource_action_text.pack(fill=tk.X)

        # 初始加载 - 使用after延迟到界面初始化完成后
        self.root.after(100, self.refresh_datasource_status)

    def create_cache_tab(self):
        """创建缓存管理标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="缓存管理")

        # 顶部按钮
        btn_frame = ttk.Frame(frame, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="刷新统计", command=self.refresh_cache_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清理过期缓存", command=self.cleanup_cache).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清空所有缓存", command=self.clear_all_cache).pack(side=tk.LEFT, padx=5)

        # 缓存统计
        stats_frame = ttk.LabelFrame(frame, text="缓存统计", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        self.cache_stats_text = tk.Text(stats_frame, height=8, width=100)
        self.cache_stats_text.pack(fill=tk.X)

        # 缓存详情
        detail_frame = ttk.LabelFrame(frame, text="缓存详情", padding=5)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("股票代码", "记录数", "最早日期", "最新日期", "主源", "校验源", "更新时间")
        self.cache_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.cache_tree.heading(col, text=col)
            self.cache_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.cache_tree.yview)
        self.cache_tree.configure(yscrollcommand=scrollbar.set)

        self.cache_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 初始加载 - 使用after延迟到界面初始化完成后
        self.root.after(100, self.refresh_cache_stats)

    def create_log_tab(self):
        """创建操作日志标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="操作日志")

        # 顶部按钮
        btn_frame = ttk.Frame(frame, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存日志", command=self.save_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="打开日志文件", command=self.open_log_file).pack(side=tk.LEFT, padx=5)

        # 日志显示
        self.log_text = scrolledtext.ScrolledText(frame, height=35, width=120)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 配置标签
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("debug", foreground="gray")

    # ===== K线数据测试功能 =====

    def fetch_kline_data(self):
        """获取K线数据"""
        stock_code = self.stock_entry.get().strip()
        freq = self.freq_var.get()
        count = self.count_var.get()
        use_cache = self.use_cache_var.get()

        if not stock_code:
            messagebox.showwarning("警告", "请输入股票代码")
            return

        try:
            count = int(count)
        except:
            messagebox.showerror("错误", "数据条数必须为整数")
            return

        self.log_message(f"开始获取 {stock_code} {freq}周期 {count}条数据 (缓存:{use_cache})", "info")
        log_to_file(f">>> 获取K线数据: code={stock_code}, freq={freq}, count={count}, use_cache={use_cache}")

        # 异步获取数据
        threading.Thread(target=self._fetch_kline_thread,
                        args=(stock_code, freq, count, use_cache),
                        daemon=True).start()

    def _fetch_kline_thread(self, stock_code, freq, count, use_cache):
        """后台线程获取K线数据"""
        start_time = time.time()

        try:
            df = self.master.get_kline(stock_code, freq=freq, count=count, use_cache=use_cache)
            elapsed = time.time() - start_time

            if df is None or df.empty:
                self.root.after(0, lambda: self.log_message(f"未获取到数据 ({elapsed:.3f}s)", "warning"))
                log_to_file(f"<<< 未获取到数据, 耗时: {elapsed:.3f}s")
                return

            # 计算涨跌幅
            # 保存source属性(因为DataFrame操作可能丢失attrs)
            source_backup = df.attrs.get('source', None) if hasattr(df, 'attrs') else None

            if 'pct_chg' not in df.columns and len(df) > 1:
                df['pct_chg'] = df['close'].pct_change() * 100

            # 恢复source属性
            if source_backup is not None:
                df.attrs['source'] = source_backup

            # 更新界面
            self.root.after(0, lambda: self._update_kline_display(df, stock_code, freq, elapsed, use_cache))

            log_to_file(f"<<< 成功获取 {len(df)} 条数据, 耗时: {elapsed:.3f}s")

        except Exception as e:
            elapsed = time.time() - start_time
            self.root.after(0, lambda: self.log_message(f"获取失败: {e} ({elapsed:.3f}s)", "error"))
            log_to_file(f"<<< 获取失败: {e}, 耗时: {elapsed:.3f}s")
            import traceback
            log_to_file(traceback.format_exc())

    def _update_kline_display(self, df, stock_code, freq, elapsed, use_cache):
        """更新K线数据显示"""
        self.current_kline_df = df

        # 清空现有数据
        for item in self.kline_tree.get_children():
            self.kline_tree.delete(item)

        # 更新信息区
        info_text = f"股票代码: {stock_code}  |  频率: {freq}  |  数据条数: {len(df)}  |  " \
                   f"日期范围: {df['date'].min()} ~ {df['date'].max()}  |  " \
                   f"耗时: {elapsed:.3f}s  |  缓存: {'是' if use_cache else '否'}\n"

        # 添加数据源信息
        if hasattr(df, 'attrs') and 'source' in df.attrs:
            info_text += f"数据来源: {df.attrs['source']}\n"

        # 添加最新数据摘要
        latest = df.iloc[-1]
        info_text += f"最新: {latest['date']} 收盘={latest['close']:.2f}"
        if 'pct_chg' in latest and not pd.isna(latest['pct_chg']):
            info_text += f" 涨跌={latest['pct_chg']:+.2f}%"

        self.kline_info_text.delete('1.0', tk.END)
        self.kline_info_text.insert('1.0', info_text)

        # 填充数据
        for idx, row in df.iterrows():
            date = row.get('date', '')
            # 强制转换为float类型，避免Series ambiguous错误
            open_price = float(row.get('open', 0)) if not pd.isna(row.get('open')) else 0.0
            high = float(row.get('high', 0)) if not pd.isna(row.get('high')) else 0.0
            low = float(row.get('low', 0)) if not pd.isna(row.get('low')) else 0.0
            close = float(row.get('close', 0)) if not pd.isna(row.get('close')) else 0.0
            pct_chg = float(row.get('pct_chg', 0)) if not pd.isna(row.get('pct_chg')) else 0.0
            volume = float(row.get('volume', 0)) if not pd.isna(row.get('volume')) else 0.0
            amount = float(row.get('amount', 0)) if not pd.isna(row.get('amount')) else 0.0

            # 格式化 - 现在volume和amount都是float类型，可以安全比较
            pct_str = f"{pct_chg:+.2f}" if pct_chg != 0 else "0.00"

            # 成交量: 转换为手 (1手=100股),显示为手/万手
            volume_in_lots = volume / 100  # 转换为手
            if volume_in_lots < 10000:
                volume_str = f"{volume_in_lots:.0f}手"
            else:
                volume_str = f"{volume_in_lots/10000:.2f}万手"

            # 成交额: Tushare返回的是千元,需要除以10转成万元
            amount_in_wan = amount / 10  # 千元转万元
            if amount_in_wan < 10000:
                amount_str = f"{amount_in_wan:.2f}万"
            else:
                amount_str = f"{amount_in_wan/10000:.2f}亿"

            source = "未知"
            if hasattr(df, 'attrs') and 'source' in df.attrs:
                source = df.attrs['source']

            values = (
                date,
                f"{open_price:.2f}",
                f"{high:.2f}",
                f"{low:.2f}",
                f"{close:.2f}",
                pct_str,
                volume_str,
                amount_str,
                source
            )

            # 插入并设置颜色
            item = self.kline_tree.insert('', 'end', values=values)
            if not pd.isna(pct_chg):
                if pct_chg > 0:
                    self.kline_tree.item(item, tags=('up',))
                elif pct_chg < 0:
                    self.kline_tree.item(item, tags=('down',))

        # 设置标签颜色
        self.kline_tree.tag_configure('up', foreground='red')
        self.kline_tree.tag_configure('down', foreground='green')

        # 日志
        self.log_message(f"成功获取 {stock_code} {len(df)}条数据 ({elapsed:.3f}s)", "success")

    def show_kline_detail(self, event):
        """双击显示K线详情"""
        selection = self.kline_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.kline_tree.item(item, 'values')

        detail = f"日期: {values[0]}\n" \
                f"开盘: {values[1]}\n" \
                f"最高: {values[2]}\n" \
                f"最低: {values[3]}\n" \
                f"收盘: {values[4]}\n" \
                f"涨跌幅: {values[5]}%\n" \
                f"成交量: {values[6]}\n" \
                f"成交额: {values[7]}\n" \
                f"数据源: {values[8]}"

        messagebox.showinfo("K线详情", detail)

    def export_kline_data(self):
        """导出K线数据到Excel"""
        if self.current_kline_df is None or self.current_kline_df.empty:
            messagebox.showwarning("警告", "没有数据可导出")
            return

        filename = f"kline_{self.stock_entry.get()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(project_root, 'test', filename)

        try:
            self.current_kline_df.to_excel(filepath, index=False)
            self.log_message(f"数据已导出到: {filepath}", "success")
            messagebox.showinfo("成功", f"数据已导出到:\n{filepath}")
        except Exception as e:
            self.log_message(f"导出失败: {e}", "error")
            messagebox.showerror("错误", f"导出失败:\n{e}")

    def show_kline_chart(self):
        """显示K线图"""
        if self.current_kline_df is None or self.current_kline_df.empty:
            messagebox.showwarning("警告", "请先获取K线数据")
            return

        try:
            import mplfinance as mpf
            import matplotlib.pyplot as plt
            from matplotlib import font_manager
            import matplotlib

            # 准备数据
            df = self.current_kline_df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
                messagebox.showerror("错误", "K线数据列不完整")
                return

            df_plot = df[['open', 'high', 'low', 'close', 'volume']]

            # ========== 中文字体配置 - 多层防护 ==========

            # 方案1: 查找系统可用的中文字体
            chinese_fonts = []
            for font in font_manager.fontManager.ttflist:
                font_name = font.name
                # 检查是否为常见中文字体
                if any(name in font_name for name in ['Microsoft YaHei', 'SimHei', 'SimSun',
                                                        'KaiTi', 'FangSong', 'Microsoft',
                                                        'YaHei', 'Hei', 'Song']):
                    chinese_fonts.append(font_name)

            if chinese_fonts:
                log_to_file(f"找到可用中文字体: {chinese_fonts[:3]}")
                matplotlib.rcParams['font.sans-serif'] = chinese_fonts[:3]
            else:
                log_to_file("警告: 未找到中文字体,使用默认配置")
                matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']

            # 方案2: 直接指定字体文件
            font_paths = [
                r"C:\Windows\Fonts\msyh.ttc",    # 微软雅黑
                r"C:\Windows\Fonts\simhei.ttf",  # 黑体
                r"C:\Windows\Fonts\simsun.ttc",  # 宋体
            ]

            font_prop = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        from matplotlib.font_manager import FontProperties
                        font_prop = FontProperties(fname=font_path)
                        log_to_file(f"加载字体文件成功: {font_path}")
                        break
                    except Exception as e:
                        log_to_file(f"加载字体文件失败: {font_path}, {e}")

            # 通用配置
            matplotlib.rcParams['font.family'] = 'sans-serif'
            matplotlib.rcParams['axes.unicode_minus'] = False

            # 获取股票代码和频率名称
            stock_code = self.stock_entry.get().strip()
            freq_name = {'d': '日线', '5': '5分钟', '15': '15分钟', '30': '30分钟', '60': '60分钟'}.get(self.freq_var.get(), '日线')

            # 创建自定义样式
            mc = mpf.make_marketcolors(
                up='red', down='green',
                edge='inherit',
                wick='inherit',
                volume='in',
                alpha=0.9
            )

            # 如果找到了字体,在样式中使用
            if font_prop:
                s = mpf.make_mpf_style(
                    marketcolors=mc,
                    gridstyle='-',
                    gridcolor='lightgray',
                    gridaxis='both',
                    y_on_right=False,
                    rc={'font.family': font_prop.get_name()}  # 使用字体
                )
            else:
                s = mpf.make_mpf_style(
                    marketcolors=mc,
                    gridstyle='-',
                    gridcolor='lightgray',
                    gridaxis='both',
                    y_on_right=False
                )

            # 绘制K线图 - 使用matplotlib的title而非mplfinance的title
            fig, axes = mpf.plot(
                df_plot,
                type='candle',
                volume=True,
                title='',  # 不使用mplfinance的标题
                ylabel='',  # 暂时不设置ylabel,后面手动设置
                ylabel_lower='',
                style=s,
                figsize=(14, 8),
                show_nontrading=False,
                returnfig=True
            )

            # 手动添加标题和标签 - 使用指定字体
            ax_main = axes[0]

            # 获取股票名称用于标题显示
            stock_name = None
            try:
                stock_name = self.master.get_stock_name(stock_code)
            except:
                pass

            # 构建标题: 股票代码 + 股票名称 + K线图
            if stock_name:
                title_text = f'{stock_code} {stock_name} K线图 ({freq_name})'
            else:
                title_text = f'{stock_code} K线图 ({freq_name})'

            if font_prop:
                ax_main.set_title(title_text, fontproperties=font_prop, fontsize=14, pad=15)
                ax_main.set_ylabel('价格', fontproperties=font_prop, fontsize=11)
                if len(axes) > 1:
                    axes[1].set_ylabel('成交量', fontproperties=font_prop, fontsize=11)
            else:
                ax_main.set_title(title_text, fontsize=14, pad=15)
                ax_main.set_ylabel('价格', fontsize=11)
                if len(axes) > 1:
                    axes[1].set_ylabel('成交量', fontsize=11)

            # 优化Y轴范围 - 从最低价下方一点开始
            try:
                # 获取K线数据的价格范围
                price_min = df_plot['low'].min()
                price_max = df_plot['high'].max()
                price_range = price_max - price_min

                # 设置Y轴范围: 最低价下方留5%空间,最高价上方留5%空间
                y_margin = price_range * 0.05
                ax_main.set_ylim(
                    price_min - y_margin,  # 下限: 最低价 - 5%
                    price_max + y_margin   # 上限: 最高价 + 5%
                )

                log_to_file(f"K线图Y轴范围优化: [{price_min - y_margin:.2f}, {price_max + y_margin:.2f}]")
            except Exception as e:
                log_to_file(f"Y轴范围优化失败: {e}")

            # 添加鼠标十字线功能
            # 创建十字线
            crosshair_v = ax_main.axvline(x=0, color='gray', linestyle='--', linewidth=0.8, visible=False)
            crosshair_h = ax_main.axhline(y=0, color='gray', linestyle='--', linewidth=0.8, visible=False)

            # 创建文本标注
            text_box = ax_main.text(
                0.02, 0.95, '',
                transform=ax_main.transAxes,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                verticalalignment='top',
                fontproperties=font_prop if font_prop else None,
                fontsize=9,
                visible=False
            )

            def on_mouse_move(event):
                """鼠标移动事件处理"""
                if event.inaxes == ax_main:
                    # 显示十字线
                    crosshair_v.set_visible(True)
                    crosshair_h.set_visible(True)
                    text_box.set_visible(True)

                    # 更新十字线位置
                    crosshair_v.set_xdata([event.xdata])
                    crosshair_h.set_ydata([event.ydata])

                    # 获取最近的K线数据
                    try:
                        x_idx = int(round(event.xdata))
                        if 0 <= x_idx < len(df_plot):
                            row = df_plot.iloc[x_idx]
                            date_str = row.name.strftime('%Y-%m-%d') if hasattr(row.name, 'strftime') else str(row.name)

                            # 计算成交量显示格式
                            volume = row['volume']
                            volume_in_lots = volume / 100  # 转换为手
                            if volume_in_lots < 10000:
                                volume_str = f"{volume_in_lots:.0f}手"
                            else:
                                volume_str = f"{volume_in_lots/10000:.2f}万手"

                            # 格式化显示信息
                            info_text = (
                                f"日期: {date_str}\n"
                                f"开盘: {row['open']:.2f}\n"
                                f"最高: {row['high']:.2f}\n"
                                f"最低: {row['low']:.2f}\n"
                                f"收盘: {row['close']:.2f}\n"
                                f"成交量: {volume_str}"
                            )
                            text_box.set_text(info_text)
                    except Exception as e:
                        # 忽略越界等错误
                        pass

                    fig.canvas.draw_idle()
                else:
                    # 隐藏十字线
                    crosshair_v.set_visible(False)
                    crosshair_h.set_visible(False)
                    text_box.set_visible(False)
                    fig.canvas.draw_idle()

            # 绑定鼠标移动事件
            fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)

            plt.show()

            self.log_message(f"K线图已显示: {stock_code}", "success")

        except ImportError:
            messagebox.showerror("错误", "缺少mplfinance库\n请安装: pip install mplfinance")
            self.log_message("缺少mplfinance库", "error")
        except Exception as e:
            messagebox.showerror("错误", f"绘制K线图失败:\n{e}")
            self.log_message(f"绘制K线图失败: {e}", "error")
            import traceback
            log_to_file(traceback.format_exc())

    # ===== 实时数据测试功能 =====

    def fetch_tick_data(self):
        """获取Tick数据"""
        stock_code = self.realtime_stock_entry.get().strip()

        if not stock_code:
            messagebox.showwarning("警告", "请输入股票代码")
            return

        self.log_message(f"获取 {stock_code} 实时Tick数据", "info")
        log_to_file(f">>> 获取Tick数据: code={stock_code}")

        threading.Thread(target=self._fetch_tick_thread,
                        args=(stock_code,),
                        daemon=True).start()

    def _fetch_tick_thread(self, stock_code):
        """后台获取Tick数据"""
        start_time = time.time()

        try:
            tick = self.master.get_tick(stock_code)
            elapsed = time.time() - start_time

            if tick is None:
                self.root.after(0, lambda: self.log_message(f"未获取到Tick数据 ({elapsed:.3f}s)", "warning"))
                log_to_file(f"<<< 未获取到Tick数据, 耗时: {elapsed:.3f}s")
                return

            self.root.after(0, lambda: self._update_tick_display(tick, stock_code, elapsed))
            log_to_file(f"<<< 成功获取Tick数据, 耗时: {elapsed:.3f}s, 数据: {tick}")

        except Exception as e:
            elapsed = time.time() - start_time
            self.root.after(0, lambda: self.log_message(f"获取Tick失败: {e} ({elapsed:.3f}s)", "error"))
            log_to_file(f"<<< 获取Tick失败: {e}, 耗时: {elapsed:.3f}s")
            import traceback
            log_to_file(traceback.format_exc())

    def _update_tick_display(self, tick, stock_code, elapsed):
        """更新Tick数据显示"""
        self.realtime_text.delete('1.0', tk.END)

        # 获取股票名称 - 详细的错误处理
        stock_name = None
        name_status = "未获取"

        try:
            # 检查baostock适配器是否可用
            if 'baostock' not in self.master.adapters:
                name_status = "baostock数据源不可用"
                log_to_file(f"错误: {name_status}")
            else:
                # 确保baostock已登录
                try:
                    import baostock as bs
                    lg = bs.login()
                    if lg.error_code != '0':
                        name_status = f"baostock登录失败: {lg.error_msg}"
                        log_to_file(name_status)
                    else:
                        log_to_file("baostock登录成功")

                        # 尝试获取股票名称
                        stock_name = self.master.get_stock_name(stock_code)

                        if stock_name:
                            name_status = f"成功: {stock_name}"
                            log_to_file(f"获取股票名称成功: {stock_code} = {stock_name}")
                        else:
                            name_status = "获取失败(API返回空)"
                            log_to_file(f"获取股票名称失败: {stock_code}, API返回None")

                except ImportError:
                    name_status = "baostock模块未安装"
                    log_to_file(f"错误: {name_status}")
                except Exception as e:
                    name_status = f"baostock异常: {str(e)}"
                    log_to_file(f"baostock登录/查询异常: {e}")
                    import traceback
                    log_to_file(traceback.format_exc())

        except Exception as e:
            name_status = f"异常: {str(e)}"
            error_msg = f"获取股票名称异常: {stock_code}, 错误: {e}"
            self.log_message(error_msg, "error")
            log_to_file(error_msg)
            import traceback
            log_to_file(traceback.format_exc())

        # 构建标题显示 - 明确显示状态
        if stock_name:
            name_display = f"{stock_code} {stock_name}"
        else:
            name_display = f"{stock_code} [{name_status}]"

        # 标题
        self.realtime_text.insert(tk.END, f"{'='*60}\n", "header")
        self.realtime_text.insert(tk.END, f"股票: {name_display}\n", "header")
        self.realtime_text.insert(tk.END, f"{'='*60}\n\n", "header")

        # 时间戳
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.realtime_text.insert(tk.END, f"更新时间: {timestamp}  (耗时: {elapsed:.3f}s)\n\n", "timestamp")

        # 基本信息
        if isinstance(tick, dict):
            # 在tick字典中添加code和name字段
            if 'code' not in tick:
                tick['code'] = stock_code

            # 添加股票名称 (从之前获取的stock_name变量)
            # 无论tick中是否有name键,都要用获取到的stock_name覆盖(确保不为空)
            if stock_name:
                tick['name'] = stock_name
            elif 'name' not in tick:
                tick['name'] = ''  # 确保name键存在

            self._display_tick_dict(tick, stock_name)
        else:
            self.realtime_text.insert(tk.END, str(tick))

        self.log_message(f"{stock_code} Tick数据已更新 ({elapsed:.3f}s)", "success")

    def _display_tick_dict(self, tick, stock_name=None):
        """格式化显示Tick字典"""
        # 股票代码和名称显示
        if 'code' in tick or stock_name:
            self.realtime_text.insert(tk.END, "【股票信息】\n", "header")

            # 显示股票代码
            if 'code' in tick:
                self.realtime_text.insert(tk.END, f"  股票代码: {tick['code']}\n")

            # 显示股票名称 - 优先使用参数,其次使用tick字典
            display_name = stock_name or tick.get('name', '')
            if display_name:
                self.realtime_text.insert(tk.END, f"  股票名称: {display_name}\n")

            self.realtime_text.insert(tk.END, "\n")

        # 数据源信息 (新增)
        self.realtime_text.insert(tk.END, "【数据源信息】\n", "header")
        source = tick.get('source', '未知')
        self.realtime_text.insert(tk.END, f"  当前数据源: {source}\n")

        # 获取健康状态
        try:
            health = self.master.get_health_status()
            if health and 'sources' in health:
                tick_sources = []
                for src_name, src_info in health['sources'].items():
                    src_config = self.master.config.get_data_source_config(src_name)
                    if src_config and 'tick' in src_config.get('use_for', []):
                        status_val = src_info.get('status', 'unknown')
                        status_icon = "✓" if status_val == 'ok' else "✗"
                        tick_sources.append(f"{src_name}({status_icon})")

                if tick_sources:
                    self.realtime_text.insert(tk.END, f"  可用Tick数据源: {', '.join(tick_sources)}\n")
        except Exception as e:
            self.realtime_text.insert(tk.END, f"  健康状态: 获取失败({e})\n")

        self.realtime_text.insert(tk.END, "\n")

        # 基本价格
        self.realtime_text.insert(tk.END, "【价格信息】\n", "header")

        # 修复: 添加'last'字段作为fallback (xtquant使用'last'存储最新价)
        # 优先级: current > price > last > 0
        current = tick.get('current', tick.get('price', tick.get('last', 0)))
        self.realtime_text.insert(tk.END, f"  最新价: {current:.2f}\n")

        if 'open' in tick:
            self.realtime_text.insert(tk.END, f"  今开: {tick['open']:.2f}\n")
        if 'high' in tick:
            self.realtime_text.insert(tk.END, f"  最高: {tick['high']:.2f}\n")
        if 'low' in tick:
            self.realtime_text.insert(tk.END, f"  最低: {tick['low']:.2f}\n")
        if 'close' in tick:
            self.realtime_text.insert(tk.END, f"  昨收: {tick['close']:.2f}\n")

        # 涨跌
        if 'percent' in tick or 'pct_chg' in tick:
            pct = tick.get('percent', tick.get('pct_chg', 0))
            tag = "up" if pct > 0 else "down"
            self.realtime_text.insert(tk.END, f"  涨跌幅: {pct:+.2f}%\n", tag)

        # 成交量成交额
        self.realtime_text.insert(tk.END, "\n【成交信息】\n", "header")
        if 'volume' in tick:
            vol = tick['volume']
            vol_str = f"{vol/10000:.2f}万" if vol < 1e8 else f"{vol/1e8:.2f}亿"
            self.realtime_text.insert(tk.END, f"  成交量: {vol_str}\n")
        if 'amount' in tick:
            amt = tick['amount']
            amt_str = f"{amt/10000:.2f}万" if amt < 1e8 else f"{amt/1e8:.2f}亿"
            self.realtime_text.insert(tk.END, f"  成交额: {amt_str}\n")

        # 买卖盘
        self.realtime_text.insert(tk.END, "\n【买卖盘口】\n", "header")
        for i in range(1, 6):
            bid_key = f'bid{i}'
            ask_key = f'ask{i}'
            bid_vol_key = f'bid{i}_volume'
            ask_vol_key = f'ask{i}_volume'

            if bid_key in tick and ask_key in tick:
                bid = tick[bid_key]
                ask = tick[ask_key]
                bid_vol = tick.get(bid_vol_key, 0)
                ask_vol = tick.get(ask_vol_key, 0)

                self.realtime_text.insert(tk.END,
                    f"  卖{i}: {ask:.2f} ({ask_vol})    买{i}: {bid:.2f} ({bid_vol})\n")

        # 其他信息
        self.realtime_text.insert(tk.END, "\n【其他信息】\n", "header")
        for key, value in tick.items():
            if key not in ['current', 'price', 'open', 'high', 'low', 'close',
                          'percent', 'pct_chg', 'volume', 'amount', 'source', 'code', 'name'] and \
               not key.startswith('bid') and not key.startswith('ask'):
                self.realtime_text.insert(tk.END, f"  {key}: {value}\n")

    def toggle_auto_refresh(self):
        """切换自动刷新"""
        self.auto_refresh = self.auto_refresh_var.get()

        if self.auto_refresh:
            self.log_message("启动自动刷新 (5秒间隔)", "info")
            self._auto_refresh_loop()
        else:
            self.log_message("停止自动刷新", "info")

    def _auto_refresh_loop(self):
        """自动刷新循环"""
        if not self.auto_refresh:
            return

        self.fetch_tick_data()
        self.root.after(5000, self._auto_refresh_loop)

    # ===== 数据源状态功能 =====

    def refresh_datasource_status(self):
        """刷新数据源状态"""
        try:
            self.log_message("刷新数据源状态", "info")
            log_to_file(">>> 刷新数据源状态")

            # 清空现有数据
            for item in self.datasource_tree.get_children():
                self.datasource_tree.delete(item)

            # 获取健康状态
            health_status = self.master.health_manager.get_health_report()
            log_to_file(f"健康状态数据: {health_status}")

            if not health_status or 'sources' not in health_status:
                self.log_message("无法获取健康状态数据", "warning")
                log_to_file("<<< 健康状态数据为空或格式错误")
                return

            sources_info = health_status.get('sources', {})

            if not sources_info:
                self.log_message("没有可用的数据源信息", "warning")
                log_to_file("<<< 没有数据源信息")
                return

            for source_name, source_info in sources_info.items():
                try:
                    # 安全地获取字段
                    status_value = source_info.get('status', 'unknown')

                    # 状态显示
                    if status_value == 'ok':
                        status = "✓ 可用"
                    elif status_value == 'warning':
                        status = "⚠ 警告"
                    elif status_value == 'error':
                        status = "✗ 错误"
                    else:
                        status = "? 未知"

                    # 优先级(从config获取)
                    source_config = self.master.config.get_data_source_config(source_name)
                    priority = source_config.get('priority', '-') if source_config else '-'

                    # 用途(从config获取)
                    use_for = source_config.get('use_for', []) if source_config else []
                    use_for_str = ', '.join(use_for) if use_for else '-'

                    # 响应时间
                    response_time = source_info.get('response_time', '-')
                    if isinstance(response_time, (int, float)):
                        response_time_str = f"{response_time:.2f}s"
                    elif isinstance(response_time, str) and response_time != '-':
                        try:
                            # 尝试解析字符串中的数字
                            response_time_str = response_time
                        except:
                            response_time_str = response_time
                    else:
                        response_time_str = '-'

                    # 成功/失败次数(可能不存在)
                    success_count = source_info.get('success_count', 0)
                    failure_count = source_info.get('failure_count', 0)

                    # 插入到Treeview
                    self.datasource_tree.insert('', tk.END, values=(
                        source_name,
                        status,
                        priority,
                        use_for_str,
                        response_time_str,
                        success_count,
                        failure_count,
                        "操作"
                    ))

                    log_to_file(f"  {source_name}: status={status_value}, priority={priority}, use_for={use_for_str}")

                except Exception as e:
                    error_msg = f"处理数据源 {source_name} 时出错: {e}"
                    self.log_message(error_msg, "warning")
                    log_to_file(f"  ! {error_msg}")
                    continue

            self.log_message(f"已更新{len(sources_info)}个数据源状态", "success")
            log_to_file(f"<<< 刷新完成, {len(sources_info)}个数据源")

        except Exception as e:
            error_msg = f"刷新数据源状态失败: {e}"
            self.log_message(error_msg, "error")
            log_to_file(f"<<< {error_msg}")
            import traceback
            tb = traceback.format_exc()
            self.log_message(f"详细错误:\n{tb}", "debug")
            log_to_file(tb)

    def run_health_check(self):
        """运行健康检查"""
        self.log_message("执行健康检查...", "info")
        log_to_file(">>> 执行健康检查")

        threading.Thread(target=self._health_check_thread, daemon=True).start()

    def _health_check_thread(self):
        """后台健康检查"""
        start_time = time.time()

        try:
            # 触发健康检查(获取测试数据)
            test_code = '600000'
            for source_name in self.master.adapters.keys():
                try:
                    adapter = self.master.adapters[source_name]
                    # 简单测试
                    if source_name == 'tushare':
                        adapter.get_kline(test_code, 'd', count=1)
                    elif source_name == 'mootdx':
                        adapter.get_kline(f'sh.{test_code}', 'd', count=1)
                    elif source_name == 'baostock':
                        adapter.get_kline(f'sh.{test_code}', 'd', count=1)
                    log_to_file(f"  {source_name}: 测试通过")
                except Exception as e:
                    log_to_file(f"  {source_name}: 测试失败 - {e}")

            elapsed = time.time() - start_time

            # 刷新显示
            self.root.after(0, self.refresh_datasource_status)
            self.root.after(0, lambda: self.log_message(f"健康检查完成 ({elapsed:.2f}s)", "success"))
            log_to_file(f"<<< 健康检查完成, 耗时: {elapsed:.2f}s")

        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"健康检查失败: {e}", "error"))
            log_to_file(f"<<< 健康检查失败: {e}")
            import traceback
            log_to_file(traceback.format_exc())

    # ===== 缓存管理功能 =====

    def refresh_cache_stats(self):
        """刷新缓存统计"""
        self.log_message("刷新缓存统计", "info")
        log_to_file(">>> 刷新缓存统计")

        try:
            stats = self.master.get_cache_statistics()
            log_to_file(f"缓存统计: {stats}")

            # 更新统计文本
            stats_text = f"【缓存统计】\n\n"
            stats_text += f"缓存股票数: {stats.get('stock_count', 0)}\n"
            stats_text += f"总记录数: {stats.get('total_records', 0)}\n"
            stats_text += f"数据库大小: {stats.get('db_size_mb', 0):.2f} MB\n"
            # 处理date_range嵌套结构
            date_range = stats.get('date_range', {})
            stats_text += f"最早数据: {date_range.get('start', 'N/A')}\n"
            stats_text += f"最新数据: {date_range.get('end', 'N/A')}\n"

            self.cache_stats_text.delete('1.0', tk.END)
            self.cache_stats_text.insert('1.0', stats_text)

            # 更新详情列表
            for item in self.cache_tree.get_children():
                self.cache_tree.delete(item)

            # 查询缓存详情
            try:
                import sqlite3
                db_path = self.master.cache_manager.db_path
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    query = """
                        SELECT code,
                               COUNT(*) as count,
                               MIN(date) as min_date,
                               MAX(date) as max_date,
                               MAX(source1) as source1,
                               MAX(source2) as source2,
                               MAX(updated_at) as last_update
                        FROM kline_cache
                        GROUP BY code
                        ORDER BY last_update DESC
                        LIMIT 100
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    for row in rows:
                        self.cache_tree.insert('', 'end', values=row)

                    conn.close()
                    log_to_file(f"<<< 缓存详情: {len(rows)}只股票")
                else:
                    log_to_file(f"<<< 缓存数据库不存在: {db_path}")
            except Exception as e:
                log_to_file(f"<<< 查询缓存详情失败: {e}")
                import traceback
                log_to_file(traceback.format_exc())

            self.log_message(f"缓存统计已刷新", "success")

        except Exception as e:
            self.log_message(f"刷新失败: {e}", "error")
            log_to_file(f"<<< 刷新失败: {e}")
            import traceback
            log_to_file(traceback.format_exc())

    def cleanup_cache(self):
        """清理过期缓存"""
        if not messagebox.askyesno("确认", "确定要清理过期缓存吗?\n(保留最近120天数据)"):
            return

        self.log_message("清理过期缓存...", "info")
        log_to_file(">>> 清理过期缓存")

        try:
            self.master.cache_manager.cleanup_old_cache(days=120)
            self.log_message("过期缓存已清理", "success")
            log_to_file("<<< 清理完成")

            # 刷新统计
            self.refresh_cache_stats()

        except Exception as e:
            self.log_message(f"清理失败: {e}", "error")
            log_to_file(f"<<< 清理失败: {e}")

    def clear_all_cache(self):
        """清空所有缓存"""
        if not messagebox.askyesno("警告", "确定要清空所有缓存吗?\n此操作不可恢复!"):
            return

        self.log_message("清空所有缓存...", "warning")
        log_to_file(">>> 清空所有缓存")

        try:
            # 直接访问缓存数据库文件并清空
            db_path = self.master.cache_manager.db_path

            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # 执行删除操作
                cursor.execute("DELETE FROM kline_cache")
                deleted_count = cursor.rowcount

                # 提交事务
                conn.commit()
                conn.close()

                self.log_message(f"所有缓存已清空 (删除{deleted_count}条记录)", "success")
                log_to_file(f"<<< 清空完成: 删除{deleted_count}条记录")
            else:
                self.log_message("缓存数据库文件不存在", "warning")
                log_to_file("<<< 缓存数据库文件不存在")

            # 刷新统计
            self.refresh_cache_stats()

        except Exception as e:
            self.log_message(f"清空失败: {e}", "error")
            log_to_file(f"<<< 清空失败: {e}")

    # ===== 日志功能 =====

    def log_message(self, message, level="info"):
        """记录日志消息"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        full_message = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, full_message, level)
        self.log_text.see(tk.END)

    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', tk.END)

    def save_log(self):
        """保存日志"""
        content = self.log_text.get('1.0', tk.END)
        filename = f"interactive_test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(project_root, 'logs', filename)

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            messagebox.showinfo("成功", f"日志已保存到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败:\n{e}")

    def open_log_file(self):
        """打开日志文件"""
        try:
            os.startfile(LOG_FILE)
        except:
            messagebox.showinfo("提示", f"日志文件路径:\n{LOG_FILE}")


def main():
    """主函数"""
    root = tk.Tk()
    app = InteractiveTestGUI(root)

    # 设置图标(如果有)
    # root.iconbitmap('icon.ico')

    root.mainloop()

    # 关闭时记录
    log_to_file("="*80)
    log_to_file("交互式测试界面关闭")
    log_to_file("="*80)


if __name__ == '__main__':
    main()

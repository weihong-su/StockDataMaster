"""
健康检测和热切换管理器

负责监控数据源健康状态,实现故障自动切换
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import deque


class HealthManager:
    """健康检测和热切换管理器"""

    def __init__(self, config, adapters: Dict):
        """
        初始化健康管理器

        Args:
            config: 配置对象
            adapters: 适配器字典 {name: adapter}
        """
        self.config = config
        self.adapters = adapters
        self.logger = logging.getLogger("DataMaster.HealthManager")

        # 健康检查配置
        self.check_interval = config.get('health_check.interval_seconds', 60)
        self.response_threshold = config.get('health_check.response_time_threshold', 5.0)
        self.failure_threshold = config.get('health_check.consecutive_failures_threshold', 3)

        # 健康状态记录
        self.health_status = {}  # {adapter_name: {'status': 'ok', 'last_check': datetime, ...}}
        self.failure_counts = {}  # {adapter_name: count}

        # 当前活跃数据源(按用途分类)
        self.active_sources = {
            'kline': None,
            'valuation': None,
            'tick': None
        }

        # 切换历史记录(使用deque限制大小)
        self.switch_history = deque(maxlen=100)

        # 监控线程
        self.monitor_thread = None
        self.is_running = False
        self.lock = threading.Lock()

    def start_monitoring(self):
        """启动健康监控线程"""
        if self.is_running:
            self.logger.warning("健康监控已在运行中")
            return

        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"健康监控线程已启动,检查间隔: {self.check_interval}秒")

    def stop_monitoring(self):
        """停止健康监控线程"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("健康监控线程已停止")

    def _monitor_loop(self):
        """健康监控循环 - 增强版(交易时段感知)"""
        while self.is_running:
            try:
                # 1. 检查所有数据源健康状态
                self.check_all_sources()

                # 2. 交易时段自动恢复xtquant
                self._auto_recover_xtquant()

                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"健康监控异常: {e}")
                time.sleep(self.check_interval)

    def check_all_sources(self):
        """检查所有数据源的健康状态"""
        with self.lock:
            for name, adapter in self.adapters.items():
                try:
                    # 执行健康检查
                    result = adapter.health_check()

                    # 获取上一次的状态
                    prev_status = self.health_status.get(name, {}).get('status', 'unknown')

                    # 更新健康状态
                    self.health_status[name] = {
                        'status': result['status'],
                        'last_check': datetime.now(),
                        'response_time': result['response_time'],
                        'data_freshness': result['data_freshness'],
                        'error_message': result['error_message']
                    }

                    # 更新失败计数
                    if result['status'] == 'error':
                        self.failure_counts[name] = self.failure_counts.get(name, 0) + 1

                        # 只在首次失败或状态变化时记录WARNING
                        if prev_status != 'error' or self.failure_counts[name] == 1:
                            self.logger.warning(
                                f"{name} 健康检查失败: {result['error_message']}"
                            )
                        # 持续失败时只记录DEBUG级别
                        else:
                            self.logger.debug(
                                f"{name} 健康检查仍失败({self.failure_counts[name]}次): {result['error_message']}"
                            )

                        # 检查是否需要切换
                        if self.failure_counts[name] >= self.failure_threshold:
                            self._trigger_switch(name, result['error_message'])
                    else:
                        # 成功则重置失败计数
                        # 如果从失败恢复,记录INFO
                        if prev_status == 'error':
                            self.logger.info(f"{name} 健康检查已恢复")
                        self.failure_counts[name] = 0

                except Exception as e:
                    self.logger.error(f"{name} 健康检查异常: {e}")
                    self.failure_counts[name] = self.failure_counts.get(name, 0) + 1

    def _auto_recover_xtquant(self):
        """
        交易时段自动恢复xtquant数据源

        逻辑:
        1. 检查当前是否在交易时段(9:15-15:00)
        2. 如果xtquant可用但不是活跃数据源,尝试恢复
        3. xtquant在交易时段最权威,应优先使用
        """
        from datetime import datetime, time as time_type

        # 判断是否为交易时段
        now = datetime.now()
        current_time = now.time()
        market_start = time_type(9, 15)
        market_end = time_type(15, 0)
        is_trading_hours = market_start <= current_time <= market_end

        if not is_trading_hours:
            return  # 非交易时段不自动恢复

        # 检查xtquant是否存在且可用
        if 'xtquant' not in self.adapters:
            return

        xtquant_health = self.health_status.get('xtquant', {})
        if xtquant_health.get('status') != 'ok':
            return  # xtquant不健康,不恢复

        # 检查xtquant的用途
        xtquant_adapter = self.adapters['xtquant']
        xtquant_uses = xtquant_adapter.config.get('use_for', [])

        # 尝试恢复每个用途
        for usage in xtquant_uses:
            current_source = self.active_sources.get(usage)

            # 如果当前不是xtquant,且xtquant可用,则切换回xtquant
            if current_source != 'xtquant':
                with self.lock:
                    old_source = self.active_sources[usage]
                    self.active_sources[usage] = 'xtquant'
                    self.logger.info(
                        f"[交易时段] {usage}数据源已恢复: {old_source} -> xtquant (xtquant更权威)"
                    )

                    # 记录切换历史
                    self.switch_history.append({
                        'time': datetime.now(),
                        'usage': usage,
                        'from': old_source,
                        'to': 'xtquant',
                        'reason': '交易时段自动恢复xtquant(更权威)'
                    })

    def _trigger_switch(self, failed_source: str, reason: str):
        """
        触发数据源切换 - 增强版(时段感知)

        Args:
            failed_source: 失败的数据源名称
            reason: 切换原因

        时段感知逻辑:
        1. 交易时段(9:15-15:00): xtquant失败时严格切换
        2. 非交易时段: xtquant失败属正常,不频繁切换
        """
        from datetime import datetime, time as time_type

        # 判断是否为交易时段
        now = datetime.now()
        current_time = now.time()
        market_start = time_type(9, 15)
        market_end = time_type(15, 0)
        is_trading_hours = market_start <= current_time <= market_end

        # 如果是xtquant在非交易时段失败,降低日志级别
        if failed_source == 'xtquant' and not is_trading_hours:
            self.logger.debug(f"[非交易时段] xtquant失败属正常: {reason}")
            # 仍然切换,但不记录WARNING
        else:
            self.logger.warning(f"触发数据源切换: {failed_source}, 原因: {reason}")

        # 获取失败数据源的用途
        failed_adapter = self.adapters.get(failed_source)
        if not failed_adapter:
            return

        failed_uses = failed_adapter.config.get('use_for', [])

        # 对每个用途尝试切换
        for usage in failed_uses:
            if self.active_sources.get(usage) == failed_source:
                # 查找备用数据源
                backup = self._find_backup_source(usage, exclude=[failed_source])

                if backup:
                    old_source = self.active_sources[usage]
                    self.active_sources[usage] = backup
                    self.logger.info(f"{usage}数据源已切换: {old_source} -> {backup}")

                    # 记录切换历史
                    self.switch_history.append({
                        'time': datetime.now(),
                        'usage': usage,
                        'from': old_source,
                        'to': backup,
                        'reason': reason
                    })

                    # 通知(如果配置启用)
                    if self.config.get('hot_switch.switch_notification', False):
                        self._send_notification(usage, old_source, backup, reason)
                else:
                    self.logger.error(f"{usage}数据源无可用备份!")

    def _find_backup_source(self, usage: str, exclude: List[str] = None) -> Optional[str]:
        """
        查找备用数据源

        Args:
            usage: 用途类型 (kline/valuation/tick)
            exclude: 排除的数据源列表

        Returns:
            备用数据源名称,如果没有可用备份返回None
        """
        exclude = exclude or []

        # 获取所有支持该用途的数据源,按优先级排序
        candidates = []
        for name, adapter in self.adapters.items():
            if name in exclude:
                continue

            if not adapter.config.get('enabled', False):
                continue

            if usage not in adapter.config.get('use_for', []):
                continue

            # 检查健康状态
            health = self.health_status.get(name, {})
            if health.get('status') == 'ok':
                priority = adapter.config.get('priority', 999)
                candidates.append((name, priority))

        # 按优先级排序
        candidates.sort(key=lambda x: x[1])

        return candidates[0][0] if candidates else None

    def get_active_source(self, usage: str) -> Optional[str]:
        """
        获取当前活跃的数据源

        Args:
            usage: 用途类型 (kline/valuation/tick)

        Returns:
            数据源名称
        """
        with self.lock:
            # 如果还没有活跃数据源,选择一个
            if self.active_sources.get(usage) is None:
                self.active_sources[usage] = self._find_backup_source(usage)

            return self.active_sources[usage]

    def get_health_report(self) -> Dict[str, Any]:
        """
        获取健康状态报告

        Returns:
            健康状态字典
        """
        with self.lock:
            report = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'sources': {},
                'active_sources': self.active_sources.copy(),
                'recent_switches': list(self.switch_history)[-10:]  # 最近10次切换
            }

            for name, adapter in self.adapters.items():
                status = self.health_status.get(name, {})
                source_report = {
                    'enabled': adapter.config.get('enabled', False),
                    'connected': adapter.is_connected,
                    'status': status.get('status', 'unknown'),
                    'last_check': status.get('last_check', '').strftime('%H:%M:%S') if status.get('last_check') else 'N/A',
                    'response_time': f"{status.get('response_time', 0):.2f}s",
                    'failure_count': self.failure_counts.get(name, 0),
                    'error': status.get('error_message')
                }

                # 增强: 获取xtquant连接统计
                if name == 'xtquant' and hasattr(adapter, 'get_connection_stats'):
                    try:
                        conn_stats = adapter.get_connection_stats()
                        source_report['connection_stats'] = {
                            'connect_count': conn_stats.get('connect_count', 0),
                            'disconnect_count': conn_stats.get('disconnect_count', 0),
                            'reconnect_count': conn_stats.get('reconnect_count', 0),
                            'heartbeat_failures': conn_stats.get('heartbeat_failures', 0),
                            'last_heartbeat': conn_stats.get('last_heartbeat').strftime('%H:%M:%S') if conn_stats.get('last_heartbeat') else 'N/A',
                            'heartbeat_age_seconds': conn_stats.get('heartbeat_age_seconds'),
                            'connection_health': conn_stats.get('connection_health', 'unknown'),
                            'retry_stats': conn_stats.get('retry_stats', {})
                        }
                    except Exception as e:
                        self.logger.debug(f"获取xtquant连接统计失败: {e}")

                report['sources'][name] = source_report

            return report

    def _send_notification(self, usage: str, old_source: str, new_source: str, reason: str):
        """
        发送切换通知

        Args:
            usage: 用途类型
            old_source: 原数据源
            new_source: 新数据源
            reason: 切换原因
        """
        message = (
            f"⚠️ 数据源切换通知\n"
            f"用途: {usage}\n"
            f"原数据源: {old_source}\n"
            f"新数据源: {new_source}\n"
            f"切换原因: {reason}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.logger.info(message)
        # TODO: 集成钉钉/邮件通知

    def force_switch(self, usage: str, target_source: str) -> bool:
        """
        强制切换数据源

        Args:
            usage: 用途类型
            target_source: 目标数据源名称

        Returns:
            切换是否成功
        """
        with self.lock:
            if target_source not in self.adapters:
                self.logger.error(f"目标数据源不存在: {target_source}")
                return False

            adapter = self.adapters[target_source]

            if usage not in adapter.config.get('use_for', []):
                self.logger.error(f"{target_source}不支持{usage}用途")
                return False

            old_source = self.active_sources.get(usage)
            self.active_sources[usage] = target_source

            self.logger.info(f"强制切换{usage}数据源: {old_source} -> {target_source}")

            # 记录切换历史
            self.switch_history.append({
                'time': datetime.now(),
                'usage': usage,
                'from': old_source,
                'to': target_source,
                'reason': '手动强制切换'
            })

            return True

    def __repr__(self):
        return f"<HealthManager: monitoring={self.is_running}, sources={len(self.adapters)}>"

"""
Mootdx数据源适配器

使用mootdx库获取通达信数据,主要用于K线和实时行情
"""

import threading
import time
from typing import Optional, Dict, Any
import pandas as pd
from mootdx.quotes import Quotes
from .base_adapter import DataSourceAdapter


class MootdxAdapter(DataSourceAdapter):
    """Mootdx数据源适配器"""

    # 频率映射: 统一格式 -> mootdx格式
    FREQ_MAP = {
        'd': 9,      # 日线
        'w': 5,      # 周线
        'm': 6,      # 月线
        '1': 8,      # 1分钟
        '1m': 8,     # 1分钟(兼容)
        '5': 0,      # 5分钟
        '5m': 0,     # 5分钟(兼容)
        '15': 1,     # 15分钟
        '15m': 1,    # 15分钟(兼容)
        '30': 2,     # 30分钟
        '30m': 2,    # 30分钟(兼容)
        '60': 3,     # 60分钟
        '60m': 3     # 60分钟(兼容)
    }

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client = None
        self.timeout = config.get('timeout', 5)
        self.server_cooldown = config.get('server_cooldown_seconds', 600)
        self.probe_symbols = config.get(
            'probe_symbols', ['000001', '510300']
        )
        self.max_server_candidates = config.get('max_server_candidates', 1)
        self._lock = threading.RLock()
        self._servers = []
        self._server_index = -1
        self._server_cooldown_until = {}
        self._auto_discovery_attempted = False

    @staticmethod
    def _normalize_server(server):
        if isinstance(server, (list, tuple)) and len(server) >= 2:
            return str(server[-2]), int(server[-1])
        return None

    def _discover_servers(self):
        """获取可用行情节点，配置节点优先，自动探测作为补充。"""
        if self._servers:
            return self._servers

        candidates = []
        configured = self.config.get('servers', [])
        single = self.config.get('server')
        if single:
            configured = [single] + list(configured)
        for item in configured:
            server = self._normalize_server(item)
            if server and server not in candidates:
                candidates.append(server)

        if not candidates:
            try:
                from mootdx import config as mootdx_config
                cached = self._normalize_server(
                    mootdx_config.get('BESTIP').get('HQ')
                )
                if cached:
                    candidates.append(cached)
            except Exception as e:
                self.logger.debug(f"{self.name} 读取缓存节点失败: {e}")

        # 正常路径优先使用显式配置节点或业务验证后缓存的 BESTIP。
        self._servers = candidates or [None]
        return self._servers

    def _discover_remote_servers(self):
        """仅在现有节点真实取数失败后执行一次公网节点探测。"""
        if self._auto_discovery_attempted:
            return False
        self._auto_discovery_attempted = True
        discovered = []
        try:
            from mootdx import config as mootdx_config
            items = [mootdx_config.get('BESTIP').get('HQ')]
            items.extend(
                mootdx_config.get('SERVER').get('HQ', [])[
                    :self.max_server_candidates
                ]
            )
            for item in items:
                server = self._normalize_server(item)
                if server and server not in self._servers:
                    discovered.append(server)
                    if len(discovered) >= self.max_server_candidates:
                        break
        except Exception as e:
            self.logger.debug(f"{self.name} 读取备用行情节点失败: {e}")
        if discovered:
            self._servers.extend(discovered)
            return True
        return False

    def _close_client(self):
        client, self.client = self.client, None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        self.is_connected = False

    def _probe_client(self, client) -> bool:
        """用多个市场标的验证节点是否真的能返回行情。"""
        for symbol in self.probe_symbols:
            try:
                df = client.bars(
                    symbol=self.normalize_code(symbol),
                    frequency=self.FREQ_MAP['d'],
                    offset=5,
                    adjust='qfq',
                )
                if df is not None and not df.empty:
                    return True
            except Exception:
                continue
        return False

    def _connect_from(self, start_index=0) -> bool:
        servers = self._discover_servers()
        now = time.monotonic()
        for step in range(len(servers)):
            index = (start_index + step) % len(servers)
            server = servers[index]
            if self._server_cooldown_until.get(server, 0) > now:
                continue
            try:
                client = Quotes.factory(
                    market='std',
                    server=server,
                    timeout=self.timeout,
                    auto_retry=True,
                    raise_exception=True,
                )
                if not self._probe_client(client):
                    try:
                        client.close()
                    except Exception:
                        pass
                    self._server_cooldown_until[server] = (
                        time.monotonic() + self.server_cooldown
                    )
                    continue
                self.client = client
                self._server_index = index
                self.is_connected = True
                self.last_error = None
                self.logger.info(
                    f"{self.name} 连接成功，节点: "
                    f"{getattr(client, 'server', server)}"
                )
                return True
            except Exception as e:
                self.last_error = str(e)
                self._server_cooldown_until[server] = (
                    time.monotonic() + self.server_cooldown
                )
        old_count = len(servers)
        if self._discover_remote_servers():
            return self._connect_from(old_count)
        self._close_client()
        return False

    def connect(self) -> bool:
        """连接并验证 Mootdx 数据源。"""
        with self._lock:
            if self.client is not None and self._probe_client(self.client):
                self.is_connected = True
                return True
            start = self._server_index + 1 if self._server_index >= 0 else 0
            self._close_client()
            ok = self._connect_from(start)
            if not ok:
                self.logger.error(
                    f"{self.name} 连接失败: 所有行情节点均无法返回测试数据"
                )
            return ok

    def disconnect(self):
        """断开连接"""
        with self._lock:
            self._close_client()
            self.logger.info(f"{self.name} 已断开连接")

    def _recover_connection(self) -> bool:
        """将当前节点置于冷却期并切换到下一个节点。"""
        servers = self._discover_servers()
        if 0 <= self._server_index < len(servers):
            current = servers[self._server_index]
            self._server_cooldown_until[current] = (
                time.monotonic() + self.server_cooldown
            )
        start = self._server_index + 1 if self._server_index >= 0 else 0
        self._close_client()
        return self._connect_from(start)

    def _bars_once(self, code, frequency, count, adjust):
        return self.client.bars(
            symbol=code,
            frequency=frequency,
            offset=count,
            adjust=adjust,
        )

    def get_kline(
        self,
        code: str,
        freq: str = 'd',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
        adjust: str = 'qfq'
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据

        Args:
            code: 股票代码
            freq: 频率
            start_date: 开始日期(mootdx不支持日期范围,此参数用于后过滤)
            end_date: 结束日期(mootdx不支持日期范围,此参数用于后过滤)
            count: 获取数量(offset参数)
            adjust: 复权类型 'qfq'=前复权, 'hfq'=后复权, None=不复权

        Returns:
            DataFrame
        """
        with self._lock:
            if not self.is_connected and not self.connect():
                return None
            try:
                code = self.normalize_code(code)
                if freq not in self.FREQ_MAP:
                    self.logger.error(f"不支持的频率: {freq}")
                    return None
                mootdx_freq = self.FREQ_MAP[freq]
                count = count or 800
                df = self._bars_once(code, mootdx_freq, count, adjust)
                if df is None or df.empty:
                    # 标的无数据可能是正常情况；仅当节点探针也失败时切换节点。
                    if self._probe_client(self.client):
                        self.logger.debug(f"Mootdx标的无数据: {code}")
                        return None
                    if not self._recover_connection():
                        self.logger.warning(f"Mootdx节点不可用: {code}")
                        return None
                    df = self._bars_once(code, mootdx_freq, count, adjust)
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                if not self._recover_connection():
                    self.logger.error(f"Mootdx获取K线失败 {code}: {e}")
                    return None
                try:
                    df = self._bars_once(code, mootdx_freq, count, adjust)
                except Exception as retry_error:
                    self.last_error = str(retry_error)
                    self.logger.error(
                        f"Mootdx切换节点后仍无法获取K线 {code}: {retry_error}"
                    )
                    return None

        try:
            # 标准化代码
            if df is None or df.empty:
                self.logger.warning(f"Mootdx未获取到数据: {code}")
                return None

            # 修复mootdx重复列问题: 原始数据包含'vol'和'volume'两列
            # 删除'vol'列,保留'volume'列(因为它是复权后的成交量)
            if 'vol' in df.columns and 'volume' in df.columns:
                df = df.drop(columns=['vol'])
                self.logger.debug("删除重复的vol列,保留复权后的volume列")

            # 标准化列名
            df = self.standardize_dataframe(df)

            # 统一成交量单位为"股" (mootdx返回的是手,需要*100)
            if 'volume' in df.columns:
                df['volume'] = df['volume'] * 100
                self.logger.debug(f"成交量单位转换: 手 -> 股 (*100)")

            # 日期过滤(如果提供了日期范围)
            if start_date:
                df = df[df['date'] >= start_date]
            if end_date:
                df = df[df['date'] <= end_date]

            # 确保必要列存在
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                self.logger.error(f"数据列不完整: {df.columns.tolist()}")
                return None

            # 复权因子统一化处理(修复mootdx部分复权问题)
            if adjust in ['qfq', 'hfq'] and 'factor' in df.columns:
                # 前复权(qfq):以最新日期为基准(最新的factor),历史数据按factor调整
                # 找到最新交易日的factor(DataFrame末尾,时间最新)
                latest_factor = df['factor'].iloc[-1] if len(df) > 0 else 1.0

                # 如果存在factor变化,需要统一化
                if df['factor'].nunique() > 1:
                    # 前复权公式: 调整后价格 = 原价格 × (最新factor / 历史factor)
                    # 这样可以消除除权除息导致的价格跳跃
                    price_cols = ['open', 'high', 'low', 'close']
                    for col in price_cols:
                        if col in df.columns:
                            # 关键修复:历史数据(factor>latest_factor的)需要向下调整
                            # 最新数据(factor=latest_factor的)保持不变
                            df[col] = df[col] * (latest_factor / df['factor'])

                    self.logger.info(
                        f"复权因子统一化: {code}, "
                        f"factor范围 {df['factor'].min():.6f}-{df['factor'].max():.6f}, "
                        f"以最新factor {latest_factor:.6f}为基准"
                    )

            # 清理NaN值
            df = df.dropna(subset=['close'])  # 至少close不能为空

            if df.empty:
                self.logger.warning(f"Mootdx数据清理后为空: {code}")
                return None

            return df

        except Exception as e:
            self.logger.error(f"Mootdx获取K线失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_valuation(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取估值数据

        注意: Mootdx不提供估值数据,返回None
        """
        self.logger.warning(f"Mootdx不支持估值数据获取")
        return None

    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        Args:
            code: 股票代码

        Returns:
            实时行情字典
        """
        with self._lock:
            if not self.is_connected and not self.connect():
                return None
            code = self.normalize_code(code)
            try:
                quotes = self.client.quotes([code])
                if quotes is None or len(quotes) == 0:
                    if self._probe_client(self.client):
                        return None
                    if not self._recover_connection():
                        return None
                    quotes = self.client.quotes([code])
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                if not self._recover_connection():
                    return None
                try:
                    quotes = self.client.quotes([code])
                except Exception as retry_error:
                    self.last_error = str(retry_error)
                    return None

        try:
            # 处理DataFrame或列表返回
            if isinstance(quotes, pd.DataFrame):
                if quotes.empty:
                    self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                    return None
                quote = quotes.iloc[0].to_dict()
            elif isinstance(quotes, list):
                if not quotes or len(quotes) == 0:
                    self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                    return None
                quote = quotes[0] if isinstance(quotes[0], dict) else quotes[0].to_dict()
            else:
                self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                return None

            # 转换为统一格式
            tick_data = {
                'code': code,
                'name': quote.get('name', ''),
                'open': quote.get('open', 0),
                'high': quote.get('high', 0),
                'low': quote.get('low', 0),
                'close': quote.get('close', 0),
                'last': quote.get('price', 0),
                'volume': quote.get('vol', 0),
                'amount': quote.get('amount', 0),
                'bid': quote.get('bid1', 0),
                'ask': quote.get('ask1', 0),
                'yesterday_close': quote.get('last_close', 0)
            }

            return tick_data

        except Exception as e:
            self.logger.error(f"Mootdx获取tick失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def health_check(self) -> Dict[str, Any]:
        """直接探测 Mootdx 节点，不复用业务缓存。"""
        started = time.monotonic()
        result = {
            'status': 'ok',
            'response_time': 0.0,
            'data_freshness': True,
            'error_message': None,
        }
        with self._lock:
            healthy = (
                self.client is not None
                and self.is_connected
                and self._probe_client(self.client)
            )
            if not healthy:
                healthy = self._recover_connection()
        result['response_time'] = time.monotonic() - started
        if not healthy:
            result['status'] = 'error'
            result['error_message'] = '所有行情节点均无法返回测试数据'
            return result
        if result['response_time'] > self.config.get('timeout', 5):
            result['status'] = 'warning'
            result['error_message'] = (
                f'响应时间过长: {result["response_time"]:.2f}秒'
            )
        return result

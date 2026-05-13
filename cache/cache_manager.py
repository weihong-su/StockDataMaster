"""
SQLite缓存管理器

提供日K线数据的智能缓存功能,支持双源校验和平滑切换
"""

import sqlite3
import numpy as np
import pandas as pd
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, time
import threading


# validated=1 且具备真实第二数据源（不是 NULL/''/'none'）才算双源校验通过。
# 仅 validated=1 但 source2 为空/none 的行被视为"未通过双源校验"——历史上 xtquant
# 单源缓存与某些早期路径会落入这种状态，下次读取需当作未命中。
_DUAL_SOURCE_VALIDATED_SQL = (
    "validated=1 "
    "AND source2 IS NOT NULL AND source2<>'' AND source2<>'none'"
)


class CacheManager:
    """缓存管理器"""

    def __init__(self, config, adapters: Dict):
        """
        初始化缓存管理器

        Args:
            config: 配置对象
            adapters: 适配器字典
        """
        self.config = config
        self.adapters = adapters
        self.logger = logging.getLogger("DataMaster.CacheManager")

        # 缓存配置
        self.enabled = config.is_cache_enabled()
        self.db_path = config.get('cache.db_path', 'cache/kline_cache.db')
        self.max_days = config.get_cache_max_days()
        self.stock_name_expire_days = config.get('cache.stock_name_expire_days', 30)  # 股票名称缓存过期天数(默认30天)
        self.stock_name_cleanup_day = config.get('cache.stock_name_cleanup_day', 0)  # 清理日(0=周一,1=周二,...,6=周日,默认周一)
        self.stock_name_skip_expiration_check = config.get('cache.stock_name_skip_expiration_check', True)  # 跳过过期检查以提升性能

        # 校验容忍度
        self.price_tolerance_abs = config.get('cache.validation.price_tolerance_abs', 0.01)
        self.price_tolerance_pct = config.get('cache.validation.price_tolerance_pct', 0.005)
        self.volume_tolerance_pct = config.get('cache.validation.volume_tolerance_pct', 0.05)
        self.return_tolerance = config.get('cache.validation.return_tolerance', 0.005)
        self.ratio_tolerance = config.get('cache.validation.ratio_tolerance', 0.005)
        self.min_pass_rate = config.get('cache.validation.min_pass_rate',
                             config.get('validation.min_pass_rate', 0.8))

        # 线程锁
        self.lock = threading.Lock()

        # 上次清理时间(用于控制清理频率)
        self.last_cleanup_date = None

        # 初始化数据库
        if self.enabled:
            self._init_database()
            self._auto_cleanup_on_startup()  # 启动时检查是否需要清理

    def _init_database(self):
        """初始化SQLite数据库"""
        try:
            # 确保目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # 创建表
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # K线缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kline_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    turn REAL,
                    source1 TEXT,
                    source2 TEXT,
                    validated INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(code, date)
                )
            ''')

            # 🔥 新增: 股票名称缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_name_cache (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_date ON kline_cache(code, date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated ON kline_cache(validated)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_name ON stock_name_cache(code)')

            # 自动迁移：为旧表补充 turn 列（换手率）
            try:
                cursor.execute("ALTER TABLE kline_cache ADD COLUMN turn REAL")
            except Exception:
                pass  # 列已存在，忽略

            conn.commit()
            conn.close()

            self.logger.info(f"缓存数据库初始化成功: {self.db_path}")

        except Exception as e:
            self.logger.error(f"缓存数据库初始化失败: {e}")
            self.enabled = False

    def _auto_cleanup_on_startup(self):
        """
        启动时自动检查并执行清理
        策略: 只在配置的清理日(默认周一)或距离上次清理超过7天时执行
        """
        if not self.enabled:
            return

        today = datetime.now()
        weekday = today.weekday()  # 0=周一, 1=周二, ..., 6=周日

        # 检查是否是清理日
        if weekday == self.stock_name_cleanup_day:
            # 检查今天是否已经清理过
            if self.last_cleanup_date != today.date():
                self.logger.info(f"今天是清理日(周{weekday+1}),执行股票名称缓存清理")
                cleaned_count = self.clean_expired_stock_names()
                if cleaned_count > 0:
                    self.logger.info(f"自动清理完成: {cleaned_count}条过期记录")
                self.last_cleanup_date = today.date()
        else:
            self.logger.debug(f"今天不是清理日(周{weekday+1}),跳过自动清理")


    def get_cached_kline(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        从缓存获取K线数据

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            count: 获取数量

        Returns:
            DataFrame或None
        """
        if not self.enabled:
            return None

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)

                # 构建查询：仅返回经过双源校验的行
                # validated=1 但 source2='none' 的"伪双源"数据视为未命中
                query = (
                    "SELECT date,open,high,low,close,volume,amount,turn "
                    "FROM kline_cache WHERE code=? AND "
                    + _DUAL_SOURCE_VALIDATED_SQL
                )
                params = [code]

                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date)

                # 🔥 关键修复: 使用count时,需要从最新数据开始取
                # 先降序排列取最新N条,然后在Python中反转为升序
                if count:
                    query += " ORDER BY date DESC"
                    query += f" LIMIT {count}"
                else:
                    query += " ORDER BY date"

                # 执行查询
                df = pd.read_sql_query(query, conn, params=params)
                conn.close()

                if df.empty:
                    return None

                # 🔥 如果使用了count参数,需要反转数据顺序(从降序变回升序)
                if count and len(df) > 0:
                    df = df.iloc[::-1].reset_index(drop=True)

                # 设置数据来源为缓存
                df.attrs['source'] = 'cache'

                return df

        except Exception as e:
            self.logger.error(f"从缓存获取数据失败 {code}: {e}")
            return None

    def save_to_cache(
        self,
        code: str,
        df: pd.DataFrame,
        source1: str,
        source2: Optional[str] = None,
        validated: bool = False
    ) -> bool:
        """
        保存数据到缓存

        Args:
            code: 股票代码
            df: K线数据
            source1: 主数据源
            source2: 校验数据源
            validated: 是否已校验

        Returns:
            是否保存成功
        """
        if not self.enabled or df is None or df.empty:
            return False

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                now = datetime.now()
                now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                today_str = now.strftime('%Y-%m-%d')

                # 市场收盘时间 15:00
                market_close_time = time(15, 0)
                can_cache_today = now.time() >= market_close_time

                # 统计跳过的当日数据
                skipped_today_count = 0

                for _, row in df.iterrows():
                    row_date = str(row['date'])

                    # 🔥 智能缓存：盘中时段跳过当日数据
                    if row_date == today_str and not can_cache_today:
                        skipped_today_count += 1
                        self.logger.debug(f"盘中时段，跳过当日数据: {row_date} (当前时间: {now.strftime('%H:%M:%S')})")
                        continue

                    # 使用REPLACE实现更新或插入
                    cursor.execute('''
                        REPLACE INTO kline_cache (
                            code, date, open, high, low, close, volume, amount, turn,
                            source1, source2, validated, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        code,
                        row_date,
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        float(row['volume']),
                        float(row.get('amount', 0)),
                        float(row['turn']) if 'turn' in row.index and pd.notna(row.get('turn', None)) else None,
                        source1,
                        source2,
                        1 if validated else 0,
                        now_str,
                        now_str
                    ))

                conn.commit()
                conn.close()

                cached_count = len(df) - skipped_today_count
                if skipped_today_count > 0:
                    self.logger.info(f"数据已保存到缓存 {code}: {cached_count}条 (跳过盘中当日数据: {skipped_today_count}条)")
                else:
                    self.logger.debug(f"数据已保存到缓存 {code}: {cached_count}条")
                return True

        except Exception as e:
            self.logger.error(f"保存数据到缓存失败 {code}: {e}")
            return False

    def validate_and_cache(
        self,
        code: str,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        source1: str,
        source2: str
    ) -> Optional[pd.DataFrame]:
        """
        双源校验并缓存

        Args:
            code: 股票代码
            df1: 数据源1的数据
            df2: 数据源2的数据
            source1: 数据源1名称
            source2: 数据源2名称

        Returns:
            校验通过的DataFrame
        """
        if df1 is None or df1.empty:
            self.logger.warning(f"{source1}数据为空,无法校验")
            return None

        if df2 is None or df2.empty:
            self.logger.warning(f"{source2}数据为空,无法校验")
            # 如果只有一个数据源,直接返回(不校验)
            return df1

        try:
            # 无日期重叠时无法校验，直接返回 df1
            overlap = set(df1['date'].astype(str)) & set(df2['date'].astype(str))
            if not overlap:
                self.logger.warning(f"{source1}和{source2}没有重叠数据,无法校验")
                return df1

            # 用收益率通过率判断一致性（与投票路径对齐）
            # 前复权因子在日收益率中完全抵消，多次除权不影响判断
            pass_rate = self._calculate_pass_rate(df1, df2, code)

            if pass_rate >= self.min_pass_rate:
                # 通过：缓存完整主数据（df1），行数不因除权段差异而丢失
                validated_df = df1.copy()
                self.save_to_cache(code, validated_df, source1, source2, validated=True)
                self.logger.info(
                    f"{code}双源校验完成: {len(validated_df)}/{len(validated_df)}条通过"
                    f" (收益率通过率={pass_rate*100:.1f}%)"
                )
                return validated_df
            else:
                self.logger.warning(
                    f"{code}双源校验未通过: 收益率通过率={pass_rate*100:.1f}% < {self.min_pass_rate*100:.0f}%"
                )
                return None

        except Exception as e:
            self.logger.error(f"双源校验失败 {code}: {e}")
            return None

    def validate_and_cache_voting(
        self,
        code: str,
        primary_df: pd.DataFrame,
        validation_dfs: Dict[str, pd.DataFrame],
        primary_source: str
    ) -> Optional[pd.DataFrame]:
        """
        三选二投票校验并缓存

        Args:
            code: 股票代码
            primary_df: 主数据源 DataFrame
            validation_dfs: {源名: DataFrame} 校验源字典
            primary_source: 主数据源名称

        Returns:
            校验通过的 DataFrame
        """
        if primary_df is None or primary_df.empty:
            self.logger.warning(f"{primary_source}数据为空,无法校验")
            return None

        # 无校验源时直接返回主数据(不缓存)
        if not validation_dfs:
            self.logger.info(f"{code}无校验源可用,返回未校验数据")
            return primary_df

        # 只有一个校验源时,降级为双源校验
        if len(validation_dfs) == 1:
            vs_name = list(validation_dfs.keys())[0]
            vs_df = validation_dfs[vs_name]
            return self.validate_and_cache(code, primary_df, vs_df, primary_source, vs_name)

        # 多个校验源: 三选二投票
        quorum = 2  # 需要2票通过
        votes_passed = []

        for vs_name, vs_df in validation_dfs.items():
            if vs_df is None or vs_df.empty:
                self.logger.debug(f"{vs_name}校验数据为空,跳过")
                continue

            # 使用现有的比对逻辑计算通过率
            pass_rate = self._calculate_pass_rate(primary_df, vs_df, code)

            if pass_rate >= 0.8:
                votes_passed.append(vs_name)
                self.logger.debug(f"{code} {vs_name}校验通过(通过率={pass_rate*100:.1f}%)")

                if len(votes_passed) >= quorum:
                    # 达到法定票数,使用主数据缓存
                    validated_df = primary_df.copy()
                    self.save_to_cache(
                        code, validated_df, primary_source,
                        ','.join(votes_passed[:quorum]),
                        validated=True
                    )
                    self.logger.info(
                        f"{code}投票校验通过: {votes_passed[:quorum]} "
                        f"({len(validated_df)}条)"
                    )
                    return validated_df
            else:
                self.logger.debug(f"{code} {vs_name}校验未通过(通过率={pass_rate*100:.1f}%)")

        # 未达到法定票数
        self.logger.warning(
            f"{code}投票校验未达标: {len(votes_passed)}/{quorum}票 "
            f"(通过源: {votes_passed})"
        )
        return None

    def _calculate_pass_rate(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        code: str
    ) -> float:
        """
        计算两个数据源的比对通过率（基于日收益率）

        前复权因子在日收益率计算中完全抵消，非除权日两源收益率精确相等。
        除权日（每年约 2-4 次）收益率会有差异，但占比 < 1.5%，不影响 80% 通过率阈值。

        Returns:
            通过率 (0.0-1.0)
        """
        try:
            # 各源独立排序并计算日收益率（close_t / close_{t-1} - 1）
            d1 = df1[['date', 'close', 'volume']].copy().sort_values('date').reset_index(drop=True)
            d2_tmp = df2[['date', 'close', 'volume']].copy()
            d2 = d2_tmp.loc[:, ~d2_tmp.columns.duplicated()].sort_values('date').reset_index(drop=True)

            d1['ret'] = d1['close'].pct_change()
            d2['ret'] = d2['close'].pct_change()

            # 丢弃每源首行（无前一日，NaN）
            d1 = d1.dropna(subset=['ret'])
            d2 = d2.dropna(subset=['ret'])

            merged = pd.merge(
                d1[['date', 'ret', 'volume']],
                d2[['date', 'ret', 'volume']],
                on='date', suffixes=('_1', '_2'), how='inner'
            )
            if merged.empty:
                return 0.0

            passed = 0
            for _, row in merged.iterrows():
                # 收益率差异：非除权日应 < 0.01%（浮点精度范围内）
                if abs(float(row['ret_1']) - float(row['ret_2'])) > self.return_tolerance:
                    continue
                # 成交量：与前复权无关，直接比较
                v1, v2 = float(row['volume_1']), float(row['volume_2'])
                if max(v1, v2) > 0 and abs(v1 - v2) / max(v1, v2) > self.volume_tolerance_pct:
                    continue
                passed += 1

            return passed / len(merged) if len(merged) > 0 else 0.0

        except Exception as e:
            self.logger.error(f"计算通过率失败 {code}: {e}")
            return 0.0

    def get_validated_dates(self, code: str) -> set:
        """
        获取某只股票已通过校验的缓存日期集合

        Args:
            code: 股票代码

        Returns:
            已验证日期的set，如 {'2024-01-02', '2024-01-03', ...}
        """
        if not self.enabled:
            return set()

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT date FROM kline_cache WHERE code=? AND "
                    + _DUAL_SOURCE_VALIDATED_SQL,
                    (code,)
                )
                dates = {row[0] for row in cursor.fetchall()}
                conn.close()
                return dates
        except Exception as e:
            self.logger.error(f"获取已验证日期失败 {code}: {e}")
            return set()

    def cleanup_old_cache(self, days: Optional[int] = None):
        """
        清理超过指定天数的旧缓存

        Args:
            days: 保留天数,默认使用max_days配置
        """
        if not self.enabled:
            return

        days = days or self.max_days

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # 计算截止日期
                cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

                # 删除旧数据
                cursor.execute('DELETE FROM kline_cache WHERE date < ?', (cutoff_date,))

                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()

                if deleted_count > 0:
                    self.logger.info(f"清理缓存完成,删除{deleted_count}条旧数据(早于{cutoff_date})")

        except Exception as e:
            self.logger.error(f"清理缓存失败: {e}")

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        if not self.enabled:
            return {'enabled': False}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 总记录数
            cursor.execute('SELECT COUNT(*) FROM kline_cache')
            total_count = cursor.fetchone()[0]

            # 已通过双源校验的行（与 get_cached_kline 读取标准对齐）
            cursor.execute(
                'SELECT COUNT(*) FROM kline_cache WHERE ' + _DUAL_SOURCE_VALIDATED_SQL
            )
            dual_source_count = cursor.fetchone()[0]

            # 单源缓存：validated=1 但 source2 缺失（历史脏数据或 xtquant 单源），
            # 与 validated=0 的真"待校验"分开统计，方便监控清洗效果
            cursor.execute(
                "SELECT COUNT(*) FROM kline_cache WHERE validated=1 "
                "AND (source2 IS NULL OR source2='' OR source2='none')"
            )
            single_source_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM kline_cache WHERE validated=0')
            unvalidated_count = cursor.fetchone()[0]

            # 股票数量
            cursor.execute('SELECT COUNT(DISTINCT code) FROM kline_cache')
            stock_count = cursor.fetchone()[0]

            # 数据日期范围
            cursor.execute('SELECT MIN(date), MAX(date) FROM kline_cache')
            date_range = cursor.fetchone()

            # 数据库文件大小
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            conn.close()

            return {
                'enabled': True,
                'total_records': total_count,
                # 保留旧字段名向后兼容，但语义已收紧为"双源校验通过的行数"
                'validated_records': dual_source_count,
                'dual_source_records': dual_source_count,
                'single_source_records': single_source_count,
                'unvalidated_records': unvalidated_count,
                'stock_count': stock_count,
                'date_range': {
                    'start': date_range[0],
                    'end': date_range[1]
                },
                'db_size_mb': round(db_size / 1024 / 1024, 2),
                'db_path': self.db_path
            }

        except Exception as e:
            self.logger.error(f"获取缓存统计失败: {e}")
            return {'enabled': True, 'error': str(e)}

    # ==================== 股票名称缓存方法 ====================

    def get_cached_stock_name(self, code: str) -> Optional[str]:
        """
        从缓存获取股票名称(已优化:周六清理时删除过期记录)

        策略:
        - 周六清理时已删除过期记录,缓存中只保留有效数据
        - 查询时直接返回缓存,无需时间比对,性能最优
        - 缓存不存在则返回None,触发从baostock获取最新数据

        Args:
            code: 股票代码

        Returns:
            股票名称,未找到返回None
        """
        if not self.enabled:
            return None

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # 仅查询name字段(优化:不需要updated_at,清理时已删除过期数据)
                cursor.execute(
                    'SELECT name FROM stock_name_cache WHERE code = ?',
                    (code,)
                )

                result = cursor.fetchone()
                conn.close()

                if result:
                    name = result[0]
                    self.logger.debug(f"股票名称缓存命中: {code} -> {name}")
                    return name

                return None  # 缓存不存在,返回None触发baostock查询

        except Exception as e:
            self.logger.error(f"获取股票名称缓存失败: {e}")
            return None

    def cache_stock_name(self, code: str, name: str, source: str = 'baostock') -> bool:
        """
        缓存股票名称到数据库

        Args:
            code: 股票代码
            name: 股票名称
            source: 数据来源

        Returns:
            是否成功
        """
        if not self.enabled:
            return False

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 使用 INSERT OR REPLACE 自动处理重复
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_name_cache
                    (code, name, source, created_at, updated_at)
                    VALUES (?, ?, ?,
                        COALESCE((SELECT created_at FROM stock_name_cache WHERE code = ?), ?),
                        ?)
                ''', (code, name, source, code, now, now))

                conn.commit()
                conn.close()

                self.logger.debug(f"股票名称已缓存: {code} -> {name}")
                return True

        except Exception as e:
            self.logger.error(f"缓存股票名称失败: {e}")
            return False

    def bulk_cache_stock_names(self, names: dict, source: str = 'tushare') -> int:
        """
        批量缓存股票名称（单事务写入）

        Args:
            names: {code: name} 字典
            source: 数据来源

        Returns:
            成功写入数量
        """
        if not self.enabled or not names:
            return 0

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data = [(code, name, source, code, now, now)
                        for code, name in names.items()]

                cursor.executemany('''
                    INSERT OR REPLACE INTO stock_name_cache
                    (code, name, source, created_at, updated_at)
                    VALUES (?, ?, ?,
                        COALESCE((SELECT created_at FROM stock_name_cache WHERE code = ?), ?),
                        ?)
                ''', data)

                conn.commit()
                conn.close()

                self.logger.info(f"批量缓存股票名称: {len(data)} 只 (来源: {source})")
                return len(data)

        except Exception as e:
            self.logger.error(f"批量缓存股票名称失败: {e}")
            return 0

    def get_stock_name_cache_count(self) -> int:
        """获取股票名称缓存数量"""
        if not self.enabled:
            return 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM stock_name_cache')
            count = cursor.fetchone()[0]

            conn.close()
            return count

        except Exception as e:
            self.logger.error(f"获取股票名称缓存数量失败: {e}")
            return 0

    def clean_expired_stock_names(self) -> int:
        """
        清理过期的股票名称缓存

        Returns:
            清理的数量
        """
        if not self.enabled:
            return 0

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # 计算过期时间点
                expire_date = (datetime.now() - timedelta(days=self.stock_name_expire_days)).strftime('%Y-%m-%d %H:%M:%S')

                # 查询过期记录数
                cursor.execute(
                    'SELECT COUNT(*) FROM stock_name_cache WHERE updated_at < ?',
                    (expire_date,)
                )
                count = cursor.fetchone()[0]

                if count > 0:
                    # 删除过期记录
                    cursor.execute(
                        'DELETE FROM stock_name_cache WHERE updated_at < ?',
                        (expire_date,)
                    )
                    conn.commit()
                    self.logger.info(f"清理过期股票名称缓存: {count}条 (过期时间: {expire_date})")

                conn.close()
                return count

        except Exception as e:
            self.logger.error(f"清理过期股票名称缓存失败: {e}")
            return 0

    def get_stock_name_cache_stats(self) -> Dict[str, Any]:
        """
        获取股票名称缓存统计信息

        Returns:
            统计信息字典
        """
        if not self.enabled:
            return {'enabled': False}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 总数量
            cursor.execute('SELECT COUNT(*) FROM stock_name_cache')
            total_count = cursor.fetchone()[0]

            # 过期数量
            expire_date = (datetime.now() - timedelta(days=self.stock_name_expire_days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'SELECT COUNT(*) FROM stock_name_cache WHERE updated_at < ?',
                (expire_date,)
            )
            expired_count = cursor.fetchone()[0]

            # 有效数量
            valid_count = total_count - expired_count

            # 最早和最新更新时间
            cursor.execute('SELECT MIN(updated_at), MAX(updated_at) FROM stock_name_cache')
            min_time, max_time = cursor.fetchone()

            conn.close()

            return {
                'enabled': True,
                'total_count': total_count,
                'valid_count': valid_count,
                'expired_count': expired_count,
                'expire_days': self.stock_name_expire_days,
                'oldest_update': min_time,
                'newest_update': max_time
            }

        except Exception as e:
            self.logger.error(f"获取股票名称缓存统计失败: {e}")
            return {'enabled': True, 'error': str(e)}

    def __repr__(self):
        return f"<CacheManager: enabled={self.enabled}, max_days={self.max_days}, stock_name_expire_days={self.stock_name_expire_days}>"

"""
SQLite缓存管理器

提供日K线数据的智能缓存功能,支持双源校验和平滑切换
"""

import sqlite3
import pandas as pd
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, time
import threading


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

        # 校验容忍度
        self.price_tolerance_abs = config.get('cache.validation.price_tolerance_abs', 0.01)
        self.price_tolerance_pct = config.get('cache.validation.price_tolerance_pct', 0.005)
        self.volume_tolerance_pct = config.get('cache.validation.volume_tolerance_pct', 0.05)

        # 线程锁
        self.lock = threading.Lock()

        # 初始化数据库
        if self.enabled:
            self._init_database()

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
                    source1 TEXT,
                    source2 TEXT,
                    validated INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(code, date)
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_date ON kline_cache(code, date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated ON kline_cache(validated)')

            conn.commit()
            conn.close()

            self.logger.info(f"缓存数据库初始化成功: {self.db_path}")

        except Exception as e:
            self.logger.error(f"缓存数据库初始化失败: {e}")
            self.enabled = False

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

                # 构建查询
                query = "SELECT date,open,high,low,close,volume,amount FROM kline_cache WHERE code=? AND validated=1"
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
                            code, date, open, high, low, close, volume, amount,
                            source1, source2, validated, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        code,
                        row_date,
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        float(row['volume']),
                        float(row.get('amount', 0)),
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
            # 准备df1数据(确保包含必要列)
            df1_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            has_amount = 'amount' in df1.columns
            if has_amount:
                df1_cols.append('amount')

            df1_clean = df1[df1_cols].copy()

            # 准备df2数据(只需要价格和成交量列,删除重复列)
            df2_temp = df2[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            # 删除重复列名(Mootdx有重复的volume列)
            df2_clean = df2_temp.loc[:, ~df2_temp.columns.duplicated()]

            # 合并两个数据源(按日期)
            merged = pd.merge(
                df1_clean,
                df2_clean,
                on='date',
                suffixes=('_1', '_2'),
                how='inner'
            )

            if merged.empty:
                self.logger.warning(f"{source1}和{source2}没有重叠数据,无法校验")
                return df1

            # 校验每一行
            validated_rows = []

            for _, row in merged.iterrows():
                # 价格字段校验
                price_valid = True
                for field in ['open', 'high', 'low', 'close']:
                    price1 = float(row[f'{field}_1'])
                    price2 = float(row[f'{field}_2'])

                    # 绝对差异
                    abs_diff = abs(price1 - price2)
                    # 相对差异
                    pct_diff = abs_diff / max(price1, price2) if max(price1, price2) > 0 else 0

                    # 使用Python原生bool判断,避免Series ambiguous错误
                    if bool(abs_diff > self.price_tolerance_abs and pct_diff > self.price_tolerance_pct):
                        self.logger.warning(
                            f"{code} {row['date']} {field}价格差异过大: {price1} vs {price2}"
                        )
                        price_valid = False
                        break

                if not price_valid:
                    continue

                # 成交量校验
                vol1 = float(row['volume_1'])
                vol2 = float(row['volume_2'])
                vol_diff = abs(vol1 - vol2) / max(vol1, vol2) if max(vol1, vol2) > 0 else 0

                # 使用Python原生bool判断
                if bool(vol_diff > self.volume_tolerance_pct):
                    self.logger.warning(
                        f"{code} {row['date']} 成交量差异过大: {vol1} vs {vol2}"
                    )
                    continue

                # 校验通过,使用数据源1的数据
                # amount列处理: 如果df2没有amount列,合并后amount列不会有后缀
                amount_value = 0.0
                if has_amount:
                    if 'amount_1' in merged.columns:
                        amount_value = float(row['amount_1'])
                    elif 'amount' in merged.columns:
                        amount_value = float(row['amount'])

                validated_rows.append({
                    'date': str(row['date']),
                    'open': float(row['open_1']),
                    'high': float(row['high_1']),
                    'low': float(row['low_1']),
                    'close': float(row['close_1']),
                    'volume': float(row['volume_1']),
                    'amount': amount_value
                })

            if not validated_rows:
                self.logger.warning(f"{code}所有数据均未通过双源校验")
                return None

            validated_df = pd.DataFrame(validated_rows)

            # 保存到缓存
            self.save_to_cache(code, validated_df, source1, source2, validated=True)

            self.logger.info(
                f"{code}双源校验完成: {len(validated_df)}/{len(merged)}条通过"
            )

            return validated_df

        except Exception as e:
            self.logger.error(f"双源校验失败 {code}: {e}")
            return None

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

            # 已校验记录数
            cursor.execute('SELECT COUNT(*) FROM kline_cache WHERE validated=1')
            validated_count = cursor.fetchone()[0]

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
                'validated_records': validated_count,
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

    def __repr__(self):
        return f"<CacheManager: enabled={self.enabled}, max_days={self.max_days}>"

# coding: utf-8
"""
DuckDB数据库管理模块
用于存储和管理行情数据、合约信息等
"""
import os
import threading
from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal


class DatabaseManager:
    """DuckDB数据库管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """单例模式：确保全局只有一个数据库实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认为 ~/.miniqt/miniqt.duckdb
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        if db_path is None:
            # 默认数据库路径
            home_dir = os.path.expanduser("~")
            miniqt_dir = os.path.join(home_dir, ".miniqt")
            os.makedirs(miniqt_dir, exist_ok=True)
            db_path = os.path.join(miniqt_dir, "miniqt.duckdb")

        self.db_path = db_path
        self.connection = None
        self._initialized = True
        self._connect()

    def _connect(self):
        """连接到DuckDB数据库"""
        try:
            import duckdb
            self.connection = duckdb.connect(self.db_path)
            # print(f"[DatabaseManager] 已连接到数据库: {self.db_path}")
            self._init_tables()
        except ImportError:
            raise ImportError("请先安装DuckDB: pip install duckdb")
        except Exception as e:
            print(f"[DatabaseManager] 连接数据库失败: {e}")
            # 如果是WAL文件损坏，删除数据库文件和WAL文件
            if "WAL file" in str(e) or "replay" in str(e):
                print("[DatabaseManager] 检测到WAL文件损坏，删除数据库文件...")
                import os
                wal_file = self.db_path + ".wal"
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                    print(f"[DatabaseManager] 已删除数据库文件: {self.db_path}")
                if os.path.exists(wal_file):
                    os.remove(wal_file)
                    print(f"[DatabaseManager] 已删除WAL文件: {wal_file}")
                # 重新连接
                try:
                    self.connection = duckdb.connect(self.db_path)
                    print(f"[DatabaseManager] 已重新连接到数据库: {self.db_path}")
                    self._init_tables()
                except Exception as e2:
                    print(f"[DatabaseManager] 重新连接失败: {e2}")
                    raise
            else:
                raise

    def is_fresh_database(self) -> bool:
        """检查是否为全新数据库（首次创建或重建后）

        检查逻辑：
        1. fresh 标志为 'true'
        2. 且 symbol_info 表数据少于 100 条（防止旧数据库误判）
        """
        try:
            result = self.connection.execute(
                "SELECT value FROM database_meta WHERE key = 'fresh'"
            ).fetchone()
            if result is None or result[0] != 'true':
                return False

            # 额外检查：如果 symbol_info 表已有足够数据，则不再认为是全新数据库
            try:
                count_result = self.connection.execute(
                    "SELECT COUNT(*) FROM symbol_info"
                ).fetchone()
                if count_result is not None and count_result[0] >= 100:
                    # 已有数据，自动修正 fresh 标志
                    self.mark_database_populated()
                    return False
            except Exception:
                pass

            return True
        except Exception:
            return False
    
    def mark_database_populated(self):
        """标记数据库已完成全量填充"""
        try:
            self.connection.execute(
                "UPDATE database_meta SET value = 'false' WHERE key = 'fresh'"
            )
            #print("[DatabaseManager] 数据库全量填充完成，已设置 fresh=false")
        except Exception as e:
            print(f"[DatabaseManager] 标记数据库填充状态失败: {e}")

    def _init_tables(self):
        """初始化数据库表结构"""
        try:
            # 创建合约信息表
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS symbol_info (
                    instrument_id VARCHAR PRIMARY KEY,
                    instrument_name VARCHAR,
                    ins_class VARCHAR,
                    exchange_id VARCHAR,
                    product_id VARCHAR,
                    price_tick DOUBLE,
                    volume_multiple DOUBLE,
                    open_limit DOUBLE,
                    max_limit_order_volume INTEGER,
                    max_market_order_volume INTEGER,
                    min_limit_order_volume INTEGER,
                    min_market_order_volume INTEGER,
                    open_max_market_order_volume INTEGER,
                    open_max_limit_order_volume INTEGER,
                    open_min_market_order_volume INTEGER,
                    open_min_limit_order_volume INTEGER,
                    underlying_symbol VARCHAR,
                    strike_price DOUBLE,
                    expired BOOLEAN,
                    expire_datetime TIMESTAMP,
                    expire_rest_days INTEGER,
                    delivery_year INTEGER,
                    delivery_month INTEGER,
                    last_exercise_datetime TIMESTAMP,
                    exercise_year INTEGER,
                    exercise_month INTEGER,
                    option_class VARCHAR,
                    upper_limit DOUBLE,
                    lower_limit DOUBLE,
                    pre_settlement DOUBLE,
                    pre_open_interest DOUBLE,
                    pre_close DOUBLE,
                    trading_time_day VARCHAR,
                    trading_time_night VARCHAR,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 检查并添加缺失的列（用于数据库迁移）
            self._migrate_table()

            # 创建交易所合约列表表（用于存储主力合约列表）
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS exchange_symbols (
                    id INTEGER PRIMARY KEY,
                    ins_class VARCHAR,
                    exchange_id VARCHAR,
                    instrument_id VARCHAR,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ins_class, exchange_id, instrument_id)
                )
            """)

            # 创建合约类型映射表
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS ins_class_map (
                    ins_class_en VARCHAR PRIMARY KEY,
                    ins_class_cn VARCHAR,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建交易所映射表
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS exchange_id_map (
                    exchange_id_en VARCHAR PRIMARY KEY,
                    exchange_id_cn VARCHAR,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_info_exchange
                ON symbol_info(exchange_id, ins_class)
            """)

            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchange_symbols_class
                ON exchange_symbols(ins_class, exchange_id)
            """)

            # 创建合约搜索表（用于键盘精灵快速搜索）
            # 使用复合主键 (code, name, type)，不需要单独的 id 字段
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS symbol_search_table (
                    code VARCHAR,
                    name VARCHAR,
                    type VARCHAR,
                    exchange VARCHAR,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, name, type)
                )
            """)

            # 创建搜索表索引
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_search_code
                ON symbol_search_table(code)
            """)

            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_search_name
                ON symbol_search_table(name)
            """)
            # 创建数据库元信息表（存储 fresh 标志等）
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS database_meta (
                    key VARCHAR PRIMARY KEY,
                    value VARCHAR
                )
            """)

            # 检查是否为全新数据库（fresh 键不存在则判断）
            result = self.connection.execute(
                "SELECT value FROM database_meta WHERE key = 'fresh'"
            ).fetchone()
            if result is None:
                # 检查 symbol_info 表是否已有数据（判断是否为旧版本数据库升级）
                try:
                    symbol_count = self.connection.execute(
                        "SELECT COUNT(*) FROM symbol_info"
                    ).fetchone()
                    has_data = symbol_count is not None and symbol_count[0] > 0
                except Exception:
                    has_data = False

                # 有数据说明是旧数据库升级，设置 fresh=false；否则是全新数据库
                fresh_value = 'false' if has_data else 'true'
                self.connection.execute(
                    "INSERT INTO database_meta (key, value) VALUES ('fresh', ?)",
                    [fresh_value]
                )
                # if fresh_value == 'true':
                #     print("[DatabaseManager] 检测到全新数据库，已设置 fresh=true")
                # else:
                #     print("[DatabaseManager] 检测到旧版本数据库升级，已设置 fresh=false")

            # print("[DatabaseManager] 数据库表初始化完成")
        except Exception as e:
            print(f"[DatabaseManager] 初始化表失败: {e}")
            raise

        # 检查并修复搜索表结构，并从 symbol_info 表重建数据
        self._init_search_table()

    def _init_search_table(self):
        """初始化搜索表：检查结构并从 symbol_info 表重建数据"""
        try:
            # 检查搜索表是否存在
            result = self.connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'symbol_search_table'"
            ).fetchone()

            need_recreate = False

            if result[0] > 0:
                # 表存在，检查结构
                table_info = self.connection.execute("DESCRIBE symbol_search_table").fetchall()
                columns = [col[0] for col in table_info]

                # 检查是否有 id 字段（旧表结构），需要重建
                if 'id' in columns:
                    need_recreate = True
            else:
                # 表不存在，需要创建
                need_recreate = True

            if need_recreate:
                # 删除旧表（如果存在）
                try:
                    self.connection.execute("DROP TABLE IF EXISTS symbol_search_table")
                except:
                    pass

                # 创建新表（使用复合主键）
                self.connection.execute("""
                    CREATE TABLE symbol_search_table (
                        code VARCHAR,
                        name VARCHAR,
                        type VARCHAR,
                        exchange VARCHAR,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (code, name, type)
                    )
                """)

                # 创建索引
                self.connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_symbol_search_code
                    ON symbol_search_table(code)
                """)

                self.connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_symbol_search_name
                    ON symbol_search_table(name)
                """)

            # 从 symbol_info 表重建搜索表数据
            self._rebuild_search_table_from_symbol_info()

        except Exception as e:
            print(f"[DatabaseManager] 初始化搜索表失败: {e}")

    def _rebuild_search_table_from_symbol_info(self):
        """从 symbol_info 表重建搜索表数据"""
        try:
            # 检查 symbol_info 表是否有数据
            result = self.connection.execute("SELECT COUNT(*) FROM symbol_info").fetchone()
            if result[0] == 0:
                # symbol_info 表没有数据，清空搜索表
                self.connection.execute("DELETE FROM symbol_search_table")
                return

            # 清空搜索表
            self.connection.execute("DELETE FROM symbol_search_table")

            # 从 symbol_info 表插入数据到搜索表
            self.connection.execute("""
                INSERT INTO symbol_search_table (code, name, type, exchange, update_time)
                SELECT 
                    instrument_id as code,
                    instrument_name as name,
                    ins_class as type,
                    exchange_id as exchange,
                    CURRENT_TIMESTAMP as update_time
                FROM symbol_info
                WHERE instrument_id IS NOT NULL AND instrument_name IS NOT NULL
            """)

            # print(f"[DatabaseManager] 已从 symbol_info 表重建搜索表数据")

        except Exception as e:
            print(f"[DatabaseManager] 从 symbol_info 表重建搜索表失败: {e}")

    def _migrate_table(self):
        """迁移表结构，添加缺失的列"""
        try:
            # 获取当前表的列信息
            result = self.connection.execute("DESCRIBE symbol_info").fetchall()
            existing_columns = {row[0] for row in result}

            # 需要添加的新列
            new_columns = [
                ('open_limit', 'DOUBLE'),
                ('min_limit_order_volume', 'INTEGER'),
                ('min_market_order_volume', 'INTEGER'),
                ('open_max_market_order_volume', 'INTEGER'),
                ('open_max_limit_order_volume', 'INTEGER'),
                ('open_min_market_order_volume', 'INTEGER'),
                ('open_min_limit_order_volume', 'INTEGER'),
            ]

            # 添加缺失的列
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    self.connection.execute(f"ALTER TABLE symbol_info ADD COLUMN {col_name} {col_type}")
                    # print(f"[DatabaseManager] 已添加列: {col_name}")

        except Exception as e:
            # print(f"[DatabaseManager] 迁移表结构失败: {e}")
            # 如果迁移失败，删除旧数据库重新创建
            import os
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                # print(f"[DatabaseManager] 已删除旧数据库: {self.db_path}")
                # 重新连接并创建表（不调用迁移方法）
                import duckdb
                self.connection = duckdb.connect(self.db_path)
                # print(f"[DatabaseManager] 已重新连接到数据库: {self.db_path}")

                # 创建完整的表结构
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_info (
                        instrument_id VARCHAR PRIMARY KEY,
                        instrument_name VARCHAR,
                        ins_class VARCHAR,
                        exchange_id VARCHAR,
                        product_id VARCHAR,
                        price_tick DOUBLE,
                        volume_multiple DOUBLE,
                        open_limit DOUBLE,
                        max_limit_order_volume INTEGER,
                        max_market_order_volume INTEGER,
                        min_limit_order_volume INTEGER,
                        min_market_order_volume INTEGER,
                        open_max_market_order_volume INTEGER,
                        open_max_limit_order_volume INTEGER,
                        open_min_market_order_volume INTEGER,
                        open_min_limit_order_volume INTEGER,
                        underlying_symbol VARCHAR,
                        strike_price DOUBLE,
                        expired BOOLEAN,
                        expire_datetime TIMESTAMP,
                        expire_rest_days INTEGER,
                        delivery_year INTEGER,
                        delivery_month INTEGER,
                        last_exercise_datetime TIMESTAMP,
                        exercise_year INTEGER,
                        exercise_month INTEGER,
                        option_class VARCHAR,
                        upper_limit DOUBLE,
                        lower_limit DOUBLE,
                        pre_settlement DOUBLE,
                        pre_open_interest DOUBLE,
                        pre_close DOUBLE,
                        trading_time_day VARCHAR,
                        trading_time_night VARCHAR,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 创建交易所合约列表表
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS exchange_symbols (
                        id INTEGER PRIMARY KEY,
                        ins_class VARCHAR,
                        exchange_id VARCHAR,
                        instrument_id VARCHAR,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(ins_class, exchange_id, instrument_id)
                    )
                """)

                # 创建索引
                self.connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_symbol_info_exchange
                    ON symbol_info(exchange_id, ins_class)
                """)

                self.connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_exchange_symbols_class
                    ON exchange_symbols(ins_class, exchange_id)
                """)

                # print("[DatabaseManager] 数据库表重新创建完成")

    def save_symbol_info(self, symbol_info_df: pd.DataFrame) -> bool:
        """
        保存合约信息到数据库

        Args:
            symbol_info_df: 合约信息DataFrame

        Returns:
            bool: 是否保存成功
        """
        try:
            if symbol_info_df is None or symbol_info_df.empty:
                # print("[DatabaseManager] 数据为空，跳过保存")
                return False

            # 检查数据库连接
            if self.connection is None:
                # print("[DatabaseManager] 数据库连接为空，尝试重新连接...")
                self._connect()
                if self.connection is None:
                    print("[DatabaseManager] 重新连接失败")
                    return False

            # 添加更新时间
            symbol_info_df = symbol_info_df.copy()
            symbol_info_df['update_time'] = datetime.now()

            # 数据类型转换：将时间戳列转换为正确的类型
            timestamp_columns = ['expire_datetime', 'last_exercise_datetime']
            for col in timestamp_columns:
                if col in symbol_info_df.columns:
                    # 如果是数值类型，转换为datetime
                    if symbol_info_df[col].dtype in ['float64', 'int64']:
                        # 将纳秒时间戳转换为datetime
                        symbol_info_df[col] = pd.to_datetime(symbol_info_df[col], unit='ns', errors='coerce')
                    # 如果已经是datetime类型，确保格式正确
                    elif symbol_info_df[col].dtype == 'object':
                        symbol_info_df[col] = pd.to_datetime(symbol_info_df[col], errors='coerce')

            # 去重：保留每个instrument_id的最后一条记录
            if 'instrument_id' in symbol_info_df.columns:
                original_count = len(symbol_info_df)
                symbol_info_df = symbol_info_df.drop_duplicates(subset='instrument_id', keep='last')
                # if len(symbol_info_df) < original_count:
                #     print(f"[DatabaseManager] 去重: {original_count} -> {len(symbol_info_df)} 条记录")

            # 获取数据库表的列顺序
            table_columns = [
                'instrument_id', 'instrument_name', 'ins_class', 'exchange_id', 'product_id',
                'price_tick', 'volume_multiple', 'open_limit', 'max_limit_order_volume',
                'max_market_order_volume', 'min_limit_order_volume', 'min_market_order_volume',
                'open_max_market_order_volume', 'open_max_limit_order_volume',
                'open_min_market_order_volume', 'open_min_limit_order_volume',
                'underlying_symbol', 'strike_price', 'expired', 'expire_datetime',
                'expire_rest_days', 'delivery_year', 'delivery_month', 'last_exercise_datetime',
                'exercise_year', 'exercise_month', 'option_class', 'upper_limit', 'lower_limit',
                'pre_settlement', 'pre_open_interest', 'pre_close', 'trading_time_day',
                'trading_time_night', 'update_time'
            ]

            # 重新排列DataFrame的列，确保与数据库表顺序一致
            # 只保留表中存在的列
            available_columns = [col for col in table_columns if col in symbol_info_df.columns]
            symbol_info_df = symbol_info_df[available_columns]

            # 使用INSERT OR REPLACE语法（DuckDB支持）
            # 先删除旧数据，再插入新数据
            instrument_ids = symbol_info_df['instrument_id'].tolist()
            placeholders = ','.join(['?' for _ in instrument_ids])
            self.connection.execute(
                f"DELETE FROM symbol_info WHERE instrument_id IN ({placeholders})",
                instrument_ids
            )

            # 插入新数据（使用明确的列名）
            columns_str = ', '.join(available_columns)
            self.connection.execute(
                f"INSERT INTO symbol_info ({columns_str}) SELECT {columns_str} FROM symbol_info_df"
            )
            # print(f"[DatabaseManager] 已保存 {len(symbol_info_df)} 条合约信息")

            return True
        except Exception as e:
            print(f"[DatabaseManager] 保存合约信息失败: {e}")
            import traceback
            traceback.print_exc()

            # 如果是WAL文件损坏，尝试重新连接
            if "WAL file" in str(e) or "replay" in str(e):
                print("[DatabaseManager] 检测到WAL文件损坏，尝试重新初始化数据库...")
                try:
                    self._connect()
                    # 重试保存
                    return self.save_symbol_info(symbol_info_df)
                except Exception as e2:
                    print(f"[DatabaseManager] 重试保存失败: {e2}")
                    return False

            return False

    def get_search_table(self) -> Optional[pd.DataFrame]:
        """
        获取搜索表数据（用于键盘精灵）

        Returns:
            pd.DataFrame: 搜索表数据，包含 code, name, type, exchange 列
        """
        try:
            result = self.connection.execute(
                "SELECT code, name, type, exchange FROM symbol_search_table ORDER BY code"
            ).fetchall()

            if result:
                return pd.DataFrame(result, columns=['code', 'name', 'type', 'exchange'])
            return None
        except Exception as e:
            print(f"[DatabaseManager] 获取搜索表失败: {e}")
            return None

    def save_exchange_symbols(self, ins_class: str, exchange_id: str, symbols: list) -> bool:
        """
        保存交易所合约列表

        Args:
            ins_class: 合约类型
            exchange_id: 交易所ID
            symbols: 合约代码列表

        Returns:
            bool: 是否保存成功
        """
        try:
            # 删除旧的合约列表
            self.connection.execute(
                "DELETE FROM exchange_symbols WHERE ins_class = ? AND exchange_id = ?",
                [ins_class, exchange_id]
            )

            # 插入新的合约列表
            if symbols:
                df = pd.DataFrame({
                    'ins_class': [ins_class] * len(symbols),
                    'exchange_id': [exchange_id] * len(symbols),
                    'instrument_id': symbols,
                    'update_time': [datetime.now()] * len(symbols)
                })
                self.connection.execute("INSERT INTO exchange_symbols SELECT * FROM df")
                # print(f"[DatabaseManager] 已保存 {len(symbols)} 个合约到 {ins_class}/{exchange_id}")
            return True
        except Exception as e:
            print(f"[DatabaseManager] 保存交易所合约列表失败: {e}")
            return False

    def save_ins_class_map(self, ins_class_map: dict) -> bool:
        """
        保存合约类型映射表

        Args:
            ins_class_map: 合约类型映射字典 {英文: 中文}

        Returns:
            bool: 是否保存成功
        """
        try:
            # 清空旧数据
            self.connection.execute("DELETE FROM ins_class_map")

            # 插入新数据
            if ins_class_map:
                df = pd.DataFrame([
                    {'ins_class_en': en, 'ins_class_cn': cn, 'update_time': datetime.now()}
                    for en, cn in ins_class_map.items()
                ])
                self.connection.execute("INSERT INTO ins_class_map SELECT * FROM df")
                #print(f"[DatabaseManager] 已保存 {len(ins_class_map)} 个合约类型映射")
            return True
        except Exception as e:
            print(f"[DatabaseManager] 保存合约类型映射失败: {e}")
            return False

    def save_exchange_id_map(self, exchange_id_map: dict) -> bool:
        """
        保存交易所映射表

        Args:
            exchange_id_map: 交易所映射字典 {英文: 中文}

        Returns:
            bool: 是否保存成功
        """
        try:
            # 清空旧数据
            self.connection.execute("DELETE FROM exchange_id_map")

            # 插入新数据
            if exchange_id_map:
                df = pd.DataFrame([
                    {'exchange_id_en': en, 'exchange_id_cn': cn, 'update_time': datetime.now()}
                    for en, cn in exchange_id_map.items()
                ])
                self.connection.execute("INSERT INTO exchange_id_map SELECT * FROM df")
                # print(f"[DatabaseManager] 已保存 {len(exchange_id_map)} 个交易所映射")
            return True
        except Exception as e:
            print(f"[DatabaseManager] 保存交易所映射失败: {e}")
            return False

    def get_ins_class_map(self) -> dict:
        """
        获取合约类型映射表

        Returns:
            dict: 合约类型映射字典 {英文: 中文}
        """
        try:
            result = self.connection.execute("SELECT ins_class_en, ins_class_cn FROM ins_class_map").fetchall()
            return {row[0]: row[1] for row in result}
        except Exception as e:
            print(f"[DatabaseManager] 获取合约类型映射失败: {e}")
            return {}

    def get_exchange_id_map(self) -> dict:
        """
        获取交易所映射表

        Returns:
            dict: 交易所映射字典 {英文: 中文}
        """
        try:
            result = self.connection.execute("SELECT exchange_id_en, exchange_id_cn FROM exchange_id_map").fetchall()
            return {row[0]: row[1] for row in result}
        except Exception as e:
            print(f"[DatabaseManager] 获取交易所映射失败: {e}")
            return {}

    def get_symbol_info(self, ins_class: str = None, exchange_id: str = None) -> Optional[pd.DataFrame]:
        """
        从数据库获取合约信息

        Args:
            ins_class: 合约类型（可选）
            exchange_id: 交易所ID（可选）

        Returns:
            pd.DataFrame: 合约信息DataFrame
        """
        try:
            query = "SELECT * FROM symbol_info WHERE 1=1"
            params = []

            if ins_class:
                query += " AND ins_class = ?"
                params.append(ins_class)

            if exchange_id:
                query += " AND exchange_id = ?"
                params.append(exchange_id)

            result = self.connection.execute(query, params).fetchdf()

            if result.empty:
                # print("[DatabaseManager] 数据库中没有找到合约信息")
                return None

            # print(f"[DatabaseManager] 从数据库加载了 {len(result)} 条合约信息")
            return result
        except Exception as e:
            print(f"[DatabaseManager] 获取合约信息失败: {e}")
            return None

    def get_exchange_symbols(self, ins_class: str, exchange_id: str) -> list:
        """
        从数据库获取交易所合约列表

        Args:
            ins_class: 合约类型
            exchange_id: 交易所ID

        Returns:
            list: 合约代码列表
        """
        try:
            result = self.connection.execute(
                "SELECT instrument_id FROM exchange_symbols WHERE ins_class = ? AND exchange_id = ?",
                [ins_class, exchange_id]
            ).fetchall()

            symbols = [row[0] for row in result]
            # print(f"[DatabaseManager] 从数据库加载了 {len(symbols)} 个合约")
            return symbols
        except Exception as e:
            print(f"[DatabaseManager] 获取交易所合约列表失败: {e}")
            return []

    def has_data(self) -> bool:
        """
        检查数据库中是否有数据

        Returns:
            bool: 是否有数据
        """
        try:
            result = self.connection.execute("SELECT COUNT(*) FROM symbol_info").fetchone()
            return result[0] > 0
        except Exception as e:
            print(f"[DatabaseManager] 检查数据失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            print("[DatabaseManager] 数据库连接已关闭")


class DatabaseInitThread(QThread):
    """数据库初始化线程"""
    init_finished = pyqtSignal(bool)

    def __init__(self, db_path: str = None):
        super().__init__()
        self.db_path = db_path
        self.db_manager = None

    def run(self):
        """在后台线程中初始化数据库"""
        try:
            # print("[DatabaseInitThread] 开始初始化数据库...")
            self.db_manager = DatabaseManager(self.db_path)
            has_data = self.db_manager.has_data()
            # print(f"[DatabaseInitThread] 数据库初始化完成，已有数据: {has_data}")
            self.init_finished.emit(True)
        except Exception as e:
            print(f"[DatabaseInitThread] 数据库初始化失败: {e}")
            self.init_finished.emit(False)


class SaveSymbolInfoThread(QThread):
    """保存合约信息的线程"""
    save_finished = pyqtSignal(bool)

    def __init__(self, db_manager: DatabaseManager, symbol_info_df: pd.DataFrame):
        super().__init__()
        self.db_manager = db_manager
        self.symbol_info_df = symbol_info_df

    def run(self):
        """在后台线程中保存数据"""
        try:
            # print("[SaveSymbolInfoThread] 开始保存合约信息...")
            success = self.db_manager.save_symbol_info(self.symbol_info_df)
            # print(f"[SaveSymbolInfoThread] 保存完成: {success}")
            self.save_finished.emit(success)
        except Exception as e:
            print(f"[SaveSymbolInfoThread] 保存失败: {e}")
            self.save_finished.emit(False)


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager

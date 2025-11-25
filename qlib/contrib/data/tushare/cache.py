"""
TuShare数据源缓存管理

提供TuShare数据源的专用缓存功能，包括内存缓存、磁盘缓存和缓存管理策略。

缓存层级：
1. 内存缓存：L1缓存，快速访问，容量有限
2. 磁盘缓存：L2缓存，持久化存储，容量较大
3. 缓存管理：统一缓存策略和生命周期管理

缓存策略：
- LRU最近最少使用淘汰
- TTL过期时间控制
- 容量限制和清理
- 数据一致性保证
"""

import os
import pickle
import hashlib
import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from collections import OrderedDict
from threading import Lock
import pandas as pd
from datetime import datetime, timedelta

from .config import TuShareConfig
from .exceptions import TuShareCacheError


class TuShareMemoryCache:
    """
    TuShare内存缓存

    基于LRU算法的内存缓存实现，提供快速的数据访问。
    """

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存生存时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.lock = Lock()

    def _generate_key(self, *args, **kwargs) -> str:
        """
        生成缓存键

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            缓存键字符串
        """
        key_data = f"{args}_{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期则返回None
        """
        with self.lock:
            if key not in self.cache:
                return None

            value, timestamp = self.cache[key]

            # 检查是否过期
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None

            # 移动到末尾（LRU策略）
            self.cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self.lock:
            # 如果键已存在，更新值并移动到末尾
            if key in self.cache:
                self.cache[key] = (value, time.time())
                self.cache.move_to_end(key)
                return

            # 检查容量限制
            if len(self.cache) >= self.max_size:
                # 删除最旧的条目
                self.cache.popitem(last=False)

            # 添加新条目
            self.cache[key] = (value, time.time())

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self) -> None:
        """
        清空缓存
        """
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        """
        获取缓存大小

        Returns:
            缓存条目数
        """
        with self.lock:
            return len(self.cache)

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的条目数
        """
        with self.lock:
            current_time = time.time()
            expired_keys = []

            for key, (_, timestamp) in self.cache.items():
                if current_time - timestamp > self.ttl:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        with self.lock:
            current_time = time.time()
            expired_count = sum(
                1 for _, timestamp in self.cache.values()
                if current_time - timestamp > self.ttl
            )

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "expired_count": expired_count,
                "usage_ratio": len(self.cache) / self.max_size if self.max_size > 0 else 0
            }


class TuShareDiskCache:
    """
    TuShare磁盘缓存

    基于SQLite和文件系统的磁盘缓存实现，提供持久化的数据存储。
    """

    def __init__(self, cache_dir: str, ttl: int = 86400, max_size: int = 1024 * 1024 * 1024):
        """
        初始化磁盘缓存

        Args:
            cache_dir: 缓存目录
            ttl: 缓存生存时间（秒）
            max_size: 最大缓存大小（字节）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.max_size = max_size

        # 初始化数据库
        self.db_path = self.cache_dir / "cache.db"
        self.data_dir = self.cache_dir / "data"
        self.data_dir.mkdir(exist_ok=True)

        self._init_database()

    def _init_database(self) -> None:
        """
        初始化缓存数据库
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        accessed_at REAL NOT NULL,
                        size INTEGER NOT NULL,
                        metadata TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_accessed_at ON cache_entries(accessed_at)
                """)
                conn.commit()
        except Exception as e:
            raise TuShareCacheError(
                f"初始化缓存数据库失败: {str(e)}",
                cache_path=str(self.db_path),
                cause=e
            )

    def _generate_key(self, *args, **kwargs) -> str:
        """
        生成缓存键

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            缓存键字符串
        """
        key_data = f"{args}_{sorted(kwargs.items())}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _get_file_path(self, key: str) -> Path:
        """
        获取缓存文件路径

        Args:
            key: 缓存键

        Returns:
            文件路径
        """
        # 使用键的前两位作为子目录，避免单个目录文件过多
        sub_dir = key[:2]
        file_dir = self.data_dir / sub_dir
        file_dir.mkdir(exist_ok=True)
        return file_dir / f"{key}.pkl"

    def _get_cache_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存信息

        Args:
            key: 缓存键

        Returns:
            缓存信息字典，如果不存在则返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM cache_entries WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()

                if row:
                    columns = ["key", "file_path", "created_at", "accessed_at", "size", "metadata"]
                    return dict(zip(columns, row))
                else:
                    return None
        except Exception as e:
            raise TuShareCacheError(
                f"查询缓存信息失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期则返回None
        """
        try:
            # 获取缓存信息
            cache_info = self._get_cache_info(key)
            if not cache_info:
                return None

            # 检查是否过期
            current_time = time.time()
            if current_time - cache_info["created_at"] > self.ttl:
                self.delete(key)
                return None

            # 检查文件是否存在
            file_path = Path(cache_info["file_path"])
            if not file_path.exists():
                self.delete(key)
                return None

            # 读取数据
            try:
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)

                # 更新访问时间
                self._update_access_time(key)

                return data
            except Exception as e:
                # 文件损坏，删除缓存条目
                self.delete(key)
                raise TuShareCacheError(
                    f"读取缓存文件失败: {str(e)}",
                    cache_key=key,
                    cache_path=str(file_path),
                    cause=e
                )

        except TuShareCacheError:
            raise
        except Exception as e:
            raise TuShareCacheError(
                f"获取缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def set(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            metadata: 元数据（可选）
        """
        try:
            file_path = self._get_file_path(key)
            current_time = time.time()

            # 序列化数据到文件
            try:
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
            except Exception as e:
                raise TuShareCacheError(
                    f"写入缓存文件失败: {str(e)}",
                    cache_key=key,
                    cache_path=str(file_path),
                    cause=e
                )

            # 获取文件大小
            file_size = file_path.stat().st_size

            # 更新数据库记录
            metadata_json = pickle.dumps(metadata) if metadata else None

            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries
                        (key, file_path, created_at, accessed_at, size, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        key,
                        str(file_path),
                        current_time,
                        current_time,
                        file_size,
                        metadata_json
                    ))
                    conn.commit()
            except Exception as e:
                # 删除文件，避免数据不一致
                if file_path.exists():
                    file_path.unlink()
                raise TuShareCacheError(
                    f"更新缓存数据库失败: {str(e)}",
                    cache_key=key,
                    cause=e
                )

            # 检查容量限制，清理过期和超量缓存
            self._cleanup()

        except TuShareCacheError:
            raise
        except Exception as e:
            raise TuShareCacheError(
                f"设置缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        try:
            cache_info = self._get_cache_info(key)
            if not cache_info:
                return False

            # 删除文件
            file_path = Path(cache_info["file_path"])
            if file_path.exists():
                file_path.unlink()

            # 删除数据库记录
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()

            return True

        except TuShareCacheError:
            raise
        except Exception as e:
            raise TuShareCacheError(
                f"删除缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def clear(self) -> None:
        """
        清空所有缓存
        """
        try:
            # 删除所有缓存文件
            for file_path in self.data_dir.rglob("*.pkl"):
                file_path.unlink()

            # 清空数据库
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()

        except Exception as e:
            raise TuShareCacheError(
                f"清空缓存失败: {str(e)}",
                cause=e
            )

    def _update_access_time(self, key: str) -> None:
        """
        更新缓存访问时间

        Args:
            key: 缓存键
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE cache_entries SET accessed_at = ? WHERE key = ?",
                    (time.time(), key)
                )
                conn.commit()
        except Exception as e:
            # 访问时间更新失败不影响主要功能，只记录日志
            print(f"[TuShare Cache] 更新访问时间失败: {str(e)}")

    def _cleanup(self) -> None:
        """
        清理缓存：删除过期条目和超量条目
        """
        try:
            current_time = time.time()

            with sqlite3.connect(self.db_path) as conn:
                # 删除过期条目
                expired_time = current_time - self.ttl
                cursor = conn.execute("""
                    SELECT key, file_path FROM cache_entries
                    WHERE created_at < ?
                """, (expired_time,))

                expired_entries = cursor.fetchall()
                for key, file_path in expired_entries:
                    try:
                        # 删除文件
                        path_obj = Path(file_path)
                        if path_obj.exists():
                            path_obj.unlink()
                    except Exception:
                        pass  # 忽略文件删除失败

                # 删除过期数据库记录
                conn.execute("DELETE FROM cache_entries WHERE created_at < ?", (expired_time,))

                # 检查总大小，如果超限则删除最旧的条目
                while self.get_total_size() > self.max_size:
                    cursor = conn.execute("""
                        SELECT key, file_path FROM cache_entries
                        ORDER BY accessed_at ASC
                        LIMIT 10
                    """)
                    old_entries = cursor.fetchall()

                    if not old_entries:
                        break

                    for key, file_path in old_entries:
                        try:
                            # 删除文件
                            path_obj = Path(file_path)
                            if path_obj.exists():
                                path_obj.unlink()
                        except Exception:
                            pass

                        # 删除数据库记录
                        conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))

                conn.commit()

        except Exception as e:
            # 清理失败不影响主要功能，只记录日志
            print(f"[TuShare Cache] 缓存清理失败: {str(e)}")

    def get_total_size(self) -> int:
        """
        获取缓存总大小

        Returns:
            缓存总大小（字节）
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT SUM(size) FROM cache_entries")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        try:
            current_time = time.time()

            with sqlite3.connect(self.db_path) as conn:
                # 基本统计
                cursor = conn.execute("SELECT COUNT(*), SUM(size) FROM cache_entries")
                count, total_size = cursor.fetchone()

                # 过期统计
                expired_time = current_time - self.ttl
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM cache_entries
                    WHERE created_at < ?
                """, (expired_time,))
                expired_count = cursor.fetchone()[0]

                return {
                    "count": count or 0,
                    "total_size": total_size or 0,
                    "max_size": self.max_size,
                    "ttl": self.ttl,
                    "expired_count": expired_count,
                    "usage_ratio": (total_size or 0) / self.max_size if self.max_size > 0 else 0
                }
        except Exception as e:
            return {
                "error": str(e),
                "count": 0,
                "total_size": 0,
                "max_size": self.max_size,
                "ttl": self.ttl,
                "expired_count": 0,
                "usage_ratio": 0
            }


class TuShareCacheManager:
    """
    TuShare缓存管理器

    统一管理内存缓存和磁盘缓存，提供缓存策略和生命周期管理。
    """

    def __init__(self, config: TuShareConfig):
        """
        初始化缓存管理器

        Args:
            config: TuShare配置对象
        """
        self.config = config

        # 初始化缓存组件
        if config.enable_cache:
            self.memory_cache = TuShareMemoryCache(
                max_size=1000,
                ttl=config.cache_ttl
            )
            self.disk_cache = TuShareDiskCache(
                cache_dir=config.cache_dir,
                ttl=config.cache_ttl,
                max_size=config.max_cache_size
            )
        else:
            self.memory_cache = None
            self.disk_cache = None

    def generate_key(self, *args, **kwargs) -> str:
        """
        生成缓存键

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            缓存键字符串
        """
        if self.memory_cache:
            return self.memory_cache._generate_key(*args, **kwargs)
        elif self.disk_cache:
            return self.disk_cache._generate_key(*args, **kwargs)
        else:
            key_data = f"{args}_{sorted(kwargs.items())}"
            return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str, level: str = "auto") -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键
            level: 缓存级别 ("memory", "disk", "auto")

        Returns:
            缓存值，如果不存在则返回None
        """
        if not self.config.enable_cache:
            return None

        try:
            if level == "memory" or (level == "auto" and self.memory_cache):
                # 优先从内存缓存获取
                if self.memory_cache:
                    value = self.memory_cache.get(key)
                    if value is not None:
                        return value

            if level in ["disk", "auto"] and self.disk_cache:
                # 从磁盘缓存获取
                value = self.disk_cache.get(key)
                if value is not None and self.memory_cache:
                    # 将值存入内存缓存（下次访问更快）
                    self.memory_cache.set(key, value)
                return value

            return None

        except TuShareCacheError:
            raise
        except Exception as e:
            raise TuShareCacheError(
                f"获取缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def set(self, key: str, value: Any, level: str = "all", metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            level: 缓存级别 ("memory", "disk", "all")
            metadata: 元数据（仅用于磁盘缓存）
        """
        if not self.config.enable_cache:
            return

        try:
            if level in ["memory", "all"] and self.memory_cache:
                self.memory_cache.set(key, value)

            if level in ["disk", "all"] and self.disk_cache:
                self.disk_cache.set(key, value, metadata)

        except TuShareCacheError:
            raise
        except Exception as e:
            raise TuShareCacheError(
                f"设置缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        if not self.config.enable_cache:
            return False

        success = True

        try:
            if self.memory_cache:
                success &= self.memory_cache.delete(key)

            if self.disk_cache:
                success &= self.disk_cache.delete(key)

            return success

        except Exception as e:
            raise TuShareCacheError(
                f"删除缓存失败: {str(e)}",
                cache_key=key,
                cause=e
            )

    def clear(self, level: str = "all") -> None:
        """
        清空缓存

        Args:
            level: 缓存级别 ("memory", "disk", "all")
        """
        if not self.config.enable_cache:
            return

        try:
            if level in ["memory", "all"] and self.memory_cache:
                self.memory_cache.clear()

            if level in ["disk", "all"] and self.disk_cache:
                self.disk_cache.clear()

        except Exception as e:
            raise TuShareCacheError(
                f"清空缓存失败: {str(e)}",
                cause=e
            )

    def cleanup(self) -> None:
        """
        执行缓存清理
        """
        if not self.config.enable_cache:
            return

        try:
            if self.memory_cache:
                self.memory_cache.cleanup_expired()

            if self.disk_cache:
                self.disk_cache._cleanup()

        except Exception as e:
            raise TuShareCacheError(
                f"缓存清理失败: {str(e)}",
                cause=e
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        stats = {
            "enabled": self.config.enable_cache,
            "config": {
                "cache_ttl": self.config.cache_ttl,
                "max_cache_size": self.config.max_cache_size,
                "cache_dir": self.config.cache_dir,
            }
        }

        if self.config.enable_cache:
            if self.memory_cache:
                stats["memory"] = self.memory_cache.get_stats()

            if self.disk_cache:
                stats["disk"] = self.disk_cache.get_stats()

        return stats
# cache.py
"""Caching module for archpkg-helper with SQLite backend and configurable TTL.
Provides efficient caching of search results with privacy considerations."""

import sqlite3
import json
import time
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import logging
from contextlib import contextmanager

from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

@dataclass
class CacheConfig:
    """Configuration for cache behavior with sensible defaults."""
    ttl_seconds: int = 24 * 60 * 60  # 24 hours default
    max_entries: int = 1000
    cache_dir: Optional[Path] = None
    enabled: bool = True
    cleanup_interval: int = 3600  # Cleanup expired entries every hour
    db_name: str = "cache.db"
    
    def __post_init__(self):
        if self.cache_dir is None:
            # Use XDG_CACHE_HOME standard or fallback to ~/.cache
            cache_home = os.environ.get('XDG_CACHE_HOME', 
                                      os.path.expanduser('~/.cache'))
            self.cache_dir = Path(cache_home) / 'archpkg-helper'
        
        # Ensure cache directory exists with proper permissions
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            logger.debug(f"Cache directory ready: {self.cache_dir}")
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to create cache directory: {e}")
            # Fallback to temp directory
            import tempfile
            self.cache_dir = Path(tempfile.gettempdir()) / 'archpkg-helper'
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using fallback cache directory: {self.cache_dir}")

class CacheManager:
    """Manages caching operations with SQLite backend and automatic cleanup."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize cache manager with configuration.
        
        Args:
            config: Cache configuration, uses defaults if None
        """
        self.config = config or CacheConfig()
        self.db_path = self.config.cache_dir / self.config.db_name
        self._last_cleanup = time.time()
        
        if self.config.enabled:
            self._init_db()
            logger.info(f"Cache manager initialized: {self.db_path}")
        else:
            logger.info("Cache disabled by configuration")
    
    def _init_db(self) -> None:
        """Initialize SQLite database with optimized schema."""
        try:
            with self._get_connection() as conn:
                conn.executescript('''
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        query_hash TEXT NOT NULL,
                        source TEXT NOT NULL,
                        value TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        access_count INTEGER DEFAULT 1,
                        last_accessed INTEGER NOT NULL
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_expires_at 
                    ON cache_entries(expires_at);
                    
                    CREATE INDEX IF NOT EXISTS idx_query_source 
                    ON cache_entries(query_hash, source);
                    
                    CREATE INDEX IF NOT EXISTS idx_last_accessed 
                    ON cache_entries(last_accessed);
                    
                    -- Enable WAL mode for better concurrency
                    PRAGMA journal_mode=WAL;
                    PRAGMA synchronous=NORMAL;
                    PRAGMA cache_size=10000;
                    PRAGMA temp_store=memory;
                ''')
                logger.debug("Database schema initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            # Disable cache if database initialization fails
            self.config.enabled = False
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
            conn.commit()  # Ensure changes are committed
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def _generate_cache_key(self, query: str, source: str) -> str:
        """Generate consistent cache key for query and source.
        
        Args:
            query: Search query string
            source: Package source (aur, pacman, apt, etc.)
            
        Returns:
            str: SHA256 hash of query and source
        """
        # Normalize query for consistent caching
        normalized_query = query.lower().strip()
        key_data = f"{normalized_query}:{source.lower()}"
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()
    
    def _generate_query_hash(self, query: str) -> str:
        """Generate hash for query tracking (privacy-safe)."""
        normalized_query = query.lower().strip()
        return hashlib.sha256(normalized_query.encode('utf-8')).hexdigest()[:16]
    
    def get(self, query: str, source: str) -> Optional[List[Tuple[str, str, str]]]:
        """Retrieve cached search results if available and not expired.
        
        Args:
            query: Search query string
            source: Package source (aur, pacman, apt, etc.)
            
        Returns:
            Optional[List[Tuple[str, str, str]]]: Cached results or None if not found/expired
        """
        if not self.config.enabled:
            return None
        
        key = self._generate_cache_key(query, source)
        current_time = int(time.time())
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT value, expires_at, access_count 
                    FROM cache_entries 
                    WHERE key = ? AND expires_at > ?
                ''', (key, current_time))
                
                row = cursor.fetchone()
                if row:
                    try:
                        # Update access statistics
                        conn.execute('''
                            UPDATE cache_entries 
                            SET access_count = access_count + 1, last_accessed = ?
                            WHERE key = ?
                        ''', (current_time, key))
                        
                        # Parse cached results
                        cached_data = json.loads(row['value'])
                        logger.debug(f"Cache hit for {source} query: {query[:50]}...")
                        logger.debug(f"Cache entry accessed {row['access_count']} times")
                        
                        return cached_data
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid cached data for key {key}: {e}")
                        # Remove corrupted entry
                        conn.execute('DELETE FROM cache_entries WHERE key = ?', (key,))
                        return None
                else:
                    logger.debug(f"Cache miss for {source} query: {query[:50]}...")
                    return None
                    
        except sqlite3.Error as e:
            logger.error(f"Database error during cache get: {e}")
            return None
    
    def set(self, query: str, source: str, results: List[Tuple[str, str, str]], 
            custom_ttl: Optional[int] = None) -> bool:
        """Store search results in cache with TTL.
        
        Args:
            query: Search query string
            source: Package source (aur, pacman, apt, etc.)
            results: Search results to cache
            custom_ttl: Custom TTL in seconds, uses config default if None
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.config.enabled or not results:
            return False
        
        # Privacy check: don't cache potentially sensitive queries
        if self._is_sensitive_query(query):
            logger.debug(f"Skipping cache for potentially sensitive query: {query[:20]}...")
            return False
        
        key = self._generate_cache_key(query, source)
        query_hash = self._generate_query_hash(query)
        current_time = int(time.time())
        ttl = custom_ttl or self.config.ttl_seconds
        expires_at = current_time + ttl
        
        try:
            # Serialize results (filter out sensitive information)
            sanitized_results = self._sanitize_results(results)
            json_value = json.dumps(sanitized_results, separators=(',', ':'))
            
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO cache_entries 
                    (key, query_hash, source, value, created_at, expires_at, access_count, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ''', (key, query_hash, source, json_value, current_time, expires_at, current_time))
                
                logger.debug(f"Cached {len(results)} results for {source} query (TTL: {ttl}s)")
                
                # Trigger cleanup if needed
                self._maybe_cleanup(conn)
                
                return True
                
        except (sqlite3.Error, TypeError, ValueError) as e:
            logger.error(f"Failed to cache results: {e}")
            return False
    
    def _is_sensitive_query(self, query: str) -> bool:
        """Check if query might contain sensitive information.
        
        Args:
            query: Search query to check
            
        Returns:
            bool: True if query appears sensitive
        """
        sensitive_patterns = [
            'password', 'secret', 'key', 'token', 'private',
            'credential', 'auth', 'login', 'admin', 'root'
        ]
        
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in sensitive_patterns)
    
    def _sanitize_results(self, results: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
        """Sanitize search results before caching (privacy protection).
        
        Args:
            results: Original search results
            
        Returns:
            List[Tuple[str, str, str]]: Sanitized results
        """
        sanitized = []
        for name, desc, source in results:
            # Limit description length to prevent bloat
            safe_desc = (desc or "")[:500] if desc else ""
            # Remove potential sensitive information from descriptions
            if not any(word in safe_desc.lower() for word in ['password', 'secret', 'private']):
                sanitized.append((name, safe_desc, source))
        
        return sanitized
    
    def _maybe_cleanup(self, conn: sqlite3.Connection) -> None:
        """Perform cleanup if enough time has passed since last cleanup."""
        current_time = time.time()
        if current_time - self._last_cleanup > self.config.cleanup_interval:
            self._cleanup_expired(conn)
            self._enforce_max_entries(conn)
            self._last_cleanup = current_time
    
    def _cleanup_expired(self, conn: Optional[sqlite3.Connection] = None) -> int:
        """Remove expired cache entries.
        
        Args:
            conn: Optional database connection to use
            
        Returns:
            int: Number of entries removed
        """
        current_time = int(time.time())
        
        def do_cleanup(connection):
            cursor = connection.execute(
                'DELETE FROM cache_entries WHERE expires_at <= ?',
                (current_time,)
            )
            return cursor.rowcount
        
        try:
            if conn:
                removed_count = do_cleanup(conn)
            else:
                with self._get_connection() as connection:
                    removed_count = do_cleanup(connection)
            
            if removed_count > 0:
                logger.debug(f"Cleaned up {removed_count} expired cache entries")
            
            return removed_count
            
        except sqlite3.Error as e:
            logger.error(f"Failed to cleanup expired entries: {e}")
            return 0
    
    def _enforce_max_entries(self, conn: sqlite3.Connection) -> int:
        """Enforce maximum cache entries by removing least recently used entries.
        
        Args:
            conn: Database connection
            
        Returns:
            int: Number of entries removed
        """
        try:
            # Count current entries
            cursor = conn.execute('SELECT COUNT(*) FROM cache_entries')
            current_count = cursor.fetchone()[0]
            
            if current_count <= self.config.max_entries:
                return 0
            
            # Remove oldest entries to get back under limit
            excess_count = current_count - self.config.max_entries
            cursor = conn.execute('''
                DELETE FROM cache_entries 
                WHERE key IN (
                    SELECT key FROM cache_entries 
                    ORDER BY last_accessed ASC 
                    LIMIT ?
                )
            ''', (excess_count,))
            
            removed_count = cursor.rowcount
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} LRU cache entries to enforce limit")
            
            return removed_count
            
        except sqlite3.Error as e:
            logger.error(f"Failed to enforce max entries: {e}")
            return 0
    
    def clear(self, source: Optional[str] = None) -> int:
        """Clear cache entries.
        
        Args:
            source: Optional source filter, clears all if None
            
        Returns:
            int: Number of entries removed
        """
        if not self.config.enabled:
            return 0
        
        try:
            with self._get_connection() as conn:
                if source:
                    cursor = conn.execute('DELETE FROM cache_entries WHERE source = ?', (source,))
                    logger.info(f"Cleared {source} cache entries")
                else:
                    cursor = conn.execute('DELETE FROM cache_entries')
                    logger.info("Cleared all cache entries")
                
                return cursor.rowcount
                
        except sqlite3.Error as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        if not self.config.enabled:
            return {"enabled": False}
        
        try:
            with self._get_connection() as conn:
                # Get basic stats
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_entries,
                        COUNT(CASE WHEN expires_at > ? THEN 1 END) as valid_entries,
                        SUM(access_count) as total_accesses,
                        AVG(access_count) as avg_access_count
                    FROM cache_entries
                ''', (int(time.time()),))
                
                basic_stats = cursor.fetchone()
                
                # Get source breakdown
                cursor = conn.execute('''
                    SELECT source, COUNT(*) as count 
                    FROM cache_entries 
                    WHERE expires_at > ?
                    GROUP BY source
                ''', (int(time.time()),))
                
                source_stats = dict(cursor.fetchall())
                
                return {
                    "enabled": True,
                    "db_path": str(self.db_path),
                    "total_entries": basic_stats[0] or 0,
                    "valid_entries": basic_stats[1] or 0,
                    "total_accesses": basic_stats[2] or 0,
                    "avg_access_count": round(basic_stats[3] or 0, 2),
                    "source_breakdown": source_stats,
                    "config": {
                        "ttl_seconds": self.config.ttl_seconds,
                        "max_entries": self.config.max_entries,
                        "cache_dir": str(self.config.cache_dir)
                    }
                }
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}
    
    def invalidate_query(self, query: str, source: Optional[str] = None) -> int:
        """Invalidate cache entries for a specific query.
        
        Args:
            query: Query to invalidate
            source: Optional source filter
            
        Returns:
            int: Number of entries invalidated
        """
        if not self.config.enabled:
            return 0
        
        query_hash = self._generate_query_hash(query)
        
        try:
            with self._get_connection() as conn:
                if source:
                    cursor = conn.execute(
                        'DELETE FROM cache_entries WHERE query_hash = ? AND source = ?',
                        (query_hash, source)
                    )
                else:
                    cursor = conn.execute(
                        'DELETE FROM cache_entries WHERE query_hash = ?',
                        (query_hash,)
                    )
                
                removed_count = cursor.rowcount
                if removed_count > 0:
                    logger.debug(f"Invalidated {removed_count} cache entries for query: {query[:50]}...")
                
                return removed_count
                
        except sqlite3.Error as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0

# Global cache manager instance
_cache_manager: Optional[CacheManager] = None

def get_cache_manager(config: Optional[CacheConfig] = None) -> CacheManager:
    """Get global cache manager instance (singleton pattern).
    
    Args:
        config: Cache configuration for first initialization
        
    Returns:
        CacheManager: Global cache manager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(config)
    return _cache_manager

def reset_cache_manager() -> None:
    """Reset global cache manager (useful for testing)."""
    global _cache_manager
    _cache_manager = None
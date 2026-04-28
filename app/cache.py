import os
import json
import functools
import logging
from typing import Any, Optional
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

# System-wide in-memory cache fallback (No Redis)
_local_cache = {}
_cache_expiry = {}
MAX_CACHE_SIZE = 500  # Prevent unbounded memory growth

async def get_redis_client():
    """Stub for compatibility - Always returns None to force local cache path."""
    return None

from decimal import Decimal

class CacheEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

async def set_cache(key: str, value: Any, ttl: int = 300):
    try:
        # Evict oldest entries if cache is too large
        if len(_local_cache) >= MAX_CACHE_SIZE:
            now = datetime.now()
            # First remove expired entries
            expired = [k for k, exp in _cache_expiry.items() if now >= exp]
            for k in expired:
                _local_cache.pop(k, None)
                _cache_expiry.pop(k, None)
            # If still too large, remove oldest 100 entries
            if len(_local_cache) >= MAX_CACHE_SIZE:
                oldest = sorted(_cache_expiry.items(), key=lambda x: x[1])[:100]
                for k, _ in oldest:
                    _local_cache.pop(k, None)
                    _cache_expiry.pop(k, None)

        json_val = json.dumps(value, cls=CacheEncoder)
        _local_cache[key] = json_val
        _cache_expiry[key] = datetime.now() + timedelta(seconds=ttl)
    except Exception as e:
        logger.error(f"Local cache set error: {e}")

async def get_cache(key: str) -> Optional[Any]:
    try:
        if key in _local_cache:
            if datetime.now() < _cache_expiry.get(key, datetime.now()):
                return json.loads(_local_cache[key])
            else:
                # Expired
                _local_cache.pop(key, None)
                _cache_expiry.pop(key, None)
        return None
    except Exception as e:
        logger.error(f"Local cache get error: {e}")
        return None

async def delete_cache(key: str):
    _local_cache.pop(key, None)
    _cache_expiry.pop(key, None)

async def delete_cache_pattern(prefix: str):
    """Delete all cache keys matching a prefix pattern."""
    keys_to_delete = [k for k in _local_cache if k.startswith(prefix)]
    for k in keys_to_delete:
        _local_cache.pop(k, None)
        _cache_expiry.pop(k, None)

async def invalidate_dashboard_cache():
    """Invalidate all dashboard/stats caches when case data changes."""
    await delete_cache_pattern("cache:get_dashboard_summary")
    await delete_cache_pattern("stats:")
    await delete_cache_pattern("dashboard:")

async def clear_cache(pattern: str = "*"):
    _local_cache.clear()
    _cache_expiry.clear()

def cache_response(ttl: int = 300, key_prefix: str = "cache"):
    """Decorator to cache function results in local memory."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key_parts = [key_prefix, func.__name__]
            for k, v in sorted(kwargs.items()):
                if k not in ['db', 'current_user', 'response']:
                    cache_key_parts.append(f"{k}:{v}")
            
            if 'current_user' in kwargs and hasattr(kwargs['current_user'], 'id'):
                cache_key_parts.append(f"user:{kwargs['current_user'].id}")
            
            cache_key = ":".join(cache_key_parts)
            
            cached_value = await get_cache(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            await set_cache(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

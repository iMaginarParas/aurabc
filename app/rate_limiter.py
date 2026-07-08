import time
import logging
import threading
from collections import defaultdict
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

class InMemorySlidingWindowLimiter:
    def __init__(self):
        # Maps keys (e.g. rate_limit:ip:endpoint) to lists of epoch timestamps
        self.requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            # Filter out timestamps older than the sliding window boundary
            cutoff = now - window_seconds
            self.requests[key] = [t for t in self.requests[key] if t > cutoff]
            
            # Verify request frequency
            if len(self.requests[key]) >= limit:
                logger.warning(f"Rate limit hit for key: {key} (limit {limit} per {window_seconds}s)")
                return False
            
            # Record current attempt
            self.requests[key].append(now)
            return True

# Initialize a global rate limiter instance
limiter = InMemorySlidingWindowLimiter()

def rate_limit(limit: int, window_seconds: int):
    """
    FastAPI dependency factory that returns a rate limiting checker.
    Example: Depends(rate_limit(times=5, window_seconds=60))
    """
    def rate_limit_dependency(request: Request):
        # 1. Resolve client identity (fall back to unknown)
        client_ip = "unknown"
        if request.client and request.client.host:
            client_ip = request.client.host
            
        # Parse forwarded headers if running behind a proxy (e.g. Nginx, Cloudflare)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # 2. Scope key per client IP and path
        route_path = request.url.path
        key = f"rate_limit:{client_ip}:{route_path}"

        # 3. Check rate limits
        if not limiter.is_allowed(key, limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Too Many Requests",
                    "message": "API request rate limit exceeded. Please wait and try again later.",
                    "limit": limit,
                    "window_seconds": window_seconds
                }
            )
    return rate_limit_dependency

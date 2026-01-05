"""
Security utilities for authentication, authorization, and data protection.

Provides password hashing, JWT handling, and encryption utilities.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from config.settings import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to encode
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.auth.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.secret_key.get_secret_value(),
        algorithm=settings.auth.algorithm,
    )
    
    return encoded_jwt


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Payload data to encode
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.auth.refresh_token_expire_days
        )
    
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.secret_key.get_secret_value(),
        algorithm=settings.auth.algorithm,
    )
    
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
        )
        return payload
    except JWTError:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key with prefix.
    
    Returns:
        Tuple of (full_key, prefix, key_hash)
    """
    # Generate random bytes
    key_bytes = secrets.token_bytes(32)
    full_key = secrets.token_urlsafe(32)
    
    # Create prefix for identification (first 8 chars)
    prefix = full_key[:8]
    
    # Hash the key for storage
    key_hash = get_password_hash(full_key)
    
    return full_key, prefix, key_hash


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        api_key: Plain API key
        key_hash: Stored hash
        
    Returns:
        True if key matches
    """
    return verify_password(api_key, key_hash)


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password meets security requirements.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    
    if len(password) < settings.auth.password_min_length:
        issues.append(
            f"Password must be at least {settings.auth.password_min_length} characters"
        )
    
    if not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one digit")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        issues.append("Password must contain at least one special character")
    
    return len(issues) == 0, issues


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Length of token in bytes
        
    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging/display.
    
    Args:
        data: Sensitive string to mask
        visible_chars: Number of characters to show at end
        
    Returns:
        Masked string
    """
    if len(data) <= visible_chars:
        return "*" * len(data)
    
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]


class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    For production, use Redis-based rate limiting.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed for given key.
        
        Args:
            key: Identifier (e.g., user ID, IP address)
            
        Returns:
            True if request is allowed
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        if key in self._requests:
            self._requests[key] = [
                ts for ts in self._requests[key]
                if ts > window_start
            ]
        else:
            self._requests[key] = []
        
        # Check limit
        if len(self._requests[key]) >= self.max_requests:
            return False
        
        # Record request
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        if key not in self._requests:
            return self.max_requests
        
        recent = [ts for ts in self._requests[key] if ts > window_start]
        return max(0, self.max_requests - len(recent))


# Global rate limiter instance
rate_limiter = RateLimiter()

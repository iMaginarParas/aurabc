import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

# Optional: try importing pyjwt
try:
    import jwt
except ImportError:
    jwt = None

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Decodes and strictly verifies the Supabase JWT token from the Authorization header.
    Rejects requests without verified signatures in production environments.
    """
    app_env = os.getenv("APP_ENV", "production").lower()
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    # 1. Enforce token presence in production
    if not credentials:
        if app_env == "development":
            logger.warning("No credentials found. Falling back to guest_user in development environment.")
            return {"sub": "guest_user", "email": "guest@auraroutes.com", "role": "authenticated"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required to access this resource."
        )

    token = credentials.credentials

    # 2. Check for secret configuration
    if not jwt_secret:
        if app_env == "development":
            logger.warning("SUPABASE_JWT_SECRET is missing. Bypassing signature verification in development.")
            if jwt:
                try:
                    return jwt.decode(token, options={"verify_signature": False})
                except Exception as e:
                    logger.error(f"Failed to decode token content: {str(e)}")
            return {"sub": "guest_user", "email": "guest@auraroutes.com"}
        
        logger.critical("SUPABASE_JWT_SECRET environment variable is missing in production mode.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server security configuration error. Signature validation cannot be performed."
        )

    # 3. Require PyJWT module
    if not jwt:
        logger.error("PyJWT library is missing on server runtime.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Required cryptographic libraries are missing on the host server."
        )

    # 4. Decode and cryptographically verify JWT token
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session token has expired. Please sign in again."
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cryptographic authentication verification failed: {str(err)}"
        )

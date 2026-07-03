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
    Decodes the Supabase JWT token from the Authorization header.
    Validates signature using SUPABASE_JWT_SECRET if provided.
    """
    if not credentials:
        # Fallback to guest_user in development or unauthenticated endpoints
        return {"sub": "guest_user", "email": "guest@auraroutes.com", "role": "authenticated"}

    token = credentials.credentials
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    if not jwt_secret:
        logger.warning("SUPABASE_JWT_SECRET is not configured in the environment. Skipping signature verification.")
        if jwt:
            try:
                # Decode without verification
                payload = jwt.decode(token, options={"verify_signature": False})
                return payload
            except Exception as e:
                logger.error(f"Failed to decode JWT: {str(e)}")
        # Basic fallback payload from token split
        return {"sub": "guest_user", "email": "guest@auraroutes.com"}

    if not jwt:
        logger.error("jwt (PyJWT) package is not installed. Cannot verify JWT signature.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT library not available on server."
        )

    try:
        # Verify and decode using the secret key
        # Supabase default signature algorithm is HS256
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token has expired."
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT token: {str(err)}"
        )

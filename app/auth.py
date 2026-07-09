import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import jwt
from jwt import PyJWKClient
from .config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# Global JWK client cached to avoid multiple network calls
jwk_client = None

def get_jwk_client() -> PyJWKClient:
    global jwk_client
    if jwk_client is not None:
        return jwk_client
        
    supabase_url = settings.supabase_url or os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    if not supabase_url:
        return None
        
    # Strip any trailing slash
    supabase_url = supabase_url.rstrip("/")
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    
    # Initialize PyJWKClient with caching options
    jwk_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return jwk_client

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Decodes and strictly verifies the Supabase JWT token from the Authorization header
    using Supabase's JWKS endpoint (ES256 asymmetric signature verification).
    Rejects requests without verified signatures in production environments.
    """
    app_env = os.getenv("APP_ENV", "production").lower()

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
    client = get_jwk_client()

    # 2. Check for JWK client availability (i.e. Supabase URL configured)
    if not client:
        if app_env == "development":
            logger.warning("SUPABASE_URL is missing. Bypassing signature verification in development.")
            try:
                # Decode without verification
                return jwt.decode(token, options={"verify_signature": False})
            except Exception as e:
                logger.error(f"Failed to decode token content: {str(e)}")
            return {"sub": "guest_user", "email": "guest@auraroutes.com", "role": "authenticated"}
        
        logger.critical("SUPABASE_URL environment variable is missing in production mode.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server security configuration error. Supabase URL is not configured."
        )

    # 3. Fetch public signing key from JWKS and cryptographically verify JWT token
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            options={"verify_aud": False}
        )
        return payload
    except Exception as e:
        if app_env == "development":
            logger.warning(f"JWKS verification failed: {str(e)}. Falling back to unverified decode in development.")
            try:
                return jwt.decode(token, options={"verify_signature": False})
            except Exception as decode_err:
                logger.error(f"Failed to decode token without verification: {str(decode_err)}")
            return {"sub": "guest_user", "email": "guest@auraroutes.com", "role": "authenticated"}
            
        if isinstance(e, jwt.ExpiredSignatureError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User session token has expired. Please sign in again."
            )
        elif isinstance(e, jwt.InvalidSignatureError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature. Cryptographic verification failed."
            )
        elif isinstance(e, jwt.InvalidAlgorithmError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token algorithm. Asymmetric signing is required."
            )
        else:
            logger.error(f"JWT Verification Error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Cryptographic authentication verification failed: {str(e)}"
            )

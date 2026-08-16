from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from helpers.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> bool:
    """
    Validates the X-API-Key header against the configured API_KEY in settings.
    If API_KEY is not configured in the environment (e.g. local dev), access is permitted.
    """
    settings = get_settings()
    
    # If no API key is enforced in environment, bypass check
    if not settings.API_KEY:
        return True

    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide a valid 'X-API-Key' header.",
        )

    return True

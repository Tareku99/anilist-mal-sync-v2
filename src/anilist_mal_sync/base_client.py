"""Base API client with common functionality."""

import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# HTTP Status Code Constants
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


class BaseAPIClient:
    """Base class for API clients with common request handling."""

    def __init__(self, access_token: str, base_url: str, headers: Optional[dict] = None):
        """Initialize API client with access token."""
        self.access_token = access_token
        self.base_url = base_url
        self.session = requests.Session()
        
        # Configure retry strategy for rate limits (429)
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[HTTP_TOO_MANY_REQUESTS],
            allowed_methods=["GET", "POST", "PATCH", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        default_headers = {"Authorization": f"Bearer {access_token}"}
        if headers:
            default_headers.update(headers)
        
        self.session.headers.update(default_headers)
    
    def _handle_auth_error(self, response: requests.Response, service_name: str) -> None:
        """Handle authentication errors consistently."""
        if response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            logger.error(f"{service_name} authentication failed (HTTP {response.status_code})")
            logger.error(f"{service_name} access token is invalid or expired")

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Token expiration threshold - refresh if less than 15 minutes remaining
TOKEN_REFRESH_THRESHOLD_MINUTES = 15
TOKEN_REFRESH_CHECK_INTERVAL_SECONDS = 60  # Check every minute


class TokenManager:
    """Manages OAuth2 tokens for Murex API with automatic refresh."""

    def __init__(
        self,
        username: str,
        password: str,
        group: str,
        fo_desk: str,
        load_balancer_url: str,
        verify_ssl: bool = False,
    ):
        """
        Initialize TokenManager with Murex credentials.

        Args:
            username: Murex username (e.g., "MUREXFO")
            password: Murex password
            group: Trading group (e.g., "FO_ITF")
            fo_desk: Front office desk (e.g., "FOD")
            load_balancer_url: Base URL for Murex API (e.g., "https://mx101373vm...")
            verify_ssl: Whether to verify SSL certificates (default False for self-signed)
        """
        self.username = username
        self.password = password
        self.group = group
        self.fo_desk = fo_desk
        self.load_balancer_url = load_balancer_url
        self.verify_ssl = verify_ssl

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiration: Optional[datetime] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the token manager by obtaining initial token."""
        logger.info("Initializing TokenManager...")
        self._client = httpx.AsyncClient(timeout=30.0, verify=self.verify_ssl)
        await self._obtain_token()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("TokenManager initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown the token manager and cancel refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
        logger.info("TokenManager shutdown complete")

    async def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token string

        Raises:
            RuntimeError: If token cannot be obtained or refreshed
        """
        async with self._lock:
            if self.access_token and not self._is_token_expiring_soon():
                return self.access_token

            # Token missing, expired, or expiring soon - refresh
            await self._refresh_token()
            if not self.access_token:
                raise RuntimeError("Failed to obtain valid access token")
            return self.access_token

    async def _obtain_token(self) -> None:
        """Obtain initial access token using username and password."""
        try:
            # Step 1: Get authorization code
            auth_code = await self._get_authorization_code()
            if not auth_code:
                raise RuntimeError("Failed to get authorization code")

            # Step 2: Get access token
            await self._get_access_token(auth_code)
            logger.info("Successfully obtained new access token")
        except Exception as exc:
            logger.error(f"Failed to obtain token: {exc}")
            raise

    async def _get_authorization_code(self) -> str:
        """Get OAuth2 authorization code."""
        auth_url = f"{self.load_balancer_url}/v1/api/auth/authorize"
        try:
            response = await self._client.post(
                auth_url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=(
                    "scope=openid"
                    "&response_type=code"
                    "&client_id=external-client"
                    "&redirect_uri=mx%3A//"
                ),
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logger.error(f"Failed to get authorization code: {exc}")
            raise

    async def _get_access_token(self, auth_code: str) -> None:
        """Exchange authorization code for access token."""
        token_url = f"{self.load_balancer_url}/v1/api/auth/token"
        try:
            response = await self._client.post(
                token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Bearer {auth_code}",
                },
                data=f"grant_type=authorization_code&mx_gp={self.group}&mx_fod={self.fo_desk}",
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self._parse_token_expiration(self.access_token)
        except Exception as exc:
            logger.error(f"Failed to get access token: {exc}")
            raise

    async def _refresh_token(self) -> None:
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            logger.warning("No refresh token available, obtaining new token...")
            await self._obtain_token()
            return

        token_url = f"{self.load_balancer_url}/v1/api/auth/token"
        try:
            response = await self._client.post(
                token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Bearer {self.access_token}",
                },
                data=(
                    "scope=openid"
                    "&grant_type=refresh_token"
                    f"&refresh_token={self.refresh_token}"
                    "&client_id=external-client"
                ),
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self._parse_token_expiration(self.access_token)
            logger.info("Successfully refreshed access token")
        except Exception as exc:
            logger.error(f"Failed to refresh token: {exc}")
            raise

    def _parse_token_expiration(self, token: Optional[str]) -> None:
        """
        Parse JWT token to extract expiration time.

        Args:
            token: JWT token string
        """
        if not token:
            return

        try:
            # JWT format: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                logger.warning("Invalid JWT format")
                return

            # Decode payload (add padding if needed)
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)

            if "exp" in data:
                self.token_expiration = datetime.fromtimestamp(data["exp"])
                remaining = self.token_expiration - datetime.now()
                logger.info(
                    f"Token expires at {self.token_expiration.isoformat()} "
                    f"(in {remaining.total_seconds() / 60:.1f} minutes)"
                )
        except Exception as exc:
            logger.warning(f"Could not parse token expiration: {exc}")

    def _is_token_expiring_soon(self) -> bool:
        """Check if token is expiring within the threshold."""
        if not self.token_expiration:
            return True  # Unknown expiration, refresh to be safe

        time_until_expiry = self.token_expiration - datetime.now()
        threshold = timedelta(minutes=TOKEN_REFRESH_THRESHOLD_MINUTES)
        return time_until_expiry <= threshold

    async def _refresh_loop(self) -> None:
        """Background task that periodically checks and refreshes token."""
        try:
            while True:
                await asyncio.sleep(TOKEN_REFRESH_CHECK_INTERVAL_SECONDS)
                if self._is_token_expiring_soon():
                    logger.info("Token expiring soon, triggering refresh...")
                    async with self._lock:
                        try:
                            await self._refresh_token()
                        except Exception as exc:
                            logger.error(f"Background token refresh failed: {exc}")
        except asyncio.CancelledError:
            logger.info("Token refresh loop cancelled")

    async def refresh_immediately(self) -> None:
        """Immediately refresh token (useful after 401 errors)."""
        logger.info("Immediate token refresh requested")
        async with self._lock:
            await self._refresh_token()

"""Thin async client for the mySigen cloud API.

Only covers what this integration needs: authenticate, find the station, and
read/write the time-of-use schedule.
"""

from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    EP_SCHEDULE_GET,
    EP_SCHEDULE_SAVE,
    EP_STATION_HOME,
    PERIOD_FIELDS,
    REGION_BASE_URLS,
)

_LOGGER = logging.getLogger(__name__)

# Mirrors the mySigen web app build. If auth starts failing wholesale, refresh
# these from a capture of the current web app.
WEB_APP_VERSION = "3.5.2"
WEB_APP_BUILD = "1"
WEB_APP_PACKAGE = "sigen_app"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) "
    "Gecko/20100101 Firefox/152.0"
)

# Static AES key/IV the web app uses to obscure the password before posting it.
# Hardcoded in the app bundle - obfuscation, not security.
_PASSWORD_KEY = b"sigensigensigenp"


class SigenAuthError(Exception):
    """Credentials (or region) were rejected."""


class SigenApiError(Exception):
    """The API returned something we could not use."""


def encrypt_password(password: str) -> str:
    """AES-128-CBC with key and IV both 'sigensigensigenp', base64 encoded."""
    padder = sym_padding.PKCS7(128).padder()
    data = padder.update(password.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(
        algorithms.AES(_PASSWORD_KEY), modes.CBC(_PASSWORD_KEY)
    ).encryptor()
    return base64.b64encode(encryptor.update(data) + encryptor.finalize()).decode()


class SigenClient:
    """Talks to one Sigenergy cloud region on behalf of one account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        region: str,
    ) -> None:
        if region not in REGION_BASE_URLS:
            raise ValueError(f"unknown region {region!r}")
        self._session = session
        self._username = username
        self._password = encrypt_password(password)
        self._region = region
        self._base = REGION_BASE_URLS[region]
        self._user_device_id = str(int(time.time() * 1000))
        self._session_id = str(uuid.uuid4())
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self.station_id: int | None = None
        self.station_name: str | None = None

    # ---------------------------------------------------------------- headers

    def _headers(self, content_type: str, path: str) -> dict[str, str]:
        origin = self._base.rstrip("/").replace("https://api-", "https://app-", 1)
        # The web app sends Date.now() * 1000 - microseconds, not milliseconds.
        ts = str(int(time.time() * 1000) * 1000)
        headers = {
            "Accept": "*/*",
            "Content-Type": content_type,
            "User-Agent": USER_AGENT,
            "Origin": origin,
            "Referer": f"{origin}/",
            "lang": "en_US",
            "client-server": self._region,
            "AUTH-CLIENT-ID": "sigen",
            "VERSION": "RELEASE",
            "sg-v": WEB_APP_VERSION,
            "sg-bui": WEB_APP_BUILD,
            "sg-env": "1",
            "sg-platform": "web",
            "sg-pkg": WEB_APP_PACKAGE,
            "sg-ts": ts,
            "sg-log-id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}{ts}")),
            "sg-session": self._session_id,
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    # ------------------------------------------------------------------- auth

    async def async_login(self) -> None:
        await self._token_request(
            {
                "scope": "server",
                "grant_type": "password",
                "userDeviceId": self._user_device_id,
                "username": self._username,
                "password": self._password,
            }
        )

    async def _async_refresh(self) -> None:
        try:
            await self._token_request(
                {
                    "scope": "server",
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token or "",
                }
            )
        except SigenAuthError:
            # Refresh tokens expire too; fall back to a full login.
            await self.async_login()

    async def _token_request(self, data: dict[str, str]) -> None:
        path = "auth/oauth/token"
        async with self._session.post(
            self._base + path,
            data=data,
            headers=self._headers("application/x-www-form-urlencoded", path),
            auth=aiohttp.BasicAuth("sigen", "sigen"),
        ) as resp:
            body = await resp.json(content_type=None)

        payload = (body or {}).get("data")
        if not payload or "access_token" not in payload:
            msg = (body or {}).get("msg", "no token in response")
            raise SigenAuthError(f"login failed: {msg}")

        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        # Renew a minute early so a long poll can't straddle expiry.
        self._expires_at = time.time() + float(payload.get("expires_in", 3600)) - 60

    async def _ensure_token(self) -> None:
        if not self._access_token:
            await self.async_login()
        elif time.time() >= self._expires_at:
            await self._async_refresh()

    # ---------------------------------------------------------------- request

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        await self._ensure_token()
        async with self._session.request(
            method,
            self._base + path,
            headers=self._headers("application/json", path),
            params=params,
            json=json_body,
        ) as resp:
            body = await resp.json(content_type=None)

        if not isinstance(body, dict):
            raise SigenApiError(f"{method} {path}: unexpected response {body!r}")
        code = body.get("code")
        if code != 0:
            raise SigenApiError(
                f"{method} {path}: code={code} msg={body.get('msg')!r}"
            )
        return body.get("data")

    # ------------------------------------------------------------------- API

    async def async_fetch_station(self) -> dict[str, Any]:
        data = await self._request("GET", EP_STATION_HOME) or {}
        self.station_id = data.get("stationId")
        self.station_name = data.get("stationShowName") or data.get("stationName")
        if self.station_id is None:
            raise SigenApiError("station/home returned no stationId")
        return data

    async def async_get_schedule(self) -> list[dict[str, Any]]:
        if self.station_id is None:
            await self.async_fetch_station()
        path = EP_SCHEDULE_GET.format(station_id=self.station_id)
        periods = await self._request("GET", path)
        if not isinstance(periods, list):
            raise SigenApiError(f"expected a list of periods, got {type(periods)}")
        return periods

    async def async_save_schedule(self, periods: list[dict[str, Any]]) -> None:
        """POST the whole schedule. This replaces every period - there is no
        partial update."""
        await self._request(
            "POST", EP_SCHEDULE_SAVE, json_body=self.normalise(periods)
        )

    # ----------------------------------------------------------------- helpers

    def normalise(self, periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Coerce read-back periods into exactly the shape batch/save expects."""
        out = []
        for period in periods:
            row = {key: period.get(key) for key in PERIOD_FIELDS}
            row["stationId"] = self.station_id
            row["currType"] = period.get("currType") or 1
            out.append(row)
        return out


def validate_schedule(periods: list[dict[str, Any]]) -> list[str]:
    """The backend expects the periods to tile the whole day, in order.

    Returns a list of problems; empty means it is safe to send.
    """
    if not periods:
        return ["schedule is empty"]

    errors: list[str] = []
    ordered = sorted(periods, key=lambda p: p.get("startTime") or "")

    if ordered[0].get("startTime") != "00:00":
        errors.append(f"day must start at 00:00, got {ordered[0].get('startTime')}")
    if ordered[-1].get("endTime") != "24:00":
        errors.append(f"day must end at 24:00, got {ordered[-1].get('endTime')}")
    for current, nxt in zip(ordered, ordered[1:]):
        if current.get("endTime") != nxt.get("startTime"):
            errors.append(
                f"gap or overlap between {current.get('endTime')} "
                f"and {nxt.get('startTime')}"
            )
    if len(periods) > 24:
        errors.append(f"{len(periods)} periods exceeds the 24 period limit")
    return errors

from dataclasses import dataclass
import asyncio
import ipaddress
import logging
import socket
import ssl
from time import perf_counter
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger('uvicorn.error')


@dataclass
class FetchedSource:
    url: str
    content: bytes
    content_type: str


class SourceFetchError(RuntimeError):
    pass


async def _validate_public_url(url: str) -> None:
    """Reject non-web URLs and hosts resolving to private or reserved addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise SourceFetchError('Only public HTTP(S) source URLs are supported')
    host = parts.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            info = await asyncio.get_running_loop().getaddrinfo(
                host, parts.port or (443 if parts.scheme == 'https' else 80),
                type=socket.SOCK_STREAM,
            )
        except (socket.gaierror, OSError) as exc:
            raise SourceFetchError('Source hostname could not be resolved') from exc
        addresses = [ipaddress.ip_address(entry[4][0]) for entry in info]
    if not addresses or any(not address.is_global for address in addresses):
        raise SourceFetchError('Source URL resolves to a non-public network address')


class SourceFetcher:
    def __init__(self, timeout: float = 20, max_bytes: int = 5_000_000):
        self.timeout = timeout
        self.max_bytes = max_bytes
        try:
            import truststore
            self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            self.ssl_context = ssl.create_default_context()

    async def fetch(self, url: str) -> FetchedSource:
        started = perf_counter()
        await _validate_public_url(url)
        try:
            # No automatic redirects: a public URL must not redirect to an internal host.
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
                verify=self.ssl_context,
                trust_env=False,
                headers={'User-Agent': 'NextStepAI evidence bot/1.0'},
            ) as client:
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    if response.is_redirect:
                        raise SourceFetchError('Redirected source URLs are not supported')
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self.max_bytes:
                            raise SourceFetchError('Source document exceeds size limit')
                    result = FetchedSource(str(response.url), bytes(data), response.headers.get('content-type', ''))
                    logger.info(
                        'timing stage=external_source_http duration_ms=%.1f status=%s',
                        (perf_counter() - started) * 1000, response.status_code,
                    )
                    return result
        except httpx.HTTPError as exc:
            raise SourceFetchError(f'Unable to retrieve source: {type(exc).__name__}') from exc

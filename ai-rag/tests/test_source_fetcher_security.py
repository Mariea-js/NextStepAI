import ipaddress
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.source_fetcher import SourceFetchError, _validate_public_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://127.0.0.1/internal",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/private",
    "http://[::1]/",
    "https://user:pass@example.com/",
])
@pytest.mark.asyncio
async def test_unsafe_urls_rejected(url):
    with pytest.raises(SourceFetchError):
        await _validate_public_url(url)


@pytest.mark.asyncio
async def test_public_ip_allowed():
    await _validate_public_url("https://8.8.8.8/resource")

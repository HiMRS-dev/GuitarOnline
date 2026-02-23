from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.responses import FileResponse

import app.main as main_module


@pytest.mark.asyncio
async def test_portal_page_serves_frontend_index_file() -> None:
    response = await main_module.portal_page()

    assert isinstance(response, FileResponse)
    assert Path(response.path).name == "index.html"
    assert Path(response.path).exists()

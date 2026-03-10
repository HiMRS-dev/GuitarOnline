from __future__ import annotations

from pathlib import Path


def test_nginx_overwrites_forwarded_for_header_to_prevent_spoofing() -> None:
    config = Path("ops/nginx/default.conf").read_text(encoding="utf-8")
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in config
    assert "$proxy_add_x_forwarded_for" not in config

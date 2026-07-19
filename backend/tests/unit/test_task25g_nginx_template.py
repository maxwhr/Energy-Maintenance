from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_nginx_template_has_api_proxy_spa_and_security_headers():
    text = (ROOT / "deploy/loongarch/config/nginx-energy-maintenance.conf").read_text(encoding="utf-8")
    assert "location /api/" in text
    assert "proxy_pass http://127.0.0.1:8012" in text
    assert "try_files $uri $uri/ /index.html" in text
    assert "autoindex off" in text
    assert "X-Content-Type-Options" in text


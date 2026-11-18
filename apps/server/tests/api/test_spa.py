from __future__ import annotations

import json

from app.openapi_export import main as export_main

from .conftest import INDEX, JS


def test_spa_serves_index_for_app_paths(client, dist):
    assert client.get("/app").text == INDEX
    assert client.get("/app/anything").text == INDEX


def test_spa_serves_real_files(client, dist):
    assert client.get("/assets/a.js").text == JS


def test_spa_missing_file_with_extension_404(client, dist):
    assert client.get("/assets/b.js").status_code == 404


def test_root_serves_index(client, dist):
    assert client.get("/").text == INDEX


def test_old_page_paths_serve_index(client, dist):
    for path in ("/queue", "/library", "/settings"):
        assert client.get(path).text == INDEX


def test_old_file_route_serves_index(client, dist):
    r = client.get("/downloads/1/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.text == INDEX


def test_spa_blocks_traversal(client, dist):
    assert client.get("/..%2fsecret.txt").status_code == 404
    assert client.get("/assets/..%2f..%2fsecret.txt").status_code == 404
    assert client.get("//etc/passwd").text == INDEX


def test_spa_null_byte_is_not_a_server_error(client, dist):
    assert client.get("/%00").status_code == 404
    assert client.get("/a%00b.js").status_code == 404


def test_spa_without_dist_returns_404_hint(client_no_dist):
    r = client_no_dist.get("/app")
    assert r.status_code == 404 and "pnpm build" in r.text
    assert client_no_dist.get("/health").status_code == 200
    assert client_no_dist.get("/").status_code == 404


def test_openapi_export_prints_schema(capsys):
    export_main()
    assert json.loads(capsys.readouterr().out)["openapi"].startswith("3.")

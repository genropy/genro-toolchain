"""Ported from genropy gnrpy/tests/app/cli/gnrdockerize_test.py."""

import yaml

from genro_toolchain.dockerize.compose import compose_yaml, to_yaml, traefik_labels


def test_extra_labels_empty_when_no_fqdns():
    assert traefik_labels("myapp", []) == {}


def test_extra_labels_empty_when_router_not_traefik():
    assert traefik_labels("myapp", ["myapp.local"], router="nginx") == {}


def test_extra_labels_traefik_when_fqdns():
    labels = traefik_labels("myapp", ["myapp.local"])
    assert "traefik.enable" in labels
    port = labels["traefik.http.services.myapp_svc_web.loadbalancer.server.port"]
    assert port == 8888 and isinstance(port, int)


def test_compose_minimal():
    parsed = yaml.safe_load(compose_yaml("myapp", "myapp:1.0"))
    assert parsed["services"]["myapp"]["image"] == "myapp:1.0"
    assert parsed["services"]["myapp_db"]["image"] == "postgres:latest"
    assert "labels" not in parsed["services"]["myapp"]
    assert parsed["volumes"] == {"myapp_site": {}}


def test_compose_with_traefik_labels():
    parsed = yaml.safe_load(compose_yaml("myapp", "myapp:1.0", ["a.local", "b.local"]))
    labels = parsed["services"]["myapp"]["labels"]
    assert labels["traefik.enable"] == "true"
    assert labels["traefik.http.services.myapp_svc_web.loadbalancer.server.port"] == 8888
    assert labels["traefik.http.routers.myapp_web.rule"] == (
        "(Host(`a.local`) || Host(`b.local`)) && !Path(`/websocket`)"
    )


def test_compose_dollar_var_preserved():
    raw = compose_yaml("myapp", "myapp:1.0")
    assert "${GNR_DB_HOST:-myapp_db}" in raw
    assert "${GNR_ROOTPWD:-admin}" in raw
    assert "${GNR_DB_PASSWORD:-S3cret}" in raw
    env = yaml.safe_load(raw)["services"]["myapp"]["environment"]
    assert env["GNR_DB_HOST"] == "${GNR_DB_HOST:-myapp_db}"


def test_compose_healthcheck_and_db_env():
    parsed = yaml.safe_load(compose_yaml("myapp", "myapp:1.0"))
    db = parsed["services"]["myapp_db"]
    assert db["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U genro -d myapp"]
    assert db["healthcheck"]["retries"] == 5
    assert db["environment"] == {
        "POSTGRES_PASSWORD": "S3cret",
        "POSTGRES_USER": "genro",
        "POSTGRES_DB": "myapp",
    }


def test_compose_app_ports_and_volumes():
    app = yaml.safe_load(compose_yaml("myapp", "myapp:1.0"))["services"]["myapp"]
    assert app["ports"] == ["8888:8888"]
    assert app["volumes"] == ["myapp_site:/home/genro/site/"]
    assert app["depends_on"] == {"myapp_db": {"condition": "service_healthy"}}


def test_compose_explicit_start_marker():
    assert compose_yaml("myapp", "myapp:1.0").startswith("---\n")


def test_yaml_scalars_round_trip():
    doc = {
        "plain": "abc",
        "reserved": "yes",
        "number_like": "0123",
        "colon": "a: b",
        "quote": 'say "hi"',
        "empty": "",
        "flag": True,
        "nothing": None,
        "nested": [{"k": "v"}, [1, 2], "x"],
        "empty_list": [],
    }
    assert yaml.safe_load(to_yaml(doc)) == doc

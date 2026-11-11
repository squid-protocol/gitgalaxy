"""#6572: an Elixir module name resolves to its snake_case file path (`MyApp.Accounts.User` -> my_app/accounts/user.ex)."""

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor


def _edges(token, others, importer="lib/my_app/web.ex", lang="elixir"):
    files = [{"path": importer, "lang_id": "elixir", "raw_imports": [token]}]
    files += [{"path": p, "lang_id": lang, "raw_imports": []} for p in others]
    return {dst for (_src, dst) in NetworkRiskSensor()._resolve_edges(files)}


@pytest.mark.parametrize(
    ("token", "path"),
    [
        ("MyApp.Accounts.User", "lib/my_app/accounts/user.ex"),
        ("MyApp.HTTPClient", "lib/my_app/http_client.ex"),
        ("MyApp.Repo", "lib/my_app/repo.exs"),
        ("MyAppWeb.Router", "lib/my_app_web/router.ex"),
    ],
)
def test_module_name_finds_its_snake_case_file(token, path):
    assert _edges(token, [path]) == {path}


@pytest.mark.parametrize("token", ["Enum", "Logger", "Phoenix.Controller"])
def test_stdlib_or_dependency_module_draws_no_edge(token):
    assert _edges(token, ["lib/my_app/repo.ex", "lib/my_app/logger_helper.ex"]) == set()


def test_a_name_mirroring_no_path_draws_no_edge():
    assert _edges("MyApp.Accounts.User", ["lib/user.ex"]) == set()


def test_ambiguous_match_draws_no_edge():
    paths = ["apps/a/lib/my_app/user.ex", "apps/b/lib/my_app/user.ex"]
    assert _edges("MyApp.User", paths) == set()


def test_other_languages_keep_their_behaviour():
    assert _edges("MyApp.User", ["lib/my_app/user.py"], lang="python") == set()

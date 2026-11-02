"""auth_middleware per-signal probe (#4108 slice 8): python, javascript, typescript.

Gate decorators, mixins and credential/token verification calls the rules used to miss, with near-miss
controls (definitions, bare names, hash-only calls) that must stay quiet.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

PY_FIRES = [
    "@user_passes_test(lambda u: u.is_staff)",
    "@jwt_required()",
    "@permission_classes([IsAuthenticated])",
    "class V(LoginRequiredMixin, View):",
    "class V(PermissionRequiredMixin, View):",
    "ok = check_password_hash(h, pw)",
    "ok = verify_password(pw, h)",
    "ok = bcrypt.checkpw(pw, h)",
]
PY_QUIET = [
    "h = generate_password_hash(pw)",
    "h = bcrypt.hashpw(pw, salt)",
    "x = jwt_required_flag",
    "LoginRequiredMixinFoo = 1",
    "import verify_password_utils",
]
JS_FIRES = [
    "app.use(passport.initialize());",
    "app.use(passport.session());",
    "passport.authorize('twitter')(req, res, next);",
    "app.use(expressjwt({ secret, algorithms: ['HS256'] }));",
    "const ok = await argon2.verify(hash, pw);",
    "const { payload } = await jwtVerify(token, key);",
    "const u = await auth.verifyIdToken(idToken);",
]
JS_QUIET = [
    "const h = await argon2.hash(pw);",
    "function expressjwtHelper() {}",
    "const jwtVerifyOptions = {};",
    "passport.use(strategy);",
    "const sessionStore = passport_session;",
]


def _rule(lang):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["auth_middleware"]


@pytest.mark.parametrize("text", PY_FIRES)
def test_python_missed_forms_fire(text):
    assert _rule("python").search(text), text


@pytest.mark.parametrize("text", PY_QUIET)
def test_python_near_misses_quiet(text):
    assert not _rule("python").search(text), text


@pytest.mark.parametrize("lang", ["javascript", "typescript"])
@pytest.mark.parametrize("text", JS_FIRES)
def test_js_family_missed_forms_fire(lang, text):
    assert _rule(lang).search(text), (lang, text)


@pytest.mark.parametrize("lang", ["javascript", "typescript"])
@pytest.mark.parametrize("text", JS_QUIET)
def test_js_family_near_misses_quiet(lang, text):
    assert not _rule(lang).search(text), (lang, text)


@pytest.mark.parametrize("lang", ["python", "javascript", "typescript"])
def test_redos_immune(lang):
    assert_redos_immune(_rule(lang), "passport." * 2000 + "bcrypt." * 2000)

"""
#3339: a unit's `start_idx`/`end_idx` must slice exactly that unit out of the
code stream. Every per-unit consumer (the wrapper channel's body, the
`spatial_map` bisect behind `hit_vector`) reads `code_stream[start_idx:end_idx]`,
so a span that starts or ends in the wrong place attributes other code's hits
to the unit. Run through the real PRISM -> splice path, as a scan does.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _bodies(lang, source):
    code = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(source, lang)["code_stream"]
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    bodies: dict[str, list[str]] = {}
    for func in functions:
        if not func.get("is_synthetic_slice"):
            bodies.setdefault(func["name"], []).append(code[func["start_idx"] : func["end_idx"]].strip())
    return bodies


# Mode D's nested-opener pass measured char offsets on the literal shield, which
# collapses every string to `""`, so each string char above a nested function
# slid its span back (language-crucible cosmopolitan/heavy.lua `aux`,
# nextvar.lua `mp2`).
LUA = """\
local banner = 'a long string literal that the literal shield collapses'
print("and another one, so the shielded lines are shorter")

function outer ()
  print('one more inside the enclosing function')
  local function aux ()
    print('+')
  end
  aux()
end
"""


def test_lua_nested_function_span_starts_at_its_definition():
    (body,) = _bodies("lua", LUA)["aux"]
    assert body.startswith("local function aux ()")
    assert body.endswith("end")
    assert "aux()" not in body


# The same pass serves matlab: eeglab/eeg_eval.m's `update_datafield`, a local
# function after a main function full of strings. Like eeg_eval.m, neither
# function closes with `end`, so the local one is traced by the nested pass.
MATLAB = """\
function EEG = eeg_eval(EEG)
    fprintf('a long string literal that the literal shield collapses\\n');
    disp("and another one, so the shielded lines are shorter");
    if true
        EEG = update_datafield(EEG);
    end

function EEG = update_datafield(EEG)
    if ~isfield(EEG, 'datfile'), EEG.datfile = ''; end
"""


def test_matlab_local_function_span_starts_at_its_definition():
    (body,) = _bodies("matlab", MATLAB)["update_datafield"]
    assert body.startswith("function EEG = update_datafield(EEG)")
    assert "eeg_eval" not in body


# A block-bodied arrow ended at the next func_start match, taking in the
# enclosing method's remaining statements (playwright/dispatcher.ts `collect`).
TS_BLOCK_ARROW = """\
class Scope {
  async stopPendingOperations(error: Error) {
    const controllers: Controller[] = [];
    const collect = (scope: Scope) => {
      controllers.push(scope);
    };
    collect(this);
    await Promise.all(controllers.map(controller => controller.abort(error)));
  }

  private next(error: Error) {
    return error;
  }
}
"""


def test_ts_block_bodied_arrow_ends_at_its_closing_brace():
    (body,) = _bodies("typescript", TS_BLOCK_ARROW)["collect"]
    assert body.endswith("controllers.push(scope);\n    }")
    assert "abort" not in body


# An expression-bodied arrow in an object literal ran on into the enclosing
# `catch` (vscode/lifecycle.ts `dispose`).
TS_EXPRESSION_ARROW = """\
class Refs {
  async acquire(key: string): Promise<Ref> {
    const ref = this.inner.acquire(key);
    try {
      return {
        object: ref.object,
        dispose: () => ref.dispose()
      };
    } catch (error) {
      ref.dispose();
      throw error;
    }
  }

  other(): void {
    return;
  }
}
"""


def test_ts_expression_bodied_arrow_ends_with_its_expression():
    bodies = _bodies("typescript", TS_EXPRESSION_ARROW)["dispose"]
    assert bodies == ["dispose: () => ref.dispose()"]


def test_ts_expression_arrow_ends_at_its_statement_terminator():
    source = "const double = (x: number) => x * 2;\nconsole.log('after');\nfunction next() {\n  return 1;\n}\n"
    assert _bodies("typescript", source)["double"] == ["double = (x: number) => x * 2;"]

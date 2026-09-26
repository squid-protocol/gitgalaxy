# ==============================================================================
# GitGalaxy Tool: BMS screens -> view models and web views (#3619)
#
# PURPOSE:
# A CICS program talks to its user through 3270 screens: a BMS map lays out every
# field (POS, LENGTH, ATTRB, PICIN / PICOUT, INITIAL, OCCURS, COLOR), and the
# program SENDs the map FROM its symbolic map and RECEIVEs it INTO it. The
# skeleton's `screen_bindings` (verified: BMS screen fields) join each SEND /
# RECEIVE MAP to its map's fields; this forge turns them into:
#
#   dto.screen   ScreenField (one field's geometry and attributes), ScreenCell (one
#                positioned piece of a rendered screen), ScreenModel (what every
#                screen answers: its layout, its values, its cells), and one
#                `<Map>Screen` view model per map -- a property per named field,
#                `LAYOUT` every field in screen order, labels included;
#   services     `render<Map>` per map the program SENDs and `submit<Map>(input, aid)`
#                per map it RECEIVEs (`aid` is the key the user pressed -- EIBAID),
#                each citing its COBOL lines, the business logic a TODO;
#   ui.flavour   none:          nothing more;
#                openapi-only:  a REST controller per program (GET renders a map,
#                               POST submits it, @Valid), springdoc's OpenAPI UI;
#                thymeleaf:     a web controller per program and ONE generic page
#                               (templates/screen.html) that draws any screen's
#                               cells on its 24x80 grid, with ENTER / PF3 / CLEAR.
#
# Nothing is inferred from names: a map no single BMS source defines gets no view
# model, only a TODO naming the candidates. Validation (@Size, @Pattern) comes from
# LENGTH and ATTRB=NUM, and is written only where a flavour puts the validator on the
# classpath. Every class, field and handler is recorded in the traceability manifest.
# ==============================================================================
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import (
    ClassNames,
    TraceLog,
    java_identifier,
    java_path,
    status_text,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base, java_url_segment
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import _accessors
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

SCREEN_SUBPACKAGE = "dto.screen"
CONTROLLER_SUBPACKAGE = "controller.screen"
_SHARED = ("ScreenField", "ScreenCell", "ScreenModel")


def _jstr(text: Any) -> str:
    """A Java string literal (or `null`)."""
    if text is None:
        return "null"
    return json.dumps(str(text), ensure_ascii=False)


def _attrs(f: dict) -> set[str]:
    # BMS defaults a field with no ATTRB to ASKIP (protected), NORM.
    return {a.strip().upper() for a in (f.get("attrb") or "ASKIP,NORM").split(",") if a.strip()}


def _color(f: dict) -> str | None:
    for part in (f.get("attributes") or "").split(","):
        key, _, value = part.strip().partition("=")
        if key.upper() == "COLOR" and value:
            return value.upper()
    return None


@dataclass
class ScreenProp:
    bms: dict  # the BMS field row
    java: str  # the property name
    occurs: int

    @property
    def jtype(self) -> str:
        return "List<String>" if self.occurs > 1 else "String"


@dataclass
class Screen:
    mapset: str
    map: str
    bms_file: str
    cls: str
    fields: list[dict]
    props: list[ScreenProp]
    sends: list[dict] = field(default_factory=list)  # {program key, file, line, record}
    receives: list[dict] = field(default_factory=list)


class ScreenForge:
    """Plans every BMS map the converted programs SEND or RECEIVE, once per map."""

    def __init__(self, skeletons: dict[str, dict], package: str, target: JavaTarget, names: ClassNames,
                 trace: TraceLog | None = None) -> None:  # fmt: skip
        self.package, self.target, self.names, self.trace = package, target, names, trace
        self.flavour = target.ui.flavour
        self.screens: dict[tuple[str, str, str], Screen] = {}
        self.by_program: dict[str, list[Screen]] = {}
        self.unresolved: dict[str, list[dict]] = {}  # program key -> the unresolved SEND / RECEIVE sites
        self.status: dict[str, str] = {}
        self.controllers: dict[str, str] = {}  # program key -> controller class
        for key, sk in sorted(skeletons.items()):
            section = (sk.get("sections") or {}).get("screen_bindings") or {}
            self.status[key] = status_text(section)
            for b in section.get("facts") or []:
                self._bind(key, sk["program"]["file"], b)
        if self.screens:
            for name in _SHARED:
                self.names.claim(name)
        if self.flavour != "none":
            for key in self.by_program:
                base = java_class_base(key) + "ScreenController"
                name, n = base, 1
                while name in self.names:
                    n += 1
                    name = f"{java_class_base(key)}Screen{n}Controller"
                self.controllers[key] = self.names.claim(name)

    # ---- planning ---------------------------------------------------------------
    def _bind(self, key: str, file: str, b: dict) -> None:
        site = {"key": key, "file": b.get("program") or file, "line": b.get("line"), "record": b.get("record")}
        if b.get("verb") not in ("SEND", "RECEIVE"):
            return
        if not b.get("bms_file") or not b.get("map"):
            self.unresolved.setdefault(key, []).append({**b, **site})
            return
        ident = ((b.get("mapset") or "").upper(), b["map"].upper(), b["bms_file"])
        screen = self.screens.get(ident)
        if screen is None:
            screen = self._plan(ident, b.get("fields") or [])
            self.screens[ident] = screen
        (screen.sends if b["verb"] == "SEND" else screen.receives).append(site)
        mine = self.by_program.setdefault(key, [])
        if screen not in mine:
            mine.append(screen)

    def _plan(self, ident: tuple[str, str, str], fields: list[dict]) -> Screen:
        mapset, mapname, bms_file = ident
        base = java_class_base(mapname) + "Screen"
        cls, n = base, 1
        while cls in self.names:
            n += 1
            cls = f"{java_class_base(mapset)}{base}" if n == 2 else f"{base}{n}"
        self.names.claim(cls)
        props: list[ScreenProp] = []
        seen: dict[str, int] = {}
        for f in fields:
            if not f.get("name"):
                continue  # a screen literal: in LAYOUT, not a property
            java = java_identifier(f["name"])
            seen[java] = seen.get(java, 0) + 1
            if seen[java] > 1:
                java = f"{java}{seen[java]}"
            props.append(ScreenProp(f, java, int(f.get("occurs") or 1)))
        screen = Screen(mapset, mapname, bms_file, cls, fields, props)
        if self.trace:
            first = next((f.get("line") for f in fields), None)
            path = java_path(self.package, SCREEN_SUBPACKAGE, cls)
            self.trace.record(path, "Class", "screen-view-model",
                              [{"source": f"{bms_file}:{first}", "section": "screen_bindings",
                                "item": f"MAP {mapname} MAPSET {mapset}"}])  # fmt: skip
            for p in props:
                f = p.bms
                self.trace.record(path, f"{cls}#{p.java}", "screen-field",
                                  [{"source": f"{bms_file}:{f.get('line')}", "section": "screen_bindings",
                                    "item": f"{f['name']} ({f.get('pos_line')},{f.get('pos_column')})+{f.get('length')}"}])  # fmt: skip
        return screen

    def unresolved_todos(self, key: str) -> list[str]:
        """A TODO per SEND / RECEIVE of a map no single BMS source defines; when its mapset is
        known (another site resolves a map of it), the maps that mapset does define -- CBSA's
        BNK1CCS sends MAP('BNK1CCM'), the mapset's name, whose one map is BNK1CC."""
        out = []
        for u in self.unresolved.get(key, []):
            cands = ", ".join(u.get("bms_candidates") or []) or "none in the repository"
            mapset = (u.get("mapset") or "").upper()
            maps = sorted({m for (ms, m, _f) in self.screens if ms == mapset})
            hint = f"; mapset {mapset} defines {', '.join(maps)}" if maps else ""
            out.append(f"TODO: {u.get('verb')} MAP {u.get('map') or '?'} (mapset {u.get('mapset') or '?'}) at "
                       f"{u['file']}:{u['line']}: no single BMS source defines it (candidates: {cands}){hint}")  # fmt: skip
        return out

    # ---- Java: shared types -------------------------------------------------------
    def _shared_sources(self) -> dict[str, str]:
        pkg = f"{self.package}.{SCREEN_SUBPACKAGE}"
        field_src = f"""package {pkg};

/**
 * One BMS field (DFHMDF) of a map: where it sits on the 3270 screen and how it behaves (#3619).
 * `name` is null for a screen literal (a label, which never reaches the symbolic map); `line` / `column`
 * are POS=(line,column) -- the attribute byte, so the data starts one column after it; `input` is
 * ATTRB=UNPROT, `numeric` ATTRB=NUM, `bright` BRT, `dark` DRK, `cursor` IC; `initial` the INITIAL text;
 * `occurs` the OCCURS count (1 without one).
 */
public record ScreenField(String name, int line, int column, int length, boolean input, boolean numeric,
                          boolean bright, boolean dark, boolean cursor, String initial, String color, int occurs) {{
}}
"""
        cell_src = f"""package {pkg};

/**
 * One positioned piece of a rendered screen (#3619): a label, an output field or an input box.
 * `key` is the form key of an input (the property name, `name.n` for the n-th occurrence), else null;
 * `line` is 1-based, `column` the 0-based column the data starts in; `css` the classes that style it.
 */
public record ScreenCell(String key, int line, int column, int length, boolean input, String text, String css,
                         boolean cursor) {{
}}
"""
        model_src = f"""package {pkg};

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * What every BMS screen view model answers (#3619): its mapset and map, its fields in screen order
 * (labels included), and the current values of its named fields keyed as a form posts them.
 */
public interface ScreenModel {{

    String mapsetName();

    String mapName();

    List<ScreenField> screenLayout();

    Map<String, String> screenValues();

    /** The screen as positioned cells: every label, output field and input box, OCCURS expanded. */
    default List<ScreenCell> screenCells() {{
        Map<String, String> values = screenValues();
        List<ScreenCell> cells = new ArrayList<>();
        for (ScreenField f : screenLayout()) {{
            String css = "f" + (f.input() ? " in" : "") + (f.bright() ? " brt" : "") + (f.dark() ? " drk" : "")
                    + (f.color() != null ? " c-" + f.color().toLowerCase() : "");
            for (int i = 0; i < f.occurs(); i++) {{
                String key = f.name() == null ? null : (f.occurs() > 1 ? f.name() + "." + (i + 1) : f.name());
                String text = key == null ? (f.initial() == null ? "" : f.initial()) : values.getOrDefault(key, "");
                int column = f.column() + i * (f.length() + 1);
                cells.add(new ScreenCell(f.input() ? key : null, f.line(), column, f.length(), f.input() && key != null,
                        f.dark() ? "" : text, css, f.cursor() && i == 0));
            }}
        }}
        return cells;
    }}
}}
"""
        return {"ScreenField": field_src, "ScreenCell": cell_src, "ScreenModel": model_src}

    # ---- Java: a view model -------------------------------------------------------
    def _prop_lines(self, s: Screen, p: ScreenProp) -> list[str]:
        f, attrs = p.bms, _attrs(p.bms)
        sym = ", ".join(f"{f['name']}{sfx}" for sfx in ("I", "O"))
        extra = []
        if f.get("picin") or f.get("picout"):
            extra.append(f"PICIN={f.get('picin') or '-'} PICOUT={f.get('picout') or '-'}")
        if p.occurs > 1:
            extra.append(f"OCCURS={p.occurs}")
        doc = (f"    /** {f['name']}: ({f.get('pos_line')},{f.get('pos_column')}), {f.get('length')} bytes, "
               f"ATTRB={','.join(sorted(attrs))}{'; ' + '; '.join(extra) if extra else ''} -- {s.bms_file}:{f.get('line')}."
               f" Symbolic map {sym}. */")  # fmt: skip
        out = [doc]
        validate = self.flavour != "none" and "UNPROT" in attrs
        anns = []
        if validate and f.get("length"):
            anns.append(f"@Size(max = {int(f['length'])})")
        if validate and "NUM" in attrs:
            anns.append('@Pattern(regexp = "[0-9 ]*")')
        if p.occurs > 1:
            inner = " ".join([*anns, "String"])
            out.append(f"    private List<{inner}> {p.java};\n")
        else:
            out += [f"    {a}" for a in anns]
            out.append(f"    private String {p.java};\n")
        return out

    def view_model_source(self, s: Screen) -> str:
        pkg = f"{self.package}.{SCREEN_SUBPACKAGE}"
        lombok = self.target.lombok
        imports = ["java.util.ArrayList", "java.util.LinkedHashMap", "java.util.List", "java.util.Map"]
        if self.flavour != "none" and any("UNPROT" in _attrs(p.bms) for p in s.props):
            imports += ["jakarta.validation.constraints.Pattern", "jakarta.validation.constraints.Size"]
        if lombok:
            imports += ["lombok.Data", "lombok.NoArgsConstructor"]
        sends = ", ".join(f"{x['file']}:{x['line']}" for x in s.sends) or "no SEND"
        receives = ", ".join(f"{x['file']}:{x['line']}" for x in s.receives) or "no RECEIVE"
        status = next((self.status[x["key"]] for x in s.sends + s.receives), "untested")
        java = [f"package {pkg};\n"] + [f"import {i};" for i in sorted(imports)] + [""]
        java += ["/**",
                 f" * BMS map {s.map} of mapset {s.mapset} ({s.bms_file}): the screen as a view model (#3619).",
                 f" * SEND at {sends}; RECEIVE at {receives}.",
                 f" * One property per named field (symbolic map {s.map}I / {s.map}O); LAYOUT is every field in",
                 " * screen order, labels included. BMS screen fields field testing: " + status + ".",
                 " */"]  # fmt: skip
        if lombok:
            java += ["@Data", "@NoArgsConstructor"]
        java.append(f"public class {s.cls} implements ScreenModel {{\n")
        java += [f"    public static final String MAPSET = {_jstr(s.mapset)};",
                 f"    public static final String MAP = {_jstr(s.map)};",
                 "    public static final List<ScreenField> LAYOUT = List.of("]  # fmt: skip
        rows = []
        for f in s.fields:
            a = _attrs(f)
            rows.append(
                f"            new ScreenField({_jstr(f.get('name'))}, {int(f.get('pos_line') or 0)}, "
                f"{int(f.get('pos_column') or 0)}, {int(f.get('length') or 0)}, {str('UNPROT' in a).lower()}, "
                f"{str('NUM' in a).lower()}, {str('BRT' in a).lower()}, {str('DRK' in a).lower()}, "
                f"{str('IC' in a).lower()}, {_jstr(f.get('initial'))}, {_jstr(_color(f))}, {int(f.get('occurs') or 1)})"
            )
        java.append(",\n".join(rows) + ");\n")
        for p in s.props:
            java += self._prop_lines(s, p)
        if not lombok:
            java += _accessors(s.cls, [(p.jtype, p.java) for p in s.props])
        java += [
            "    @Override", "    public String mapsetName() {", "        return MAPSET;", "    }", "",
            "    @Override", "    public String mapName() {", "        return MAP;", "    }", "",
            "    @Override", "    public List<ScreenField> screenLayout() {", "        return LAYOUT;", "    }", "",
            "    @Override", "    public Map<String, String> screenValues() {",
            "        Map<String, String> values = new LinkedHashMap<>();",
        ]  # fmt: skip
        for p in s.props:
            name = p.bms["name"]
            if p.occurs > 1:
                java += [f"        if ({p.java} != null) {{",
                         f"            for (int i = 0; i < {p.java}.size(); i++) {{",
                         f"                values.put({_jstr(name)} + \".\" + (i + 1), {p.java}.get(i));",
                         "            }", "        }"]  # fmt: skip
            else:
                java.append(f"        values.put({_jstr(name)}, {p.java});")
        java += ["        return values;", "    }", "",
                 "    /** A view model from posted form values (keys as `screenValues` writes them). */",
                 f"    public static {s.cls} fromValues(Map<String, String> values) {{",
                 f"        {s.cls} screen = new {s.cls}();"]  # fmt: skip
        for p in s.props:
            name, setter = p.bms["name"], "set" + p.java[0].upper() + p.java[1:]
            if p.occurs > 1:
                java += ["        {", "            List<String> items = new ArrayList<>();",
                         f"            for (int i = 1; i <= {p.occurs}; i++) {{",
                         f"                items.add(values.get({_jstr(name)} + \".\" + i));", "            }",
                         f"            screen.{setter}(items);", "        }"]  # fmt: skip
            else:
                java.append(f"        screen.{setter}(values.get({_jstr(name)}));")
        java += ["        return screen;", "    }", "}"]
        return "\n".join(java) + "\n"

    # ---- Java: service handlers ---------------------------------------------------
    def service_extras(self, key: str) -> dict | None:
        screens = self.by_program.get(key, [])
        todos = self.unresolved_todos(key)
        if not screens and not todos:
            return None
        pkg = f"{self.package}.{SCREEN_SUBPACKAGE}"
        imports = [f"import {pkg}.{s.cls};" for s in screens]
        if any(any(r["key"] == key for r in s.receives) for s in screens):
            imports.append(f"import {pkg}.ScreenModel;")
        methods: list[str] = []
        svc = f"{java_class_base(key)}Service"
        status = self.status.get(key, "untested")
        for s in screens:
            sends = [x for x in s.sends if x["key"] == key]
            receives = [x for x in s.receives if x["key"] == key]
            if sends:
                where = ", ".join(f"{x['file']}:{x['line']}" for x in sends)
                rec = sorted({x["record"] for x in sends if x["record"]}) or [f"{s.map}O (the default)"]
                methods += [
                    f"    /** SEND MAP({s.map}) MAPSET({s.mapset}) FROM({', '.join(rec)}) at {where} (#3619).",
                    f"     *  TODO: port the logic that fills {', '.join(rec)} before the SEND.",
                    f"     *  BMS screen fields field testing: {status}. */",
                    f"    public {s.cls} render{java_class_base(s.map)}({s.cls} screen) {{",
                    "        return screen;",
                    "    }\n",
                ]
                if self.trace:
                    self.trace.record(java_path(self.package, "service", svc), f"{svc}#render{java_class_base(s.map)}",
                                      "screen-send", [{"source": f"{x['file']}:{x['line']}", "section": "screen_bindings"}
                                                      for x in sends],
                                      [f"TODO: port the logic that fills {', '.join(rec)} before the SEND"])  # fmt: skip
            if receives:
                where = ", ".join(f"{x['file']}:{x['line']}" for x in receives)
                rec = sorted({x["record"] for x in receives if x["record"]}) or [f"{s.map}I (the default)"]
                back = f"render{java_class_base(s.map)}(input)" if sends else "input"
                methods += [
                    f"    /** RECEIVE MAP({s.map}) MAPSET({s.mapset}) INTO({', '.join(rec)}) at {where} (#3619).",
                    "     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.",
                    f"     *  TODO: port the logic that reads {', '.join(rec)} after the RECEIVE, and return the "
                    "screen to show next.",
                    f"     *  BMS screen fields field testing: {status}. */",
                    f"    public ScreenModel submit{java_class_base(s.map)}({s.cls} input, String aid) {{",
                    f"        return {back};",
                    "    }\n",
                ]
                if self.trace:
                    self.trace.record(java_path(self.package, "service", svc), f"{svc}#submit{java_class_base(s.map)}",
                                      "screen-receive", [{"source": f"{x['file']}:{x['line']}",
                                                          "section": "screen_bindings"} for x in receives],
                                      [f"TODO: port the logic that reads {', '.join(rec)} after the RECEIVE"])  # fmt: skip
        doc = [f"Screens (#3619): {', '.join(s.cls for s in screens) or 'none resolved'}.", *todos]
        return {"imports": imports, "methods": methods, "class_doc": doc}

    # ---- Java: controllers --------------------------------------------------------
    def controller_source(self, key: str) -> str:
        screens = self.by_program[key]
        cls, svc = self.controllers[key], f"{java_class_base(key)}Service"
        var = svc[0].lower() + svc[1:]
        pkg, spkg = f"{self.package}.{CONTROLLER_SUBPACKAGE}", f"{self.package}.{SCREEN_SUBPACKAGE}"
        thymeleaf = self.flavour == "thymeleaf"
        imports = {f"{self.package}.service.{svc}", f"{spkg}.ScreenModel", *(f"{spkg}.{s.cls}" for s in screens)}
        if thymeleaf:
            imports |= {"java.util.Map", "org.springframework.stereotype.Controller", "org.springframework.ui.Model",
                        "org.springframework.web.bind.annotation.GetMapping",
                        "org.springframework.web.bind.annotation.PostMapping",
                        "org.springframework.web.bind.annotation.RequestMapping",
                        "org.springframework.web.bind.annotation.RequestParam"}  # fmt: skip
            base = f"/screens/{java_url_segment(key)}"
        else:
            imports |= {"jakarta.validation.Valid", "org.springframework.web.bind.annotation.GetMapping",
                        "org.springframework.web.bind.annotation.PostMapping",
                        "org.springframework.web.bind.annotation.RequestBody",
                        "org.springframework.web.bind.annotation.RequestMapping",
                        "org.springframework.web.bind.annotation.RequestParam",
                        "org.springframework.web.bind.annotation.RestController"}  # fmt: skip
            base = f"/api/v1/{java_url_segment(key)}/screens"
        if self.target.lombok:
            imports.add("lombok.RequiredArgsConstructor")
        java = [f"package {pkg};\n"] + [f"import {i};" for i in sorted(imports)] + [""]
        what = (
            "web pages (Thymeleaf: templates/screen.html)"
            if thymeleaf
            else "REST endpoints (OpenAPI: /swagger-ui.html)"
        )
        java += ["/**", f" * The BMS screens of {key.upper()} as {what} (#3619): GET shows a map",
                 " * (the service's render), POST submits it with the key pressed (the service's submit) and shows",
                 " * the screen the service returns.", " */"]  # fmt: skip
        java += ["@Controller" if thymeleaf else "@RestController", f'@RequestMapping("{base}")']
        if self.target.lombok:
            java.append("@RequiredArgsConstructor")
        java += [f"public class {cls} {{\n", f"    private final {svc} {var};\n"]
        if not self.target.lombok:
            java += [f"    public {cls}({svc} {var}) {{", f"        this.{var} = {var};", "    }\n"]
        for s in screens:
            m = java_class_base(s.map)
            path = s.map.lower()
            sends = any(x["key"] == key for x in s.sends)
            receives = any(x["key"] == key for x in s.receives)
            shown = f"{var}.render{m}(new {s.cls}())" if sends else f"new {s.cls}()"
            if thymeleaf:
                java += [f'    @GetMapping("/{path}")', f"    public String show{m}(Model model) {{",
                         f'        return page(model, {shown}, "{base}/{path}");', "    }\n"]  # fmt: skip
                if receives:
                    java += [f'    @PostMapping("/{path}")',
                             f"    public String submit{m}(@RequestParam Map<String, String> form,",
                             '            @RequestParam(name = "aid", defaultValue = "ENTER") String aid, Model model) {',
                             f"        ScreenModel next = {var}.submit{m}({s.cls}.fromValues(form), aid);",
                             f'        return page(model, next, "{base}/{path}");', "    }\n"]  # fmt: skip
            else:
                java += [f'    @GetMapping("/{path}")', f"    public {s.cls} show{m}() {{",
                         f"        return {shown};", "    }\n"]  # fmt: skip
                if receives:
                    java += [f'    @PostMapping("/{path}")',
                             f"    public ScreenModel submit{m}(@Valid @RequestBody {s.cls} input,",
                             '            @RequestParam(name = "aid", defaultValue = "ENTER") String aid) {',
                             f"        return {var}.submit{m}(input, aid);", "    }\n"]  # fmt: skip
            if self.trace:
                self.trace.record(java_path(self.package, CONTROLLER_SUBPACKAGE, cls), f"{cls}#show{m}",
                                  "screen-endpoint", [{"source": f"{x['file']}:{x['line']}", "section": "screen_bindings"}
                                                      for x in s.sends + s.receives if x["key"] == key])  # fmt: skip
        if thymeleaf:
            java += ["    private String page(Model model, ScreenModel screen, String action) {",
                     '        model.addAttribute("screen", screen);',
                     '        model.addAttribute("cells", screen.screenCells());',
                     '        model.addAttribute("action", action);',
                     '        return "screen";', "    }"]  # fmt: skip
        java.append("}")
        return "\n".join(java) + "\n"

    # ---- output -------------------------------------------------------------------
    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        if not self.screens:
            return {}
        models = self._shared_sources()
        models.update({s.cls: self.view_model_source(s) for s in self.screens.values()})
        out: dict[tuple[str, ...], dict[str, str]] = {("dto", "screen"): models}
        if self.controllers:
            out[("controller", "screen")] = {c: self.controller_source(k) for k, c in self.controllers.items()}
        return out

    def resources(self) -> dict[str, str]:
        """Non-Java files under src/main/resources, by relative path."""
        if self.flavour != "thymeleaf" or not self.screens:
            return {}
        return {"templates/screen.html": SCREEN_TEMPLATE}

    def audit_line(self) -> str:
        n_fields = sum(len(s.props) for s in self.screens.values())
        sends = sum(len(s.sends) for s in self.screens.values())
        receives = sum(len(s.receives) for s in self.screens.values())
        unresolved = sum(len(v) for v in self.unresolved.values())
        return (f"  • BMS screens (#3619)      : {len(self.screens)} view models ({n_fields} fields) for "
                f"{len(self.by_program)} programs; {sends} SEND / {receives} RECEIVE sites; {unresolved} unresolved "
                f"maps; UI: {self.flavour}\n")  # fmt: skip


# One page for every screen: the controller hands it `cells` (ScreenModel.screenCells) and `action`.
SCREEN_TEMPLATE = """<!DOCTYPE html>
<!-- #3619: every BMS screen, drawn from its cells on the 24x80 grid. Generated by GitGalaxy. -->
<html xmlns:th="http://www.thymeleaf.org">
<head>
  <meta charset="utf-8">
  <title th:text="${screen.mapsetName() + ' / ' + screen.mapName()}">screen</title>
  <style>
    body { background: #111; font-family: monospace; }
    .screen { position: relative; width: 81ch; height: 30em; background: #000; color: #3c3; line-height: 1.25em; }
    .f { position: absolute; white-space: pre; }
    .brt { font-weight: bold; }
    input.f { background: #000; color: #3cf; border: none; border-bottom: 1px solid #3c3; font: inherit; padding: 0; }
    .c-blue { color: #58f; } .c-red { color: #f55; } .c-pink { color: #f6c; } .c-green { color: #3c3; }
    .c-turquoise { color: #3cc; } .c-yellow { color: #ee3; } .c-neutral { color: #ddd; }
    .keys { margin-top: 1em; }
  </style>
</head>
<body>
<form method="post" th:action="${action}">
  <div class="screen">
    <th:block th:each="c : ${cells}">
      <input th:if="${c.input()}" type="text" th:class="${c.css()}" th:name="${c.key()}" th:value="${c.text()}"
             th:attr="maxlength=${c.length()},size=${c.length()}" th:autofocus="${c.cursor()}"
             th:style="|top: ${(c.line() - 1) * 1.25}em; left: ${c.column()}ch;|">
      <span th:unless="${c.input()}" th:class="${c.css()}" th:text="${c.text()}"
            th:style="|top: ${(c.line() - 1) * 1.25}em; left: ${c.column()}ch;|"></span>
    </th:block>
  </div>
  <div class="keys">
    <button type="submit" name="aid" value="ENTER">Enter</button>
    <button type="submit" name="aid" value="PF3">PF3</button>
    <button type="submit" name="aid" value="CLEAR">Clear</button>
  </div>
</form>
</body>
</html>
"""

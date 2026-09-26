// TypeScript call-graph reference for tests/tools/call_graph_resolution.py
// (Level 2, the `typescript` mode). pyan3 plays this role for Python.
//
// The TypeScript compiler's own type checker resolves every call in the repo:
// for `x.save()` it knows x's type, so it knows WHICH `save` runs. That makes
// it a much stronger reference than a name-matching tool, though still not
// ground truth: an `any` receiver or an unresolved import leaves it silent.
//
//   node tests/tools/ts_callgraph.js <repo>   > graph.json
//
// Needs the `typescript` package on NODE_PATH (CI pins it; the Python side
// passes `npm root -g` when NODE_PATH is unset). Output:
//   version   the typescript version that produced it
//   defs      [path, name, line] for every named function-like with a body
//   edges     [caller, callee] pairs, each a def key
//   external  [caller, callee name] pairs whose call the checker resolved
//             ONLY to declarations outside the repo (lib.d.ts, node_modules):
//             `str.trim()` is String.prototype.trim, whatever the repo defines
// A key's line is where the declaration starts (the `const f =` line for an
// arrow or function expression bound to a name), 1-based.
"use strict";
const ts = require("typescript");
const fs = require("fs");
const path = require("path");

// TypeScript 7 (the native Go port) ships no JavaScript compiler API: its
// package exports neither createProgram nor a type checker. The reference
// needs a 6.x (or earlier) package, which is what CI pins.
if (typeof ts.createProgram !== "function") {
  process.stderr.write(
    `ts_callgraph: typescript ${ts.version} on NODE_PATH has no JavaScript compiler API (7.x is the native port); ` +
      "install typescript@6.0.2\n",
  );
  process.exit(3);
}

const repo = path.resolve(process.argv[2] || ".");
const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "build", "out", "coverage"]);
const SOURCE = /\.(c|m)?tsx?$/;
const DECLARATION = /\.d\.(c|m)?ts$/;

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.isFile() && SOURCE.test(e.name) && !DECLARATION.test(e.name)) out.push(p);
  }
  return out;
}

// The repo's own root tsconfig (module resolution, customConditions, paths),
// with every source file as a root: the reference must see the files the
// engine scans, not only the ones a build includes.
function compilerOptions() {
  const cfg = ts.findConfigFile(repo, ts.sys.fileExists, "tsconfig.json");
  let options = {};
  if (cfg && path.dirname(cfg) === repo) {
    const read = ts.readConfigFile(cfg, ts.sys.readFile);
    if (!read.error) options = ts.parseJsonConfigFileContent(read.config, ts.sys, repo).options;
  }
  return Object.assign(
    { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.NodeNext, moduleResolution: ts.ModuleResolutionKind.NodeNext },
    options,
    { noEmit: true, skipLibCheck: true, allowJs: false, types: [], jsx: ts.JsxEmit.Preserve },
  );
}

const files = walk(repo, []).sort();
const program = ts.createProgram(files, compilerOptions());
const checker = program.getTypeChecker();
// The compiler reports file names with forward slashes on every platform.
const fold = (p) => (process.platform === "win32" ? p.toLowerCase() : p);
const repoPrefix = fold(repo.split(path.sep).join("/") + "/");
const inRepo = (sf) =>
  !!sf && !sf.isDeclarationFile && fold(sf.fileName).startsWith(repoPrefix) && !sf.fileName.includes("/node_modules/");

function unwrap(e) {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression?.(e)) {
    e = e.expression;
  }
  return e;
}

function nameOf(node) {
  if (ts.isConstructorDeclaration(node)) return "constructor";
  if (ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node) || ts.isGetAccessor(node) || ts.isSetAccessor(node)) {
    return node.name ? node.name.getText() : null;
  }
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
    if (ts.isFunctionExpression(node) && node.name) return node.name.text;
    let p = node.parent;
    while (ts.isParenthesizedExpression(p) || ts.isAsExpression(p)) p = p.parent;
    if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
    if ((ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p)) && p.name) return p.name.getText();
    // `inst._zod.parse = (payload) => ...`: the member it is assigned to
    if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken && p.right === node) {
      const left = unwrap(p.left);
      if (ts.isPropertyAccessExpression(left)) return left.name.text;
      if (ts.isIdentifier(left)) return left.text;
    }
  }
  return null;
}

function keyOf(node) {
  const name = nameOf(node);
  if (!name) return null;
  const sf = node.getSourceFile();
  let anchor = node;
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
    anchor = node.parent;
    while (ts.isParenthesizedExpression(anchor) || ts.isAsExpression(anchor)) anchor = anchor.parent;
  }
  const line = sf.getLineAndCharacterOfPosition(anchor.getStart(sf)).line + 1;
  return [path.relative(repo, sf.fileName).split(path.sep).join("/"), name, line];
}

// The function a declaration names: itself, a bound arrow/function
// expression, or a class's constructor (`new Foo()` runs it).
function functionOf(decl) {
  if (ts.isFunctionDeclaration(decl) || ts.isMethodDeclaration(decl) || ts.isConstructorDeclaration(decl)) {
    return decl.body ? decl : null; // an overload signature has no body
  }
  if (ts.isGetAccessor(decl) || ts.isSetAccessor(decl)) return decl.body ? decl : null;
  if ((ts.isVariableDeclaration(decl) || ts.isPropertyAssignment(decl) || ts.isPropertyDeclaration(decl)) && decl.initializer) {
    const init = unwrap(decl.initializer);
    if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) return init;
  }
  if (ts.isClassDeclaration(decl) || ts.isClassExpression(decl)) {
    return decl.members.find((m) => ts.isConstructorDeclaration(m) && m.body) || null;
  }
  return null;
}

// -> {keys: in-repo function keys, external: true when every declaration is outside the repo}
function resolve(call) {
  const e = unwrap(call.expression);
  const id = ts.isPropertyAccessExpression(e) ? e.name : e;
  let sym = checker.getSymbolAtLocation(id);
  if (!sym) return { keys: [], external: false };
  if (sym.flags & ts.SymbolFlags.Alias) {
    try {
      sym = checker.getAliasedSymbol(sym);
    } catch {
      return { keys: [], external: false };
    }
  }
  const decls = sym.declarations || [];
  const keys = [];
  for (const d of decls) {
    if (!inRepo(d.getSourceFile())) continue;
    const fn = functionOf(d);
    const k = fn && keyOf(fn);
    if (k) keys.push(k);
  }
  const external = decls.length > 0 && decls.every((d) => !inRepo(d.getSourceFile()));
  return { keys, external, name: id.getText ? id.getText() : null };
}

const defs = [];
const edges = new Map();
const external = new Map();
for (const sf of program.getSourceFiles()) {
  if (!inRepo(sf)) continue;
  const stack = []; // enclosing NAMED functions; an anonymous callback's calls belong to its enclosing one
  const visit = (node) => {
    let pushed = false;
    if (ts.isFunctionLike(node) && node.body !== undefined) {
      const k = keyOf(node);
      if (k) {
        defs.push(k);
        stack.push(k);
        pushed = true;
      }
    }
    if ((ts.isCallExpression(node) || ts.isNewExpression(node)) && stack.length) {
      const src = stack[stack.length - 1];
      const r = resolve(node);
      for (const dst of r.keys) {
        const s = JSON.stringify([src, dst]);
        if (JSON.stringify(src) !== JSON.stringify(dst)) edges.set(s, [src, dst]);
      }
      if (r.external && r.name) external.set(JSON.stringify([src, r.name]), [src, r.name]);
    }
    ts.forEachChild(node, visit);
    if (pushed) stack.pop();
  };
  visit(sf);
}

process.stdout.write(
  JSON.stringify({
    version: ts.version,
    files: files.length,
    defs,
    edges: [...edges.values()],
    external: [...external.values()],
  }),
);

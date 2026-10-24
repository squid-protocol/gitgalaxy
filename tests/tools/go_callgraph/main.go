// Go call-graph reference for tests/tools/callgraph_refs.py (#3782, epic #3772).
//
//	go run -C tests/tools/go_callgraph . <repo>   > graph.json
//
// Type-checks every package, tests included (the engine scans _test.go too) of <repo>, builds SSA, and takes the call
// graph of golang.org/x/tools/go/callgraph/vta over a CHA seed: static calls,
// interface and func-value calls narrowed to the concrete types that reach them.
// Output is the contract of callgraph_refs.py:
//
//	{"tool":"go-callgraph","files":N,"defs":[[path,name,line]],
//	 "edges":[[caller,callee,line]],"external":[[caller,calleeName]]}
//
// A def is a named function or method with a body, named bare (`Execute`, not
// `Command.Execute`) at the line of its `func` keyword, as the engine reports it.
// A closure's calls belong to its enclosing named function. Build tags are the
// host's (GOOS/GOARCH of the machine running it).
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/cha"
	"golang.org/x/tools/go/callgraph/vta"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

type key [3]any // path, name, line

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: go_callgraph <repo>")
		os.Exit(2)
	}
	repo, err := filepath.Abs(os.Args[1])
	if err != nil {
		fail(err)
	}
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedSyntax | packages.NeedTypes |
			packages.NeedTypesInfo | packages.NeedImports | packages.NeedDeps | packages.NeedModule,
		Dir:   repo,
		Tests: true,
		Env:   append(os.Environ(), "GOWORK=off", "GOTOOLCHAIN=local"),
	}
	pkgs, err := packages.Load(cfg, "./...")
	if err != nil {
		fail(err)
	}
	prog, _ := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()

	inRepo := func(file string) (string, bool) {
		rel, err := filepath.Rel(repo, file)
		if err != nil || strings.HasPrefix(rel, "..") {
			return "", false
		}
		rel = filepath.ToSlash(rel)
		if strings.HasPrefix(rel, "vendor/") || strings.Contains(rel, "/vendor/") {
			return "", false
		}
		return rel, true
	}

	// named: the named, bodied function a ssa.Function belongs to (a closure -> its
	// enclosing one), or nil for a synthetic wrapper, a package initialiser or a
	// function outside the repo.
	named := func(fn *ssa.Function) *key {
		for fn != nil && fn.Parent() != nil {
			fn = fn.Parent()
		}
		if fn == nil {
			return nil
		}
		if o := fn.Origin(); o != nil {
			fn = o // a generic instantiation -> its declaration
		}
		decl, ok := fn.Syntax().(*ast.FuncDecl)
		if !ok || decl.Body == nil {
			return nil
		}
		pos := prog.Fset.Position(decl.Pos())
		rel, ok := inRepo(pos.Filename)
		if !ok {
			return nil
		}
		return &key{rel, decl.Name.Name, pos.Line}
	}

	defs := map[key]bool{}
	files := map[string]bool{}
	for fn := range ssautil.AllFunctions(prog) {
		if k := named(fn); k != nil {
			defs[*k] = true
			files[k[0].(string)] = true
		}
	}
	for _, p := range pkgs {
		for _, f := range p.GoFiles {
			if rel, ok := inRepo(f); ok {
				files[rel] = true
			}
		}
	}

	graph := vta.CallGraph(ssautil.AllFunctions(prog), cha.CallGraph(prog))
	type edge struct {
		src, dst key
	}
	first := map[edge]int{}
	external := map[[2]any]bool{}
	var extKeys [][2]any
	_ = callgraph.GraphVisitEdges(graph, func(e *callgraph.Edge) error {
		src := named(e.Caller.Func)
		if src == nil {
			return nil
		}
		callee := e.Callee.Func
		if callee.Synthetic != "" && callee.Parent() == nil && callee.Origin() == nil {
			return nil // a wrapper (bound method, thunk), not a function
		}
		line := 0
		if e.Site != nil {
			line = prog.Fset.Position(e.Site.Pos()).Line
		}
		if dst := named(callee); dst != nil {
			if *dst == *src {
				return nil
			}
			ed := edge{*src, *dst}
			if old, ok := first[ed]; !ok || (line > 0 && line < old) {
				first[ed] = line
			}
			return nil
		}
		if callee.Parent() != nil || callee.Name() == "init" {
			return nil
		}
		// resolved to a function with no body in the repo: outside it
		ext := [2]any{*src, callee.Name()}
		if !external[ext] {
			external[ext] = true
			extKeys = append(extKeys, ext)
		}
		return nil
	})

	out := struct {
		Tool     string  `json:"tool"`
		Files    int     `json:"files"`
		Defs     [][]any `json:"defs"`
		Edges    [][]any `json:"edges"`
		External [][]any `json:"external"`
	}{Tool: "go-callgraph", Files: len(files), Defs: [][]any{}, Edges: [][]any{}, External: [][]any{}}
	for k := range defs {
		out.Defs = append(out.Defs, []any{k[0], k[1], k[2]})
	}
	for e, line := range first {
		out.Edges = append(out.Edges, []any{e.src[:], e.dst[:], line})
	}
	for _, e := range extKeys {
		k := e[0].(key)
		out.External = append(out.External, []any{k[:], e[1]})
	}
	sortRows(out.Defs)
	sortRows(out.Edges)
	sortRows(out.External)
	enc := json.NewEncoder(os.Stdout)
	if err := enc.Encode(out); err != nil {
		fail(err)
	}
}

func sortRows(rows [][]any) {
	sort.Slice(rows, func(i, j int) bool {
		a, _ := json.Marshal(rows[i])
		b, _ := json.Marshal(rows[j])
		return string(a) < string(b)
	})
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "go_callgraph:", err)
	os.Exit(1)
}

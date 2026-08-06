import sys
sys.path.insert(0, "/home/joe/nyx_projects/gitgalaxy")
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

test_cases = [
    # structural boundaries
    ('structural_boundaries', 'map[string]int', 'map_name'),
    ('structural_boundaries', '<-chan int', 'channel'),
    ('structural_boundaries', 'go func(){}()', 'going'),
    ('structural_boundaries', 'defer f.Close()', 'deferred'),
    # class_start
    ('class_start', 'type Foo[T map[string]int] struct {', 'type Foo[T map[string]int] func()'),
    ('class_start', 'type \n Foo \n [T map[string]int] \n struct {', 'type \n Foo \n int'),
    # func_start
    ('func_start', 'func Foo[T map[string]int](x T) {', 'func(x int) {'),
    ('func_start', 'func (s *Server[T]) Foo[U []int](x U) {', 'func_name()'),
    ('func_start', 'func \n(s *Server)\nFoo\n[T map[string]int]\n(x T) {', 'myfunc Foo() {'),
    # args
    ('args', 'func Foo[T map[string]int](x T)', 'func_name(x int)'),
    ('args', 'func (s *Server[T]) Foo[U []int](x U)', 'func Foo()'), # Wait, args matches func Foo() without parameters? `\([^)]*\)` matches `()`.
    # branch
    ('branch', 'else if true {', 'else_case'),
    ('branch', 'case <-ch:', 'mycase := 1'),
    ('branch', 'for k, v := range m {', 'for_loop'),
    ('branch', 'goto L', 'gotoclass'),
]

for sig, pos, neg in test_cases:
    pat = GO_RULES[sig]
    print(sig, "POS", bool(pat.search(pos)), "NEG", not bool(pat.search(neg)))

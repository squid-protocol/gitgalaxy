import re
import sys
import os

# Add to sys.path to avoid PYTHONPATH issues
sys.path.insert(0, "/home/joe/nyx_projects/gitgalaxy")
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

def run_tests():
    fs = GO_RULES["func_start"]
    print("func_start:")
    print("1", bool(fs.search("func Foo() {")))
    print("2", bool(fs.search("func (s *Server) Foo(x int) {")))
    print("3", bool(fs.search("func (s *Server[T]) Foo(x int) {")))
    print("4", bool(fs.search("func \n(s *Server)\nFoo\n[T any]\n(x T) {")))
    print("5 anonymous:", bool(fs.search("func(x int) {")))
    
    args = GO_RULES["args"]
    print("args:")
    print("1", bool(args.search("func Foo(x int)")))
    print("2", bool(args.search("func (s *Server) Foo(x int)")))
    print("3", bool(args.search("func (s *Server[T]) Foo(x int)")))
    print("4", bool(args.search("func \n(s *Server)\nFoo\n[T any]\n(x T)")))
    print("5 anonymous:", bool(args.search("func(x int)")))

    cs = GO_RULES["class_start"]
    print("class_start:")
    print("1", bool(cs.search("type Foo struct")))
    print("2", bool(cs.search("type Foo[T any] struct")))
    print("3", bool(cs.search("type \n Foo \n [T any] \n struct")))

run_tests()

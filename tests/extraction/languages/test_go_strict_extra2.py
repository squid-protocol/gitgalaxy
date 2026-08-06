import sys
sys.path.insert(0, "/home/joe/nyx_projects/gitgalaxy")
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

fs = GO_RULES["func_start"]
args = GO_RULES["args"]
cs = GO_RULES["class_start"]

print("fs map:", bool(fs.search("func Foo[T map[string]int](x T) {")))
print("args map:", bool(args.search("func Foo[T map[string]int](x T) {")))
print("cs map:", bool(cs.search("type Foo[T map[string]int] struct {")))


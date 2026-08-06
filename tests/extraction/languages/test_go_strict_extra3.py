import sys
sys.path.insert(0, "/home/joe/nyx_projects/gitgalaxy")
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

gen = LANGUAGE_DEFINITIONS["go"]["rules"]["generics"]

print("gen simple:", bool(gen.search("[T any]")))
print("gen map:", bool(gen.search("[T map[string]any]")))
print("gen slice:", bool(gen.search("[T []any]")))
print("gen nested:", bool(gen.search("[T interface{ M() []any }]")))


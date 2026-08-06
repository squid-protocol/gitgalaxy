import sys
sys.path.insert(0, "/home/joe/nyx_projects/gitgalaxy")
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

gen = LANGUAGE_DEFINITIONS["go"]["rules"]["generics"]

m1 = gen.search("[T any]")
m2 = gen.search("[T map[string]any]")
m3 = gen.search("[T []any]")

print(m1.group(0) if m1 else None)
print(m2.group(0) if m2 else None)
print(m3.group(0) if m3 else None)

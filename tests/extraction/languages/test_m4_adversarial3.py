from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
import re
pattern = LANGUAGE_DEFINITIONS["m4"]["rules"]["doc"]
print("param:", bool(pattern.search("dnl @param foo")))
print("parameter:", bool(pattern.search("dnl @parameter foo")))
print("returns:", bool(pattern.search("dnl @returns foo")))

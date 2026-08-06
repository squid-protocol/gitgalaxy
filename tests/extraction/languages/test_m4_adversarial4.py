from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
pattern = LANGUAGE_DEFINITIONS["m4"]["rules"]["safety"]
print("AC_CHECK_HEADER:", bool(pattern.search("AC_CHECK_HEADER")))
print("AC_CHECK_HEADERS:", bool(pattern.search("AC_CHECK_HEADERS")))
print("AC_CHECK_FUNCS:", bool(pattern.search("AC_CHECK_FUNCS")))
print("AC_CHECK_PROGS:", bool(pattern.search("AC_CHECK_PROGS")))

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

rules = LANGUAGE_DEFINITIONS["swift"]["rules"]
print("branch:")
for case in ["throws(Error)", "throws", "try", "catch"]:
    print(case, bool(rules["branch"].search(case)))

print("args:")
for case in ["{ [weak self] in", "func foo(a: (((Int) -> Void)?)) {", "func foo<T>(x: T)"]:
    print(case, bool(rules["args"].search(case)))
    if rules["args"].search(case):
        print(rules["args"].search(case).group(0))

print("func_start:")
for case in ["func foo()", "public final func bar()", "isolated func baz()", "nonisolated(unsafe) func qux()", "macro myMacro()"]:
    print(case, bool(rules["func_start"].search(case)))
    if rules["func_start"].search(case):
        print(rules["func_start"].search(case).group(0))

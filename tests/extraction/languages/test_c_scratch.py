import re
args_str = r"(?!(?:if|for|while|switch|return|sizeof|typeof|_Alignof|__typeof__|__builtin_[a-zA-Z0-9_]+)\b)\b[a-zA-Z_]\w*[ \t\n*]*\(\s*(?:const\s+|volatile\s+)?(?:int|char|void|float|double|long|short|unsigned|signed|struct|enum)\b(?:[^)(]|\([^)]*\))*\)"
args_regex = re.compile(args_str)
print("typeof:", args_regex.search("typeof(int)"))
print("_Alignof:", args_regex.search("_Alignof(int)"))
print("__builtin_types_compatible_p:", args_regex.search("__builtin_types_compatible_p(int, float)"))
print("foo:", args_regex.search("foo(int x)"))

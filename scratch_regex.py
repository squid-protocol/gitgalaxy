import re

dependency_capture = re.compile(
    r"(?:^[ \t]*(?:(?:pub[ \t]+)?const[ \t]+(?:@\"[^\"]+\"|[a-zA-Z_]\w*)[ \t]*=[ \t]*|_[ \t]*=[ \t]*)?@import|(?:^[ \t]*(?:const[ \t]+(?:@\"[^\"]+\"|[a-zA-Z_]\w*)[ \t]*=[ \t]*)?@cImport[ \t\n]*\{[ \t\n]*)?@cInclude|[ \t]*@cInclude)[ \t\n]*\([ \t\n]*['\"]([^'\"]+)['\"]",
    re.M,
)

deps = [
    'const std = @import("std");',
    'const net = @import("std").net;',
    'const parser = @import("parser.zig");',
    'const c = @cImport({ @cInclude("stdio.h"); });',
    '_ = @import("std");',
    'const \nstd\n=\n@import\n(\n"std"\n)\n;',
    'pub const @"weird import" = @import("weird-name.zig");',
]

print("\nDEPENDENCY_CAPTURE")
for t in deps:
    m = dependency_capture.search(t)
    print(f"{t!r} -> {m.group(1) if m else None}")

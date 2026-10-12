"""#4546: a `.h` is Objective-C only on Objective-C evidence.

Class: every `.h` header (shared C / C++ / Objective-C extension) with no Objective-C
marker -- GL/Vulkan/SDL-style API headers, macro-heavy headers, `extern "C"` guards,
plain prototypes -- must not be called Objective-C, wherever it sits (alone, beside
other headers, beside `.c` or `.m` files). Real Objective-C headers still are.
Uses the REAL registry, not the isolated mock in test_language_lens.py.
"""

import pytest

from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GL = """#ifndef __glext_h_
#define __glext_h_ 1
#ifdef __cplusplus
extern "C" {
#endif
#define GL_VERSION_1_2 1
typedef unsigned int GLenum;
typedef void (APIENTRYP PFNGLBLENDCOLORPROC) (GLfloat red, GLfloat green, GLfloat blue, GLfloat alpha);
#ifdef GL_GLEXT_PROTOTYPES
GLAPI void APIENTRY glBlendColor (GLfloat red, GLfloat green, GLfloat blue, GLfloat alpha);
#endif
#ifdef __cplusplus
}
#endif
#endif
"""
VK = """#ifndef VULKAN_CORE_H_
#define VULKAN_CORE_H_ 1
#ifdef __cplusplus
extern "C" {
#endif
#define VK_MAKE_VERSION(major, minor, patch) \\
    ((((uint32_t)(major)) << 22) | (((uint32_t)(minor)) << 12) | ((uint32_t)(patch)))
#define VK_DEFINE_HANDLE(object) typedef struct object##_T* object;
VK_DEFINE_HANDLE(VkInstance)
typedef enum VkResult { VK_SUCCESS = 0, VK_NOT_READY = 1 } VkResult;
typedef struct VkApplicationInfo { VkStructureType sType; const void* pNext; } VkApplicationInfo;
typedef VkResult (VKAPI_PTR *PFN_vkCreateInstance)(const VkInstanceCreateInfo* pCreateInfo);
#ifndef VK_NO_PROTOTYPES
VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(const VkInstanceCreateInfo* pCreateInfo);
#endif
#ifdef __cplusplus
}
#endif
#endif
"""
SDL = """#ifndef SDL_h_
#define SDL_h_
#include "SDL_stdinc.h"
#include "begin_code.h"
#ifdef __cplusplus
extern "C" {
#endif
extern DECLSPEC int SDLCALL SDL_Init(Uint32 flags);
#define SDL_INIT_TIMER 0x00000001u
#ifdef __cplusplus
}
#endif
#include "close_code.h"
#endif
"""
MACRO = """#pragma once
#define MAX(a,b) ((a)>(b)?(a):(b))
#define CHECK(x) do { if (!(x)) abort(); } while (0)
struct point { int x; int y; };
static inline int dot(struct point a, struct point b) { return a.x*b.x + a.y*b.y; }
"""
PLAIN = """#ifndef FOO_H
#define FOO_H
int foo(int a);
int bar(const char *s);
#endif
"""
CPP = """#pragma once
#include <vector>
namespace a { class B { public: B(); virtual ~B(); template<typename T> T get(); }; }
"""
OBJC = {
    "interface": "#import <Foundation/Foundation.h>\n@interface Foo : NSObject\n- (void)bar;\n@end\n",
    "protocol": "@protocol Foo <NSObject>\n- (void)bar;\n@end\n",
    "nonnull": "NS_ASSUME_NONNULL_BEGIN\n@interface Foo : NSObject\n@property (nonatomic) NSInteger x;\n@end\nNS_ASSUME_NONNULL_END\n",
    "uikit": '#import <UIKit/UIKit.h>\n#import "Bar.h"\n@class Baz;\n',
    "ns_enum_only": "typedef NS_ENUM(NSInteger, Foo) { FooA, FooB };\nFOUNDATION_EXPORT NSString * const FooKey;\n",
    "cocoa_c_style": "#import <Cocoa/Cocoa.h>\nextern NSString *const Kx;\n",
    "nsstring_only": "#include <Foundation/Foundation.h>\nNSString *foo(NSArray *a);\n",
    "block_api": 'typedef void (^Handler)(NSError *error);\n#import "Foo.h"\n',
}

NOT_OBJC = {
    "gl_ext": (GL, "c"),
    "vulkan_core": (VK, "c"),
    "sdl": (SDL, "c"),
    "macro_heavy": (MACRO, "c"),
    "plain_prototypes": (PLAIN, "c"),
    "cpp_namespace_class": (CPP, "cpp"),
    "cpp_template": ("#pragma once\ntemplate <typename T>\nT twice(T x) { return x + x; }\n", "cpp"),
    "cpp_std": ("#pragma once\n#include <cstdint>\nstd::size_t n();\n", "cpp"),
    "cpp_class_inherit": ("class A : public B {\npublic:\n  A();\n};\n", "cpp"),
}

NEIGHBOURHOODS = {
    "alone": (),
    "beside_headers": ("zz_other.h", "zz_other2.h"),
    "beside_c": ("zz_impl.c", "zz_impl2.c"),
    "beside_objc_sources": ("zz_app.m", "zz_app2.m", "zz_app3.m"),
}


def _classify(tmp_path, name, text, extras):
    (tmp_path / name).write_text(text)
    for extra in extras:
        (tmp_path / extra).write_text("// placeholder\n")
    tally: dict[str, int] = {}
    for child in tmp_path.iterdir():
        tally[child.suffix.lower()] = tally.get(child.suffix.lower(), 0) + 1
        tally[child.name.lower()] = 1
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, LEXICAL_FAMILY_HEURISTICS)
    return detector.inspect(tmp_path / name, text, ext_tally=tally)["lang_id"]


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
@pytest.mark.parametrize("style", NOT_OBJC)
def test_header_without_objc_evidence_is_not_objective_c(tmp_path, style, hood):
    text, expected = NOT_OBJC[style]
    assert _classify(tmp_path, "hdr.h", text, NEIGHBOURHOODS[hood]) == expected


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
@pytest.mark.parametrize("style", OBJC)
def test_header_with_objc_evidence_stays_objective_c(tmp_path, style, hood):
    assert _classify(tmp_path, "hdr.h", OBJC[style], NEIGHBOURHOODS[hood]) == "objective-c"


def test_objc_evidence_beats_cpp_evidence(tmp_path):
    text = "#import <Foundation/Foundation.h>\n#include <vector>\n@interface A : NSObject\n@end\n"
    assert _classify(tmp_path, "mixed.h", text, ()) == "objective-c"


def test_dot_m_files_unaffected(tmp_path):
    text = "#import <Foundation/Foundation.h>\n@implementation A\n@end\n"
    assert _classify(tmp_path, "a.m", text, ()) == "objective-c"

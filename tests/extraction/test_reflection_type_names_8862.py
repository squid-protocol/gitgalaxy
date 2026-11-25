"""reflection_metaprogramming reads a call or keyword form, not a type name or import (#8862, unplanted_family_contracts.md).

C# `using System.Reflection.Emit;`, a Java `ClassLoader` type name and Rust `PhantomData` matched as sites.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SITES = {
    "csharp": (
        'MethodInfo m = typeof(Foo).GetMethod("Bar");',
        "var o = Activator.CreateInstance(t);",
        "il.Emit(OpCodes.Ret);",
        "ILGenerator il = mb.GetILGenerator();",
        "var a = System.Reflection.Assembly.GetExecutingAssembly();",
    ),
    "java": (
        'Class.forName("Foo");',
        "m.invoke(o);  Method.invoke(o);",
        "ClassLoader.getSystemClassLoader();",
        "cl = obj.getClass().getClassLoader();",
        'c = loader.loadClass("Foo");',
    ),
    "rust": ("std::mem::transmute(x)", "macro_rules! foo {}", "UnsafeCell::new(1)"),
}
NOT_SITES = {
    "csharp": ("using System.Reflection;", "using System.Reflection.Emit;", "void Emit(int x) {}"),
    "java": ("ClassLoader loader;", "import java.lang.ClassLoader;"),
    "rust": ("marker: PhantomData<T>,", "use std::marker::PhantomData;"),
}


def _cases(table):
    return [(lang, text) for lang, texts in table.items() for text in texts]


@pytest.mark.parametrize(("lang", "text"), _cases(SITES))
def test_a_reflection_call_still_counts(lang, text):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["reflection_metaprogramming"].search(text)


@pytest.mark.parametrize(("lang", "text"), _cases(NOT_SITES))
def test_a_type_name_or_import_is_not_a_site(lang, text):
    assert not LANGUAGE_DEFINITIONS[lang]["rules"]["reflection_metaprogramming"].search(text)

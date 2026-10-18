"""#5462: out-of-class member definitions of a class template (`Foo<A, B>::method(...)`)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _extraction_harness import assert_redos_immune  # type: ignore

RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]

CASES = [
    (
        "template<uint8_t W, uint8_t H>\nvoid Adafruit_SSD1306<W, H>::drawPixel(int16_t x) {",
        "Adafruit_SSD1306<W, H>::drawPixel",
    ),
    ("void idList<type>::Append(const type &a) {", "idList<type>::Append"),
    ("Type &idHashTable<Type>::Get(const char *key) {", "idHashTable<Type>::Get"),
    ("void Foo<A, B>::m() {", "Foo<A, B>::m"),
    ("void Foo<std::map<int, std::vector<int>>, 3>::m(int a) {", "Foo<std::map<int, std::vector<int>>, 3>::m"),
    ("void Foo<int N = 4>::m() {", "Foo<int N = 4>::m"),
    ("void ns::Foo<T>::m() {", "ns::Foo<T>::m"),
    ("void Outer<T>::Inner::m() {", "Outer<T>::Inner::m"),
    ("void Outer::Inner<T>::m() {", "Outer::Inner<T>::m"),
    ("Foo<T>::Foo(int x) : a(x) {", "Foo<T>::Foo"),
    ("Foo<T>::~Foo() {", "Foo<T>::~Foo"),
    ("T &Foo<T>::operator[](int i) {", "Foo<T>::operator[]"),
    ("bool Foo<T>::operator==(const Foo<T> &o) const {", "Foo<T>::operator=="),
    ("Foo<T>::operator bool() const {", "Foo<T>::operator bool"),
    ("template<> void Foo<int>::m() {", "Foo<int>::m"),
    ("template<>\nvoid Foo<std::vector<int>>::m(const int &a) {", "Foo<std::vector<int>>::m"),
]


@pytest.mark.parametrize("payload,name", CASES)
def test_template_member_definition(payload, name):
    m = RULES["func_start"].search(payload)
    assert m and m.group(1) == name


@pytest.mark.parametrize(
    "payload",
    [
        "Foo<T>::m();",  # a call, no body brace
        "x = a < b && c > d::m() {",  # comparison, not a template qualifier
        "if (Foo<T>::m()) {",
    ],
)
def test_template_member_invalid(payload):
    assert RULES["func_start"].search(payload) is None


@pytest.mark.parametrize(
    "payload",
    [
        "void Foo<" + "A<" * 40,
        "void Foo<" + "A, " * 400 + "::m(",
        "void Foo<A<B<C>>>" + "::Bar<A<B<C>>>" * 40 + "::m",
    ],
)
def test_template_member_redos(payload):
    assert_redos_immune(RULES["func_start"], payload)

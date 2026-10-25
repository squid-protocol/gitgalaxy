"""#5462: the tail between a definition's parameter list and its body (`f() THROWS {`, `f() noexcept(x) {`)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _extraction_harness import assert_redos_immune  # type: ignore

RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]


def _name(payload):
    m = RULES["func_start"].search(payload)
    return next((g for g in m.groups() if g), None) if m else None


CASES = [
    # specifier macros
    ("uint16_t MBlockBitStream::readBit() THROWS {", "MBlockBitStream::readBit"),
    ("void f() Q_DECL_NOEXCEPT {", "f"),
    ("void f() const Q_DECL_OVERRIDE {", "f"),
    ("void set_done() ASIO_RVALUE_REF_QUAL ASIO_NOEXCEPT {", "set_done"),
    ("strand(const strand& other) ASIO_NOEXCEPT\n    : executor_(other.executor_),\n      impl_(other.impl_)\n  {", "strand"),
    ("Result createInstance(\n    int a,\n    int b) const\n    VULKAN_HPP_NOEXCEPT\n{", "createInstance"),
    # exception specifications
    ("void f() noexcept(false) {", "f"),
    ("void f() noexcept(sizeof(T) > 4) {", "f"),
    ("void swap(reference other) noexcept (std::is_nothrow_move_constructible<value_t>::value) {", "swap"),
    ("void f() throw() {", "f"),
    ("void f() throw(std::bad_alloc, E) {", "f"),
    # trailing return types
    ("auto f() -> const char* {", "f"),
    ("auto f() -> decltype(a + b) {", "f"),
    ("auto f(T&& x) -> decltype(std::forward<T>(x)) {", "f"),
    ("auto f() -> std::map<int, int> {", "f"),
    ("auto f() const -> int {", "f"),
    # already handled members of the class
    ("void f() & noexcept {", "f"),
    ("int f(int a) override final {", "f"),
    # requires clause and function-try-block
    ("void f(T t) requires Foo<T> {", "f"),
    ("void f(T t) requires (sizeof(T) > 4) {", "f"),
    ("void f() try {", "f"),
    # #3772: a thread-safety annotation macro with arguments, on its own line below the `)`
    ("void Mock::AllowLeak(const void* p)\n    GTEST_LOCK_EXCLUDED_(internal::g_mutex) {", "Mock::AllowLeak"),
    ("void Done() const\n    GTEST_LOCK_EXCLUDED_(mutex_) {", "Done"),
    ("void Run(int a,\n         int b) const override\n      GTEST_LOCK_EXCLUDED_(g_mutex) {", "Run"),
    ("bool Check() const\n    GTEST_EXCLUSIVE_LOCK_REQUIRED_(mutex_) {", "Check"),
    ("void f()\n    ABSL_LOCKS_EXCLUDED(mu_) noexcept {", "f"),
    ("void f()\n    EXCLUSIVE_LOCKS_REQUIRED(a, b)\n    GUARDED_BY(c) {", "f"),
]


@pytest.mark.parametrize("payload,name", CASES)
def test_post_param_tail(payload, name):
    assert _name(payload) == name


@pytest.mark.parametrize(
    "payload,name",
    [
        # #5461 column-0 macro chains keep the macro's defined name, never the statement before it
        ("EXTERN_CVAR(Bool, x)\nCUSTOM_CVAR(Int, am_cheat, 0, 0) {", "am_cheat"),
        ("CVAR(Bool, x, false, 0)\nCCMD(spray) {", "spray"),
    ],
)
def test_macro_chain_keeps_its_name(payload, name):
    assert _name(payload) == name


@pytest.mark.parametrize(
    "payload,name",
    [
        # #3772: only the lock-annotation vocabulary is a tail; any other indented macro stays a chain
        ("  EXTERN_CVAR(Bool, x)\n  CUSTOM_CVAR(Int, y, 0, 0) {", "CUSTOM_CVAR"),  # unchanged by #3772
        ("void f()\n    DEFINE_THING(a, b) {", "DEFINE_THING"),
    ],
)
def test_other_indented_macro_is_not_a_tail(payload, name):
    assert _name(payload) == name


@pytest.mark.parametrize(
    "payload",
    [
        "struct alignas(16) VEC {",
        "void f() THROWS;",
        "    if (x) LIKELY {",
        "x = f() -> g {",
        "void f() MY_ATTR(1, 2) {",  # an argument-list macro reads as a macro statement chain
        "void f() GTEST_LOCK_EXCLUDED_(mu) {",  # #3772: the annotation tail is for a line of its own
    ],
)
def test_post_param_tail_invalid(payload):
    assert _name(payload) is None


@pytest.mark.parametrize(
    "payload",
    [
        "void f()" + " THROWS" * 400,
        "void f() noexcept(" + "(a)" * 400,
        "void f() throw(" + "a, " * 400,
        "auto f() -> " + "A, " * 400,
        "void f() requires " + "a && " * 400,
        "void f()\n" + "  X\n" * 400,
        "void f()" + "\n  LOCK_A(x)" * 400,
        "void f()\n  " + "LOCK_" * 400 + "(x)",
        "void f()\n  LOCK(" + "(a)" * 400,
    ],
)
def test_post_param_tail_redos(payload):
    assert_redos_immune(RULES["func_start"], payload)

import re

DEEP_CASES = """
_FORTRAN_DEEP_CASES = [
    # branch
    ("branch", "SELECT TYPE(a)", "SELECT_TYPE_VAR = 1"),
    ("branch", "SELECT  RANK (b)", "CASE_VAL = 1"),
    ("branch", "GO TO 10", "DO_SOMETHING(x)"),
    ("branch", "DO WHILE (x > 0)", "EXIT_CODE = 0"),
    ("branch", "IF (A .AND. B) THEN", "CYCLE_TIME = 5.0"),
    ("branch", "ELSEWHERE", "WHERE_AM_I = 'HERE'"),
    
    # args
    ("args", "INTENT( INOUT )", "VALUE_OF_X = 1"),
    ("args", "REAL, VALUE :: x", "OPTIONAL_ARG = .TRUE."),
    ("args", "INTEGER, OPTIONAL :: y", "ENTRY_POINT = 5"),
    ("args", "ENTRY my_entry(a, b)", "MY_SUBROUTINE = 10"),
    ("args", "FUNCTION foo ()", "FUNCTION_PTR = null()"),
    ("args", "SUBROUTINE bar( x, y, * )", "SUBROUTINE_NAME = 'bar'"),
    
    # func_start
    ("func_start", "PURE RECURSIVE INTEGER FUNCTION my_func()", "END SUBROUTINE foo"),
    ("func_start", "TYPE(MY_TYPE) FUNCTION get_type()", "END FUNCTION foo"),
    ("func_start", "DOUBLE PRECISION FUNCTION foo()", "END PROGRAM main"),
    ("func_start", "MODULE SUBROUTINE my_mod_sub ()", "x = FUNCTION_CALL()"),
    ("func_start", "ELEMENTAL IMPURE SUBROUTINE sub()", "TYPE(MY_TYPE) :: FUNCTION_NAME"),
    ("func_start", "PROGRAM main ! This is a comment", "INTEGER :: PROGRAM_ID"),
    ("func_start", "INTEGER(KIND=4), DIMENSION(:) FUNCTION foo()", "INTEGER :: FUNCTION_X"),
    ("func_start", "CLASS(*), POINTER :: FUNCTION poly_func()", "CLASS_NAME = 'abc'"),
    
    # class_start
    ("class_start", "SUBMODULE (parent:child) my_sub", "END MODULE my_module"),
    ("class_start", "BLOCK DATA my_data", "END TYPE my_type"),
    ("class_start", "INTERFACE my_intf", "TYPE(my_type) :: x"),
    ("class_start", "TYPE, ABSTRACT, EXTENDS(base) :: my_type", "TYPE(my_type) FUNCTION foo()"),
    ("class_start", "TYPE my_type", "SUBMODULE_NAME = 'abc'"),
    ("class_start", "TYPE :: my_type", "BLOCK_DATA_VAR = 1"),
    
    # structural_boundaries
    ("structural_boundaries", "END SUBROUTINE", "END IF"),
    ("structural_boundaries", "END TYPE", "END DO"),
    ("structural_boundaries", "DOUBLE PRECISION", "CLASS_NAME = 1"),
    ("structural_boundaries", "BLOCK DATA", "RETURN_CODE = 0"),
    ("structural_boundaries", "CONTAINS", "BLOCK_SIZE = 512"),
    ("structural_boundaries", "CLASS", "MODULE_VAR = 1"),
]

@pytest.mark.parametrize("signature,positive,negative", _FORTRAN_DEEP_CASES)
def test_fortran_signature_deep_cases(signature, positive, negative):
    pattern = FORTRAN_RULES[signature]
    assert pattern is not None, f"fortran's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"fortran {signature!r} failed to match deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"fortran {signature!r} incorrectly matched deep excluded case: {negative!r}"
"""

with open("/home/joe/nyx_projects/gitgalaxy/tests/extraction/languages/test_fortran_strict.py", "a") as f:
    f.write(DEEP_CASES)


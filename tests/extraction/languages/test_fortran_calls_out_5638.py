"""
Fortran call sites (#5638): a function reference `x = F(a)` and an argument-less `CALL F` land in `calls_out_to`
(fixed and free form); an array element, an element store, a statement-function definition, a component, an
intrinsic and a statement keyword never do; an early `RETURN` no longer ends the unit, so calls after it count.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

F77 = """\
      SUBROUTINE DMAIN
      INTEGER T0, MO, TBL(10), MOSEC(5)
      REAL W(3,3)
      DOUBLE PRECISION DP(4)
      CHARACTER*8 NAMES(3)
      DIMENSION LATE(6)
      COMMON /BLK/ CM(7), SCALAR
      T0 = I_TICKS(1)
      MO = P_SPAWN(2, 3)
      MOSEC(PLMO) = R_PSEC(4)
      TBL(3) = TBL(2) + W(1,2) + DP(1) + LATE(2) + CM(1)
      NAMES(1) = 'NOT_A_CALL(1)'
      STFN(X) = X * 2.0
      IF (M_ANYK(0)) THEN
         CALL G_NEW
      ENDIF
      IF (T0 .GT. 0) CALL G_LATE
      CALL V_TEXT((320 - V_TEXTW(1)) / 2, 5)
      X = SQRT(2.0) + MAX(1, 2)
      WRITE(6,100) TBL(1), K_AFTER(2)
      CALL S_START
      RETURN
      END
"""

F90 = """\
subroutine dmain()
  integer :: t0, tbl(10)
  real, dimension(3,3) :: w
  real, allocatable :: buf(:)
  type(thing) :: obj
  t0 = i_ticks(1)
  if (m_anyk(0)) then
     call g_new
  end if
  tbl(3) = tbl(2) + w(1,2) + buf(1) + obj%part(2)
  call v_text((320 - v_textw(1)) / 2, &
              5)
  x = sqrt(2.0) + k_after(3)
end subroutine dmain
"""

SINGLE_NAMES = (
    ("name", "src", "expected"),
    [
        (
            "DMAIN",
            F77,
            ["I_TICKS", "P_SPAWN", "R_PSEC", "M_ANYK", "G_NEW", "G_LATE", "V_TEXT", "V_TEXTW", "K_AFTER", "S_START"],
        ),
        ("dmain", F90, ["i_ticks", "m_anyk", "g_new", "v_text", "v_textw", "k_after"]),
    ],
)


def _calls(src: str) -> dict[str, list[str]]:
    result = StructuralExtractor("fortran", LANGUAGE_DEFINITIONS).splice(src, "")
    return {f["name"]: f["calls_out_to"] for f in result["functions"]}


@pytest.mark.parametrize(*SINGLE_NAMES)
def test_function_references_and_argumentless_call(name, src, expected):
    assert _calls(src)[name] == expected


def test_early_return_does_not_end_the_unit():
    src = (
        "      SUBROUTINE A\n      IF (X) THEN\n         CALL P\n         RETURN\n      ENDIF\n"
        "      CALL Q\n      END\n      SUBROUTINE B\n      CALL Z\n      END\n"
    )
    assert _calls(src) == {"A": ["P", "Q"], "B": ["Z"]}


def test_array_declared_in_one_unit_is_a_call_in_another():
    src = (
        "      SUBROUTINE A\n      REAL F(3)\n      X = F(1)\n      END\n"
        "      SUBROUTINE B\n      X = F(1)\n      END\n"
    )
    assert _calls(src) == {"A": [], "B": ["F"]}

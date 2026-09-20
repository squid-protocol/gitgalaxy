# ==============================================================================
# GitGalaxy Core: Path Proximity (#3200, #3199)
#
# One definition of "which of these candidate files is nearest to that one",
# shared by the two resolvers that have to choose between same-named files:
# `invocation_resolver.py` (a CALL naming a PROGRAM-ID several files declare)
# and `network_risk_sensor.py` (a COPY naming a member several directories
# hold). They disagree about what to do with a tie -- a call picks one, an
# import refuses to guess -- so this module exposes the RANK, and each resolver
# decides for itself. `nearest_path` is the pick-one form #3200 already used.
#
# EVERY comparison normalises separators first. The engine stores OS-native
# paths, so on Windows an un-normalised depth count (`path.count("/")`) is 0 for
# every candidate and the tiebreak silently degrades to alphabetical -- a
# resolution that disagrees with Linux for the same repository. #3223 went red
# on exactly this class of thing.
# ==============================================================================
from typing import Optional


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def proximity_rank(candidate: str, src_path: str) -> tuple[int, int]:
    """`(-shared directory depth, candidate depth)`, sorted ascending: nearest first.

    The first term prefers the candidate sharing the longest leading run of
    directories with `src_path` -- its own subtree's copy of a name beats a
    stranger's. The second breaks a shared-depth tie towards the SHALLOWER
    path, which is what a repository-wide library looks like: a member at
    `COPYBOOK/X.cpy` is the one a program outside every subtree gets, and
    `deep/nested/lib/X.cpy` is the one that subtree keeps to itself.

    It is deliberately NOT a total order -- two equidistant, equally shallow
    candidates rank equal, and the caller says what that means.
    """
    src_dirs = _posix(src_path).split("/")[:-1]
    dirs = _posix(candidate).split("/")[:-1]
    shared = 0
    for a, b in zip(src_dirs, dirs):
        if a != b:
            break
        shared += 1
    return -shared, len(dirs)


def nearest_path(candidates: list[str], src_path: str) -> Optional[str]:
    """The single nearest candidate, alphabetically broken so a tie still yields one.

    Deterministic and independent of scan order: a repository scanned on two
    machines must produce the same edge.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return sorted(candidates, key=lambda c: (*proximity_rank(c, src_path), _posix(c)))[0]

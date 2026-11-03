"""
Divisões de treino por estilo e dias na semana. Os músculos de cada dia vêm em ordem de
prioridade (grandes primeiro) e os exercícios aparecem agrupados por músculo.

Base científica, em duas partes que não devem ser confundidas:
- O que a literatura sustenta: o volume semanal por músculo e, com menos certeza, a
  frequência (treinar um músculo 2x/semana tende a superar 1x quando o volume não é
  controlado [R2]; com volume igual, a diferença some [R9]).
- O que é convenção: a composição de cada dia (ex.: "peito + tríceps", "empurrar") e o
  próprio nome dos estilos. Nenhuma fonte indica um estilo superior aos outros com o mesmo
  volume; a escolha serve à rotina e à preferência do usuário.
"""

from dataclasses import dataclass
from typing import Literal

SplitStyle = Literal["auto", "full_body", "upper_lower", "push_pull_legs", "hybrid", "body_part"]


@dataclass(frozen=True)
class Item:
    muscle: str
    # None = todas as vagas do músculo; senão, só estas (ex.: ombro posterior no dia de puxar)
    slots: tuple[str, ...] | None = None


@dataclass(frozen=True)
class DayTemplate:
    name: str
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Split:
    name: str
    days: tuple[DayTemplate, ...]


class InvalidSplitError(ValueError):
    """Estilo de divisão indisponível para o número de dias."""


def _day(name: str, *items: str | tuple[str, tuple[str, ...]]) -> DayTemplate:
    return DayTemplate(
        name,
        tuple(Item(item) if isinstance(item, str) else Item(item[0], item[1]) for item in items),
    )


_PRESS_LATERAL = ("press", "lateral")
_LATERAL_REAR = ("lateral", "rear")
_REAR = ("rear",)

# --- Corpo inteiro --------------------------------------------------------------------
_FULL_2 = Split(
    "Corpo inteiro",
    (
        _day(
            "Corpo inteiro A",
            "quadriceps",
            "chest",
            "lats",
            "hamstrings",
            "middle back",
            ("shoulders", _PRESS_LATERAL),
            "biceps",
            "calves",
        ),
        _day(
            "Corpo inteiro B",
            "hamstrings",
            "chest",
            "middle back",
            "quadriceps",
            "lats",
            ("shoulders", _LATERAL_REAR),
            "triceps",
            "glutes",
            "abdominals",
        ),
    ),
)
_FULL_3 = Split(
    "Corpo inteiro",
    (
        _day(
            "Corpo inteiro A",
            "quadriceps",
            "chest",
            "lats",
            ("shoulders", _PRESS_LATERAL),
            "biceps",
            "abdominals",
        ),
        _day(
            "Corpo inteiro B",
            "hamstrings",
            "chest",
            "middle back",
            "glutes",
            "triceps",
            "calves",
        ),
        _day(
            "Corpo inteiro C",
            "quadriceps",
            "hamstrings",
            "lats",
            "middle back",
            ("shoulders", _LATERAL_REAR),
            "biceps",
            "calves",
        ),
    ),
)

# --- Superior/Inferior ----------------------------------------------------------------
_UPPER_A = _day(
    "Superior A", "chest", "lats", ("shoulders", _PRESS_LATERAL), "middle back", "biceps", "triceps"
)
_UPPER_B = _day(
    "Superior B", "chest", "lats", "middle back", ("shoulders", _LATERAL_REAR), "triceps", "biceps"
)
_UPPER_C = _day(
    "Superior C", "lats", "chest", ("shoulders", _PRESS_LATERAL), "middle back", "biceps", "triceps"
)
_LOWER_A = _day("Inferior A", "quadriceps", "hamstrings", "glutes", "calves", "abdominals")
_LOWER_B = _day("Inferior B", "hamstrings", "quadriceps", "glutes", "calves", "abdominals")
_LOWER_C = _day("Inferior C", "quadriceps", "hamstrings", "glutes", "calves", "abdominals")

_UL_4 = Split("Superior/Inferior", (_UPPER_A, _LOWER_A, _UPPER_B, _LOWER_B))
_UL_6 = Split(
    "Superior/Inferior", (_UPPER_A, _LOWER_A, _UPPER_B, _LOWER_B, _UPPER_C, _LOWER_C)
)

# --- Empurrar/Puxar/Pernas -------------------------------------------------------------
_PUSH = ("chest", ("shoulders", _PRESS_LATERAL), "triceps")
_PULL = ("lats", "middle back", ("shoulders", _REAR), "biceps")
_LEGS = ("quadriceps", "hamstrings", "glutes", "calves", "abdominals")

_PPL_3 = Split(
    "Empurrar/Puxar/Pernas",
    (_day("Empurrar", *_PUSH), _day("Puxar", *_PULL), _day("Pernas", *_LEGS)),
)
_PPL_6 = Split(
    "Empurrar/Puxar/Pernas",
    (
        _day("Empurrar A", *_PUSH),
        _day("Puxar A", *_PULL),
        _day("Pernas A", *_LEGS),
        _day("Empurrar B", *_PUSH),
        _day("Puxar B", *_PULL),
        _day("Pernas B", "hamstrings", "quadriceps", "glutes", "calves", "abdominals"),
    ),
)

# --- Misto (5 dias) -----------------------------------------------------------------------
_HYBRID_5 = Split(
    "Misto: superior/inferior + empurrar/puxar/pernas",
    (
        _day(
            "Superior",
            "chest",
            "lats",
            ("shoulders", _PRESS_LATERAL),
            "middle back",
            "biceps",
            "triceps",
        ),
        _day("Inferior", "quadriceps", "hamstrings", "glutes", "calves", "abdominals"),
        _day("Empurrar", "chest", ("shoulders", _PRESS_LATERAL), "triceps"),
        _day("Puxar", "lats", "middle back", ("shoulders", _REAR), "biceps"),
        _day("Pernas", "quadriceps", "hamstrings", "glutes", "calves"),
    ),
)

# --- Por grupos musculares (cada músculo 1x/semana) ---------------------------------------
_BODY_PART_3 = Split(
    "Por grupos musculares",
    (
        _day("Peito e costas", "chest", "lats", "middle back"),
        _day("Pernas", "quadriceps", "hamstrings", "glutes", "calves"),
        _day("Ombros e braços", "shoulders", "biceps", "triceps", "abdominals"),
    ),
)
_BODY_PART_4 = Split(
    "Por grupos musculares",
    (
        _day("Peito e tríceps", "chest", "triceps"),
        _day("Costas e bíceps", "lats", "middle back", "biceps"),
        _day("Pernas", "quadriceps", "hamstrings", "glutes", "calves"),
        _day("Ombros e abdômen", "shoulders", "abdominals"),
    ),
)
_BODY_PART_5 = Split(
    "Por grupos musculares",
    (
        _day("Peito", "chest"),
        _day("Costas", "lats", "middle back"),
        _day("Ombros e abdômen", "shoulders", "abdominals"),
        _day("Braços", "biceps", "triceps"),
        _day("Pernas", "quadriceps", "hamstrings", "glutes", "calves"),
    ),
)
_BODY_PART_6 = Split(
    "Por grupos musculares",
    (
        _day("Peito", "chest"),
        _day("Costas", "lats", "middle back"),
        _day("Ombros e abdômen", "shoulders", "abdominals"),
        _day("Braços", "biceps", "triceps"),
        _day("Quadríceps e panturrilhas", "quadriceps", "calves"),
        _day("Posteriores e glúteos", "hamstrings", "glutes"),
    ),
)

SPLITS: dict[tuple[str, int], Split] = {
    ("full_body", 2): _FULL_2,
    ("full_body", 3): _FULL_3,
    ("upper_lower", 4): _UL_4,
    ("upper_lower", 6): _UL_6,
    ("push_pull_legs", 3): _PPL_3,
    ("push_pull_legs", 6): _PPL_6,
    ("hybrid", 5): _HYBRID_5,
    ("body_part", 3): _BODY_PART_3,
    ("body_part", 4): _BODY_PART_4,
    ("body_part", 5): _BODY_PART_5,
    ("body_part", 6): _BODY_PART_6,
}

# Estilo escolhido quando o usuário deixa em "automático": o que mantém cada grupo
# principal 2x/semana sempre que o número de dias permite.
AUTO_STYLE: dict[int, str] = {
    2: "full_body",
    3: "full_body",
    4: "upper_lower",
    5: "hybrid",
    6: "push_pull_legs",
}

DAYS = tuple(sorted({days for _, days in SPLITS}))


def styles_for(days: int) -> list[str]:
    """Estilos disponíveis (além de "auto") para o número de dias."""
    return [style for (style, d) in SPLITS if d == days]


def resolve_style(style: str, days: int) -> str:
    return AUTO_STYLE[days] if style == "auto" else style


def get_split(style: str, days: int) -> Split:
    resolved = resolve_style(style, days)
    try:
        return SPLITS[(resolved, days)]
    except KeyError:
        raise InvalidSplitError(
            f"O estilo de divisão escolhido não está disponível para {days} dias por semana."
        ) from None

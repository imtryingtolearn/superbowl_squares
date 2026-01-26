from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable


def parse_digits(value: str) -> list[int] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) != 10:
        return None
    digits: list[int] = []
    for x in data:
        if not isinstance(x, int) or x < 0 or x > 9:
            return None
        digits.append(x)
    if len(set(digits)) != 10:
        return None
    return digits


def digits_to_json(digits: Iterable[int]) -> str:
    return json.dumps(list(digits), separators=(",", ":"))


def square_id(row: int, col: int) -> int:
    return row * 10 + col


def row_col_from_id(square_id_: int) -> tuple[int, int]:
    return divmod(square_id_, 10)


@dataclass(frozen=True)
class QuarterWinner:
    quarter: int
    rows_last_digit: int
    cols_last_digit: int
    winning_square_id: int


def compute_winner_square_id(*, rows_score: int, cols_score: int, row_digits: list[int], col_digits: list[int]) -> int:
    rows_last = rows_score % 10
    cols_last = cols_score % 10
    row_index = row_digits.index(rows_last)
    col_index = col_digits.index(cols_last)
    return square_id(row_index, col_index)


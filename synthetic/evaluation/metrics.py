"""Accuracy measures shared by the evaluation scripts."""

from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz.distance import Levenshtein

FieldValue = str | int | float | None


def normalise_for_compare(value: FieldValue) -> str:
    """Canonical string for exact-match comparison (case and spacing ignored)."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split()).casefold() if value is not None else ""


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein edits per reference character (0 is perfect; may exceed 1)."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return Levenshtein.distance(reference, hypothesis) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Word-level Levenshtein edits per reference word."""
    ref, hyp = reference.split(), hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


@dataclass
class Tally:
    """Correct/total counts grouped by a key such as (tenant, document type)."""

    correct: dict[tuple[str, ...], int] = field(default_factory=lambda: defaultdict(int))
    total: dict[tuple[str, ...], int] = field(default_factory=lambda: defaultdict(int))

    def add(self, key: tuple[str, ...], ok: bool) -> None:
        """Count one observation under ``key``."""
        self.total[key] += 1
        self.correct[key] += int(ok)

    def rate(self, key: tuple[str, ...]) -> float:
        """Accuracy for ``key`` (0 when nothing was counted)."""
        return self.correct[key] / self.total[key] if self.total[key] else 0.0

    def overall(self) -> float:
        """Accuracy over all keys."""
        total = sum(self.total.values())
        return sum(self.correct.values()) / total if total else 0.0

    def rows(self) -> list[tuple[tuple[str, ...], int, int, float]]:
        """``(key, correct, total, rate)`` sorted by key."""
        return [(k, self.correct[k], self.total[k], self.rate(k)) for k in sorted(self.total)]


@dataclass
class Confusion:
    """Binary confusion counts, e.g. for re-upload predictions."""

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    def add(self, predicted: bool, actual: bool) -> None:
        """Count one prediction."""
        if predicted and actual:
            self.tp += 1
        elif predicted:
            self.fp += 1
        elif actual:
            self.fn += 1
        else:
            self.tn += 1

    @property
    def precision(self) -> float:
        """Share of predicted positives that were positive."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        """Share of actual positives that were predicted."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

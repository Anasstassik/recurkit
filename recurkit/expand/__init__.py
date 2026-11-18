"""Date generator: turns a rule into a lazy sequence of local date-times.

This layer works with local (wall-clock) time only and knows nothing about
time zones (design decision D-02).
"""

from recurkit.expand.defaults import ExpansionPlan, plan_for
from recurkit.expand.iterator import Occurrence, ValidityCheck, occurrences
from recurkit.expand.query import after, before, between, is_occurrence

__all__ = [
    "ExpansionPlan",
    "Occurrence",
    "ValidityCheck",
    "after",
    "before",
    "between",
    "is_occurrence",
    "occurrences",
    "plan_for",
]

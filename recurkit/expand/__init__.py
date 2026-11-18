"""Date generator: turns a rule into a lazy sequence of local date-times.

This layer works with local (wall-clock) time only and knows nothing about
time zones (design decision D-02).
"""

from recurkit.expand.defaults import ExpansionPlan, plan_for

__all__ = ["ExpansionPlan", "plan_for"]

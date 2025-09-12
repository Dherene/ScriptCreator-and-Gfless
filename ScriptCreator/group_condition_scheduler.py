"""Asynchronous condition scheduler for leader/member groups.

This module proposes a new scheme for running condition scripts for
multiple characters in parallel.  Each character evaluates its own set
of conditions without blocking others, reducing latency and avoiding
interference between members of a group.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List


ConditionCallable = Callable[[], Awaitable[bool] | bool]
ActionCallable = Callable[[], Awaitable[None] | None]


@dataclass
class Condition:
    """Represents a condition to be checked and executed."""

    name: str
    check: ConditionCallable
    action: ActionCallable

    async def try_execute(self) -> bool:
        """Run the condition and execute its action if the check passes."""
        result = self.check()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            action_result = self.action()
            if asyncio.iscoroutine(action_result):
                await action_result
            return True
        return False


@dataclass
class Character:
    """Container for a character's conditions."""

    name: str
    conditions: List[Condition] = field(default_factory=list)

    async def run(self) -> None:
        """Evaluate conditions sequentially without blocking other characters."""
        # Work on a copy to allow modifications during iteration.
        for cond in list(self.conditions):
            executed = await cond.try_execute()
            if executed:
                # Remove the condition once it succeeds.
                self.conditions.remove(cond)
            # Yield control so other characters may run.
            await asyncio.sleep(0)


class GroupConditionScheduler:
    """Coordinate leader and members concurrently."""

    def __init__(self, leader: Character, members: List[Character]) -> None:
        self.leader = leader
        self.members = members

    async def run(self) -> None:
        """Run all characters' condition loops in parallel."""
        tasks = [asyncio.create_task(c.run()) for c in [self.leader, *self.members]]
        await asyncio.gather(*tasks)


__all__ = [
    "Condition",
    "Character",
    "GroupConditionScheduler",
]
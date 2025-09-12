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
        # ``check`` may be synchronous or asynchronous.  If it's a regular
        # function we offload it to ``asyncio.to_thread`` so the event loop
        # remains responsive even for CPU bound work.
        if asyncio.iscoroutinefunction(self.check):
            result = await self.check()
        else:
            result = await asyncio.to_thread(self.check)

        if result:
            if asyncio.iscoroutinefunction(self.action):
                await self.action()
            else:
                await asyncio.to_thread(self.action)
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
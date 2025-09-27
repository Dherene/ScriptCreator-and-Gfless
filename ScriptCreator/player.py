import time
import json
import copy
import phoenix
import threading
import asyncio
import ast
import re
import contextvars
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable
from queue import Queue, Empty
from getports import returnCorrectPort, returnCorrectPID
from path import loadMap, findPath
from calculatefieldlocation import calculate_field_location, calculate_point_B_position
import random
import math
import subprocess
import gfless_api
import textwrap
try:
    import psutil
except ImportError:  # psutil is optional but recommended
    psutil = None
import pywinctl as pwc

from PyQt5 import QtWidgets

from group_console import console_print, use_group_console



# Syllable pools for roleplay-style name generation
PREFIXES = [
    "Ael", "Bel", "Cor", "Dar", "El", "Fen", "Gor", "Hal",
    "Kal", "Mor", "Thal", "Vor", "Zel", "Ryn", "Syl", "Dra",
    "Tor", "Val", "Xan", "Lys", "Kyr", "Ori", "Jor", "Ser",
    "Mal", "Ner", "Ery", "Alar", "Vey", "Zor",
    "aen", "belu", "corin", "daras", "elin", "fenra", "goran", "halis",
    "kalem", "morin", "thalor", "voren", "zelen", "rynar", "sylen", "draven",
    "torin", "valen", "xanor", "lysin", "kyral", "orien", "joren", "serin",
    "malor", "neris", "eryn", "alaren", "veyra", "zorin",
    # 50 únicos de 2 letras (se quedan con mayúscula inicial)
    "Aa", "Ab", "Ac", "Ad", "Ae", "Af", "Ag", "Ah", "Ai", "Aj",
    "Ak", "Al", "Am", "An", "Ao", "Ap", "Aq", "Ar", "As", "At",
    "Au", "Av", "Aw", "Ax", "Ay", "Az", "Ba", "Bb", "Bc", "Bd",
    "Be", "Bf", "Bg", "Bh", "Bi", "Bj", "Bk", "Bl", "Bm", "Bn",
    "Bo", "Bp", "Bq", "Br", "Bs", "Bt", "Bu", "Bv", "Bw", "Bx"
]

ROOTS = [
    "adan", "bar", "cor", "dun", "el", "far", "gar", "har", "ion",
    "anor", "bel", "dros", "fal", "grim", "lor", "mir", "tor", "ul",
    "thal", "rin", "vor", "sar", "mor", "kar", "nor", "tir", "zan",
    "ryn", "gol", "fen",
    "Adel", "Borin", "Calar", "Durel", "Emin", "Faron", "Galor", "Helin",
    "Iron", "Jarel", "Korin", "Lunor", "Miran", "Narel", "Orrin", "Phael",
    "Quen", "Ralos", "Selor", "Tarin", "Ulric", "Varon", "Worin", "Xarel",
    "Ymir", "Zeran", "Thoren", "Brynn", "Cyran", "Drael",
    # 50 únicos de 2 letras en minúscula
    "ca", "cb", "cc", "cd", "ce", "cf", "cg", "ch", "ci", "cj",
    "ck", "cl", "cm", "cn", "co", "cp", "cq", "cr", "cs", "ct",
    "cu", "cv", "cw", "cx", "cy", "cz", "da", "db", "dc", "dd",
    "de", "df", "dg", "dh", "di", "dj", "dk", "dl", "dm", "dn",
    "do", "dp", "dq", "dr", "ds", "dt", "du", "dv", "dw", "dx"
]

SUFFIXES = [
    "dor", "ion", "mir", "nar", "ric", "thas", "wen",
    "as", "eth", "ian", "or", "uth", "ys", "en", "ir", "oth",
    "el", "ar", "is", "al", "orim", "us", "ael", "ior",
    "ien", "yr", "os", "ethar", "orn", "iel",
    "Ael", "Ien", "Orn", "Eth", "Ul", "Yth", "On", "Er",
    "As", "Ior", "Uth", "Ius", "Oth", "An", "Um", "Yr",
    "Es", "Aris", "Is", "Olin", "Eus", "Ir", "Aur", "Enn",
    "Orim", "Ath", "Ith", "Eal", "Uel", "Oros",
    # 50 únicos de 2 letras en minúscula
    "ea", "eb", "ec", "ed", "ee", "ef", "eg", "eh", "ei", "ej",
    "ek", "el", "em", "en", "eo", "ep", "eq", "er", "es", "et",
    "eu", "ev", "ew", "ex", "ey", "ez", "fa", "fb", "fc", "fd",
    "fe", "ff", "fg", "fh", "fi", "fj", "fk", "fl", "fm", "fn",
    "fo", "fp", "fq", "fr", "fs", "ft", "fu", "fv", "fw", "fx"
]



# proxy object exposing group-scoped variables via attribute access
class GroupNamespace:
    """Allow scripts to access group variables as attributes."""

    def __init__(self, player):
        super().__setattr__("_player", player)

    def __getattr__(self, name):
        return self._player.get_group_var(name)

    def __setattr__(self, name, value):
        self._player.set_group_var(name, value)

    def __delattr__(self, name):
        self._player.del_group_var(name)

    def get(self, name, default=None):
        return self._player.get_group_var(name, default)


class SubgroupNamespace:
    """Expose subgroup-scoped variables using attribute access."""

    def __init__(self, player):
        super().__setattr__("_player", player)

    def __getattr__(self, name):
        return self._player.get_subgroup_var(name)

    def __setattr__(self, name, value):
        self._player.set_subgroup_var(name, value)

    def __delattr__(self, name):
        self._player.del_subgroup_var(name)

    def get(self, name, default=0):
        return self._player.get_subgroup_var(name, default)


class ConditionControl:
    """Expose ``cond.on`` and ``cond.off`` helpers to toggle conditions."""

    def __init__(self, player):
        object.__setattr__(self, "_player", player)

    def _toggle(self, attribute, value):
        if isinstance(value, bool) or not isinstance(value, int):
            self._player.log(f"cond.{attribute} expects an integer index.")
            return
        self._player._set_condition_active_by_number(value, attribute == "on")

    @property
    def on(self):
        return None

    @on.setter
    def on(self, value):
        self._toggle("on", value)

    @property
    def off(self):
        return None

    @off.setter
    def off(self, value):
        self._toggle("off", value)


class ConditionTimer:
    """Numeric helper exposing the time elapsed since the last condition change."""

    __slots__ = ("_player",)

    def __init__(self, player):
        self._player = player

    def _value(self, cond_type=None, name=None):
        elapsed = self._player.time_since_last_condition_change(cond_type, name)
        if isinstance(elapsed, (int, float)):
            return float(elapsed)
        return 0.0

    def __call__(self, cond_type=None, name=None):
        """Return elapsed seconds, optionally for a specific condition."""

        return self._value(cond_type, name)

    def reset(self, cond_type=None, name=None):
        """Reset the activity timer globally or for a specific condition."""

        self._player.reset_condition_activity_timer(cond_type, name)

    def __float__(self):
        return float(self._value())

    def __int__(self):
        return int(self._value())

    def __bool__(self):
        return bool(self._value())

    def __repr__(self):
        return f"{self._value():.6f}"

    __str__ = __repr__


class TimeNamespace:
    """Wrapper around :mod:`time` adding condition-aware helpers."""

    __slots__ = ("_module", "_cond")

    def __init__(self, player, module=time):
        object.__setattr__(self, "_module", module)
        object.__setattr__(self, "_cond", ConditionTimer(player))

    def __getattr__(self, name):
        return getattr(self._module, name)

    def __setattr__(self, name, value):
        if name == "cond":
            raise AttributeError("time.cond is read-only")
        setattr(self._module, name, value)

    def __delattr__(self, name):
        if name == "cond":
            raise AttributeError("time.cond cannot be deleted")
        delattr(self._module, name)

    @property
    def cond(self):
        return self._cond

    def reset_cond(self, cond_type=None, name=None):
        """Convenience wrapper that proxies to :meth:`ConditionTimer.reset`."""

        self._cond.reset(cond_type, name)

    def __dir__(self):
        return sorted(set(dir(self._module)) | {"cond", "reset_cond"})


# encapsulation for periodical conditions so each player can manage its own
# execution task and compiled function without interfering with others
@dataclass
class PeriodicCondition:
    name: str
    code: str
    active: bool
    interval: float
    func: Optional[Callable] = field(default=None, repr=False)
    task: Optional[asyncio.Task] = field(default=None, repr=False)
    _code_cache: str = field(default="", repr=False)
    last_error: Optional[str] = field(default=None, repr=False)


# player class which can be reused in other standalone apis
class Player:
    # shared storage for variables scoped per group (leader PID)
    _group_vars = {}
    _group_var_lock = threading.Lock()
    _subgroup_vars = {}
    _subgroup_var_lock = threading.Lock()

    class _GroupConsoleBuffer:
        __slots__ = ("chunks",)

        def __init__(self):
            self.chunks = []

        def append_text(self, text: str) -> None:
            if text:
                self.chunks.append(text)

        def drain(self):
            chunks, self.chunks = self.chunks, []
            return chunks

        def flush(self) -> None:
            # Satisfy the interface expected by ``print`` when ``flush=True``.
            return None

    def __init__(self, name=None, on_disconnect=None, api_port=None, pid=None, new_api_port=None):
        # player info
        self.name = name
        self.id = 0
        self.pos_x = 0
        self.pos_y = 0
        self.map_id = 0
        self.level = 0
        self.champion_level = 0
        self.hp_percent = 0
        self.current_hp = 0
        self.max_hp = 0
        self.mp_percent = 0
        self.current_mp = 0
        self.max_mp = 0
        self.is_resting = 0

        # inventory
        self.equip = {}
        self.etc = {}
        self.gold = {}
        self.main = {}

        # skills
        self.skills = {}

        # map_entities
        self.items = []
        self.monsters = []
        self.npcs = []
        self.players = []

        # other
        self.map_changed = False

        # should move to shared class so map doesnt have to be loaded for each character individually
        self.map_array = []
        
        self.recv_packet_conditions = []
        self.send_packet_conditions = []
        self.periodical_conditions: list[PeriodicCondition] = []
        self._cond_counter = 0
        self._cond_control = ConditionControl(self)
        self._time_namespace = TimeNamespace(self)
        self.condition_logging_enabled = True

        # caches for compiled condition functions
        # maps condition name to a tuple of (source_code, compiled_func)
        self._compiled_recv_conditions = {}
        self._compiled_send_conditions = {}

        # track current execution status per condition type
        self._condition_state = {
            "recv_packet": set(),
            "send_packet": set(),
            "periodical": set(),
        }
        self._condition_ctx = contextvars.ContextVar(
            "condition_context", default=None
        )
        self._condition_state_lock = threading.Lock()
        self._condition_time_lock = threading.Lock()
        self._last_condition_activity = time.monotonic()
        self._last_condition_state_change = self._last_condition_activity
        self._condition_activity_by_name = {}

        # track condition-facing status for the make_party helper
        self._make_party_condition_state = 0

        # internal state for periodical walking
        # track per-condition cooldowns and thread context
        self._periodic_walking = set()
        self._last_periodic_walk = {}
        self._periodic_ctx = threading.local()
        self._periodic_cond_lock = threading.Lock()
        # dedicated executor so multiple conditions can run in parallel
        self._cond_executor = ThreadPoolExecutor(max_workers=4)
        self._periodic_main_task = None

        # walking coordination
        self.walk_lock = threading.Lock()
        self.walk_queue = Queue()
        self._walk_thread = threading.Thread(target=self._process_walk_queue, daemon=True)
        self._walk_thread.start()

        # dedicated executor for heavy path computations
        self._path_executor = ThreadPoolExecutor(max_workers=1)
        
        # asyncio event loop for non-blocking tasks
        self.loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._loop_thread.start()

        # indicates when a script has been loaded into this player
        self.script_loaded = False
        self._group_console = None
        self._group_console_buffer = None
        self._buffer_console_output = False

        # group info
        self.leadername = ""
        self.leaderID = 0
        self.partyname = []
        self.partyID = []
        self.party_subgroups = {}
        self.party_subgroup_order = {}
        self.subgroup_index = None
        self.subgroup_member_limit = 0

        # unique identifier for isolated group namespace before leaderID is known
        self._unique_group_id = id(self)
        self._current_gid = self._unique_group_id

        # proxy for group-shared variables
        self._group = GroupNamespace(self)
        self._subgroup = SubgroupNamespace(self)

        # callback when connection is lost
        self.on_disconnect = on_disconnect
        
        # initialize 100 empty attributes so user can use them as he wants
        for i in range(1, 50):
            setattr(self, f'attr{i}', 0)

        for i in range(51, 101):
            setattr(self, f'attr{i}', [])

        # connection metadata
        self.api = None
        self.api_port = str(api_port) if api_port is not None else None
        self.new_api_port = str(new_api_port) if new_api_port is not None else None
        self.port = None
        if api_port is not None:
            try:
                self.port = int(api_port)
            except (TypeError, ValueError):
                self.port = None
        self.PIDnum = pid
        self.stop_script = False

        resolved_port = self.port
        if resolved_port is None and name is not None:
            resolved_port = returnCorrectPort(self.name)
            if resolved_port is not None:
                self.api_port = str(resolved_port)

        if self.PIDnum is None and name is not None:
            pid_value = returnCorrectPID(self.name)
            if pid_value is not None:
                self.PIDnum = pid_value

        if resolved_port is not None:
            self.port = resolved_port
            try:
                self.api = phoenix.Api(self.port)
            except (TypeError, OSError):
                self.api = None
                self.stop_script = True
            else:
                pl_thread = threading.Thread(target=self.packetlogger)
                pl_thread.setDaemon(True)
                pl_thread.start()

                t = threading.Thread(target=self.queries, args=[0.25, ])
                t.start()

                # ensure condition loops are ready
                self.start_condition_loop()
        else:
            # without a resolved port we cannot communicate with the API
            self.stop_script = True

    @property
    def group_console(self):
        return self._group_console

    @group_console.setter
    def group_console(self, console):
        self._group_console = console
        if console is None and not self._buffer_console_output:
            self._group_console_buffer = None

    def prepare_group_console_output(self):
        """Capture log output until a group console becomes available."""

        self._buffer_console_output = True
        self._group_console_buffer = self._GroupConsoleBuffer()

    def flush_group_console_buffer(self):
        """Replay buffered logs into the active group console."""

        console = self._group_console
        buffer = self._group_console_buffer
        if console is None or buffer is None:
            return
        for chunk in buffer.drain():
            try:
                console.append_text(chunk)
            except Exception:
                pass
        if hasattr(console, "flush"):
            try:
                console.flush()
            except Exception:
                pass
        self._group_console_buffer = None
        self._buffer_console_output = False

    def clear_group_console_buffer(self):
        """Discard any buffered log messages."""

        self._group_console_buffer = None
        self._buffer_console_output = False

    def get_console_for_output(self):
        """Return the current console target, falling back to the buffer."""

        if self._buffer_console_output:
            if self._group_console_buffer is None:
                self._group_console_buffer = self._GroupConsoleBuffer()
            return self._group_console_buffer
        return self._group_console

    def _console_print(self, *args, **kwargs):
        """Send output to the assigned group console if available."""

        console_print(self.get_console_for_output(), *args, **kwargs)

    def log(self, *args, **kwargs):
        """Write log messages using the player's current console."""

        self._console_print(*args, **kwargs)

    def start_condition_loop(self):
        """Ensure background condition tasks are running.

        Conditions can be added or toggled from different threads (e.g. the
        GUI).  This helper restarts the asyncio supervisor task when needed and
        keeps the per-condition tasks in sync with their ``active`` flag.  It
        is safe to call multiple times and from any thread."""

        # ``self.loop`` is created in ``__init__`` but can be stopped if the
        # client was disconnected.  Recreate it when necessary so conditions
        # can continue running after a reconnection or setup load.
        if not hasattr(self, "loop") or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self.loop.run_forever, daemon=True
            )
            self._loop_thread.start()
            self._periodic_main_task = None
            with self._periodic_cond_lock:
                conds = list(self.periodical_conditions)
            for cond in conds:
                cond.task = None
        elif not getattr(self, "_loop_thread", None) or not self._loop_thread.is_alive():
            self._loop_thread = threading.Thread(
                target=self.loop.run_forever, daemon=True
            )
            self._loop_thread.start()
            self._periodic_main_task = None
            with self._periodic_cond_lock:
                conds = list(self.periodical_conditions)
            for cond in conds:
                cond.task = None

        def _ensure_tasks():
            if self._periodic_main_task is None or self._periodic_main_task.done():
                self._periodic_main_task = asyncio.create_task(
                    self.exec_periodic_conditions()
                )

            # Cancel tasks that should not be running and reset finished ones.
            with self._periodic_cond_lock:
                conds = list(self.periodical_conditions)
            for cond in conds:
                if not cond.active:
                    if cond.task and not cond.task.done():
                        cond.task.cancel()
                    cond.task = None
                elif cond.task and cond.task.done():
                    cond.task = None

        self.loop.call_soon_threadsafe(_ensure_tasks)

    @staticmethod
    def _condition_sort_key(name):
        parts = re.split(r"(\d+)", name)
        return [int(part) if part.isdigit() else part.lower() for part in parts]

    def _build_condition_sequence(self):
        entries = []
        for idx, cond in enumerate(self.recv_packet_conditions):
            entries.append(("recv_packet", idx, cond[0]))
        for idx, cond in enumerate(self.send_packet_conditions):
            entries.append(("send_packet", idx, cond[0]))
        with self._periodic_cond_lock:
            for idx, cond in enumerate(self.periodical_conditions):
                entries.append(("periodical", idx, cond.name))
        entries.sort(key=lambda item: self._condition_sort_key(item[2]))
        return entries

    def _record_condition_activity(self, cond_type=None, name=None):
        now = time.monotonic()
        with self._condition_time_lock:
            self._last_condition_activity = now
            if cond_type is not None and name is not None:
                self._condition_activity_by_name[(cond_type, name)] = now

    def _record_condition_state_change(self):
        now = time.monotonic()
        with self._condition_time_lock:
            self._last_condition_state_change = now
            self._last_condition_activity = now

    def time_since_last_condition_change(self, cond_type=None, name=None):
        with self._condition_time_lock:
            if cond_type is None and name is None:
                last = self._last_condition_state_change
            elif cond_type is not None and name is not None:
                last = self._condition_activity_by_name.get((cond_type, name))
            else:
                return None
        if last is None:
            return None
        return time.monotonic() - last

    def reset_condition_activity_timer(self, cond_type=None, name=None):
        self._record_condition_activity(cond_type, name)
        if cond_type is None and name is None:
            self._record_condition_state_change()

    def _set_condition_active_by_number(self, seq_number, active):
        if isinstance(seq_number, bool) or not isinstance(seq_number, int):
            self.log("Condition numbers must be integers.")
            return
        if seq_number < 0:
            self.log("Condition numbers start at 1.")
            return

        entries = self._build_condition_sequence()

        if seq_number == 0:
            if active:
                self.log("Condition numbers start at 1.")
                return
            if not entries:
                self.log("No conditions available to toggle.")
                return

            current_ctx = self._condition_ctx.get()
            skip_type = skip_name = None
            if isinstance(current_ctx, tuple) and len(current_ctx) == 2:
                skip_type, skip_name = current_ctx

            disabled_entries = []
            skipped_current = False
            for cond_type, idx, name in entries:
                if skip_type is not None and cond_type == skip_type and name == skip_name:
                    skipped_current = True
                    continue
                changed = False
                if cond_type == "recv_packet":
                    if self.recv_packet_conditions[idx][2]:
                        self.recv_packet_conditions[idx][2] = False
                        changed = True
                elif cond_type == "send_packet":
                    if self.send_packet_conditions[idx][2]:
                        self.send_packet_conditions[idx][2] = False
                        changed = True
                else:
                    with self._periodic_cond_lock:
                        cond = self.periodical_conditions[idx]
                        if cond.active:
                            if cond.task and not cond.task.done():
                                cond.task.cancel()
                                cond.task = None
                            cond.active = False
                            changed = True

                if changed:
                    disabled_entries.append((cond_type, name))

            self.start_condition_loop()
            if disabled_entries:
                self._record_condition_state_change()
                for cond_type, name in disabled_entries:
                    self._record_condition_activity(cond_type, name)
                    if self.condition_logging_enabled:
                        self.log(f"Condition '{name}' disabled via cond.off = 0")
                if skipped_current and self.condition_logging_enabled:
                    self.log(
                        "Current condition kept active while disabling others via cond.off = 0"
                    )
            elif skipped_current:
                if self.condition_logging_enabled:
                    self.log("Only the calling condition was active; nothing else to disable.")
            else:
                if self.condition_logging_enabled:
                    self.log("No active conditions to disable.")
            return

        if not entries:
            self.log("No conditions available to toggle.")
            return
        if seq_number > len(entries):
            self.log(
                f"Condition index {seq_number} is out of range (max {len(entries)})."
            )
            return

        cond_type, idx, name = entries[seq_number - 1]
        changed = False
        if cond_type == "recv_packet":
            previous = self.recv_packet_conditions[idx][2]
            self.recv_packet_conditions[idx][2] = active
            changed = previous != active
        elif cond_type == "send_packet":
            previous = self.send_packet_conditions[idx][2]
            self.send_packet_conditions[idx][2] = active
            changed = previous != active
        else:
            with self._periodic_cond_lock:
                cond = self.periodical_conditions[idx]
                previous = cond.active
                if not active and cond.task and not cond.task.done():
                    cond.task.cancel()
                    cond.task = None
                cond.active = active
                changed = previous != active

        self.start_condition_loop()
        if changed:
            self._record_condition_state_change()
        self._record_condition_activity(cond_type, name)
        state = "enabled" if active else "disabled"
        attr = "on" if active else "off"
        if self.condition_logging_enabled:
            self.log(f"Condition '{name}' {state} via cond.{attr} = {seq_number}")

    # ------------------------------------------------------------------ #
    # Group-shared variable helpers
    # ------------------------------------------------------------------ #
    def _resolve_gid(self, group_id):
        if group_id is not None:
            return group_id
        gid = self.leaderID if self.leaderID else self._unique_group_id
        if gid != self._current_gid:
            with Player._group_var_lock:
                Player._group_vars.setdefault(gid, {}).update(
                    Player._group_vars.pop(self._current_gid, {})
                )
            self._current_gid = gid
        return gid

    def get_group_var(self, name, default=None, group_id=None):
        """Return the value of ``name`` for this group.

        Parameters
        ----------
        name: str
            Variable identifier.
        default: Any
            Fallback value when the variable is not set.
        group_id: Optional[int]
            Override the group ID. When omitted, ``self.leaderID`` is used.
        """

        gid = self._resolve_gid(group_id)
        with Player._group_var_lock:
            group = Player._group_vars.setdefault(gid, {})
            return group.get(name, default)

    def set_group_var(self, name, value, group_id=None):
        """Assign ``value`` to ``name`` for this group."""

        gid = self._resolve_gid(group_id)
        with Player._group_var_lock:
            Player._group_vars.setdefault(gid, {})[name] = value

    def del_group_var(self, name, group_id=None):
        """Remove ``name`` from this group if present."""

        gid = self._resolve_gid(group_id)
        with Player._group_var_lock:
            group = Player._group_vars.get(gid)
            if not group:
                return
            group.pop(name, None)
            if not group:
                Player._group_vars.pop(gid, None)

    def _resolve_subgroup_ids(self, group_id=None, subgroup_index=None):
        group_identifier = group_id
        if group_identifier is None:
            group_identifier = getattr(self, "attr19", 0)
        try:
            group_identifier = int(group_identifier)
        except (TypeError, ValueError):
            group_identifier = 0
        if group_identifier <= 0:
            raise RuntimeError(
                "Subgroup variable error: the player is not assigned to a group."
            )

        subgroup_identifier = subgroup_index
        if subgroup_identifier is None:
            subgroup_identifier = getattr(self, "subgroup_index", None)
        try:
            subgroup_identifier = int(subgroup_identifier)
        except (TypeError, ValueError):
            subgroup_identifier = 0
        if subgroup_identifier <= 0:
            raise RuntimeError(
                "Subgroup variable error: the player does not belong to a subgroup."
            )

        return group_identifier, subgroup_identifier

    def get_subgroup_var(
        self,
        name,
        default=0,
        group_id=None,
        subgroup_index=None,
    ):
        """Return the value of ``name`` shared by this subgroup."""

        gid, sid = self._resolve_subgroup_ids(group_id, subgroup_index)
        with Player._subgroup_var_lock:
            subgroup_data = Player._subgroup_vars.setdefault(gid, {})
            values = subgroup_data.setdefault(sid, {})
            value = values.get(name, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def set_subgroup_var(
        self,
        name,
        value,
        group_id=None,
        subgroup_index=None,
    ):
        """Assign an integer ``value`` to ``name`` for this subgroup."""

        gid, sid = self._resolve_subgroup_ids(group_id, subgroup_index)
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"Subgroup variables accept only integers (received {value!r})."
            )

        with Player._subgroup_var_lock:
            subgroup_data = Player._subgroup_vars.setdefault(gid, {})
            subgroup_values = subgroup_data.setdefault(sid, {})
            subgroup_values[name] = numeric_value

    def del_subgroup_var(
        self,
        name,
        group_id=None,
        subgroup_index=None,
    ):
        """Remove ``name`` from the current subgroup if it exists."""

        gid, sid = self._resolve_subgroup_ids(group_id, subgroup_index)
        with Player._subgroup_var_lock:
            subgroup_data = Player._subgroup_vars.get(gid)
            if not subgroup_data:
                return
            values = subgroup_data.get(sid)
            if not values:
                return
            values.pop(name, None)
            if not values:
                subgroup_data.pop(sid, None)
            if not subgroup_data:
                Player._subgroup_vars.pop(gid, None)

    # ------------------------------------------------------------------ #
    # Party coordination helpers
    # ------------------------------------------------------------------ #
    def _record_make_party_result(self, success: bool) -> int:
        """Store the latest make_party outcome for condition checks."""

        result = 2 if success else 0
        self._make_party_condition_state = result
        return result

    def _read_make_party_state(self):
        gid = self._resolve_gid(None)
        with Player._group_var_lock:
            group = Player._group_vars.setdefault(gid, {})
            stored = group.get("_make_party_state")
            if not isinstance(stored, dict):
                return {}
            return copy.deepcopy(stored)

    def _normalize_make_party_substate(self, sub_state):
        if not isinstance(sub_state, dict):
            sub_state = {}

        ready_raw = sub_state.get("ready", set())
        if isinstance(ready_raw, set):
            ready_set = set(ready_raw)
        elif isinstance(ready_raw, (list, tuple)):
            ready_set = set(ready_raw)
        else:
            ready_set = set()

        try:
            expected = int(sub_state.get("expected", 0))
        except (TypeError, ValueError):
            expected = 0

        members_raw = sub_state.get("members", [])
        if isinstance(members_raw, (list, tuple)):
            members = list(members_raw)
        else:
            members = []

        try:
            stage = int(sub_state.get("stage", 0))
        except (TypeError, ValueError):
            stage = 0

        started = bool(sub_state.get("started", False))
        completed = bool(sub_state.get("completed", False))
        try:
            last_update = float(sub_state.get("last_update", 0.0))
        except (TypeError, ValueError):
            last_update = 0.0

        return {
            "ready": ready_set,
            "expected": expected,
            "members": members,
            "stage": stage,
            "started": started,
            "completed": completed,
            "last_update": last_update,
        }

    def _ensure_make_party_substate_mutable(self, state, subgroup_index):
        sub_state = state.get(subgroup_index)
        if not isinstance(sub_state, dict):
            sub_state = {}

        ready_raw = sub_state.get("ready")
        if isinstance(ready_raw, set):
            ready_set = ready_raw
        elif isinstance(ready_raw, (list, tuple)):
            ready_set = set(ready_raw)
        else:
            ready_set = set()
        sub_state["ready"] = ready_set

        try:
            sub_state["expected"] = int(sub_state.get("expected", 0))
        except (TypeError, ValueError):
            sub_state["expected"] = 0

        members_raw = sub_state.get("members")
        if isinstance(members_raw, list):
            sub_state["members"] = members_raw
        elif isinstance(members_raw, tuple):
            sub_state["members"] = list(members_raw)
        else:
            sub_state["members"] = []

        try:
            sub_state["stage"] = int(sub_state.get("stage", 0))
        except (TypeError, ValueError):
            sub_state["stage"] = 0

        sub_state["started"] = bool(sub_state.get("started", False))
        sub_state["completed"] = bool(sub_state.get("completed", False))
        try:
            sub_state["last_update"] = float(sub_state.get("last_update", 0.0))
        except (TypeError, ValueError):
            sub_state["last_update"] = 0.0

        state[subgroup_index] = sub_state
        return sub_state

    def _update_make_party_state(self, updater):
        gid = self._resolve_gid(None)
        with Player._group_var_lock:
            group = Player._group_vars.setdefault(gid, {})
            state = group.get("_make_party_state")
            if not isinstance(state, dict):
                state = {}
            result = updater(state)
            group["_make_party_state"] = state
            return result

    def _safe_party_id(self):
        try:
            return int(self.id)
        except (TypeError, ValueError):
            return self.id

    def _register_make_party_ready(self, subgroup_index, expected_size, member_ids):
        def updater(state):
            sub_state = self._ensure_make_party_substate_mutable(state, subgroup_index)
            if sub_state.get("completed"):
                sub_state["ready"].clear()
                sub_state["started"] = False
                sub_state["completed"] = False
                sub_state["stage"] = 0
                sub_state["members"] = []
                sub_state["expected"] = 0

            sub_state["expected"] = int(expected_size)
            sub_state["members"] = list(member_ids)

            ready_set = sub_state["ready"]
            current_id = self._safe_party_id()
            added = current_id not in ready_set
            if added:
                ready_set.add(current_id)

            ready_count = len(ready_set)
            started_now = False
            if ready_count >= sub_state["expected"] and not sub_state["started"]:
                sub_state["started"] = True
                sub_state["stage"] = 0
                sub_state["completed"] = False
                sub_state["last_update"] = time.time()
                started_now = True

            return added, ready_count, sub_state["expected"], bool(sub_state["started"]), started_now

        return self._update_make_party_state(updater)

    def _wait_for_make_party_start(self, subgroup_index, expected_size):
        def ensure_started(state):
            sub_state = self._ensure_make_party_substate_mutable(state, subgroup_index)
            ready_count = len(sub_state["ready"])
            started_now = False
            if ready_count >= expected_size and not sub_state["started"]:
                sub_state["started"] = True
                sub_state["stage"] = 0
                sub_state["completed"] = False
                sub_state["last_update"] = time.time()
                started_now = True
            return ready_count, bool(sub_state["started"]), started_now

        while not getattr(self, "stop_script", False):
            ready_count, started, _ = self._update_make_party_state(ensure_started)
            if ready_count >= expected_size and started:
                return True
            time.sleep(0.25)
        return False

    def _wait_for_make_party_stage(self, subgroup_index, target_stage):
        while not getattr(self, "stop_script", False):
            state = self._read_make_party_state()
            sub_state = self._normalize_make_party_substate(state.get(subgroup_index))
            if sub_state.get("completed") and sub_state.get("stage", 0) >= target_stage:
                return sub_state
            if sub_state.get("stage", 0) >= target_stage:
                return sub_state
            time.sleep(0.2)
        return None

    def _set_make_party_stage(self, subgroup_index, stage, *, completed=False):
        def updater(state):
            sub_state = self._ensure_make_party_substate_mutable(state, subgroup_index)
            current_stage = int(sub_state.get("stage", 0))
            if stage > current_stage:
                sub_state["stage"] = stage
            if completed:
                sub_state["completed"] = True
            sub_state["last_update"] = time.time()
            return sub_state["stage"], sub_state["completed"]

        return self._update_make_party_state(updater)

    def _finalize_make_party_state(self, subgroup_index):
        def updater(state):
            if subgroup_index not in state:
                return False
            sub_state = self._ensure_make_party_substate_mutable(state, subgroup_index)
            ready_set = sub_state["ready"]
            ready_set.discard(self._safe_party_id())
            sub_state["last_update"] = time.time()
            if not ready_set:
                state.pop(subgroup_index, None)
                return True
            return False

        return self._update_make_party_state(updater)

    def _get_subgroup_membership_info(self, expected_size, subgroup_index):
        try:
            expected = int(expected_size)
        except (TypeError, ValueError):
            return None
        if expected <= 0:
            return None

        party_ids = getattr(self, "partyID", [])
        party_names = getattr(self, "partyname", [])
        if not isinstance(party_ids, list) or len(party_ids) <= 1:
            return None
        if not isinstance(party_names, list):
            party_names = []

        members = []
        for idx in range(1, len(party_ids)):
            pid = party_ids[idx]
            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                continue
            name = party_names[idx] if idx < len(party_names) else None
            if not isinstance(name, str) or not name:
                name = f"Member {pid_int}"
            members.append((pid_int, name))

        if not members:
            return None

        try:
            player_id = int(self.id)
        except (TypeError, ValueError):
            return None

        try:
            target_subgroup = int(subgroup_index)
        except (TypeError, ValueError):
            target_subgroup = None
        if target_subgroup is not None and target_subgroup <= 0:
            target_subgroup = None

        subgroup_map = {}
        order_map = {}
        if target_subgroup is not None:
            raw_map = getattr(self, "party_subgroups", None)
            if isinstance(raw_map, dict):
                for key, subgroup_value in raw_map.items():
                    try:
                        pid_int = int(key)
                        subgroup_int = int(subgroup_value)
                    except (TypeError, ValueError):
                        continue
                    if subgroup_int > 0:
                        subgroup_map[pid_int] = subgroup_int
            raw_order = getattr(self, "party_subgroup_order", None)
            if isinstance(raw_order, dict):
                for key, order_value in raw_order.items():
                    try:
                        pid_int = int(key)
                        order_int = int(order_value)
                    except (TypeError, ValueError):
                        continue
                    if order_int >= 0:
                        order_map[pid_int] = order_int

        if target_subgroup is not None and subgroup_map:
            filtered_members = []
            contains_player = False
            for enum_index, (pid, name) in enumerate(members):
                if subgroup_map.get(pid) == target_subgroup:
                    order = order_map.get(pid)
                    filtered_members.append((pid, name, order, enum_index))
                    if pid == player_id:
                        contains_player = True
            if (
                contains_player
                and len(filtered_members) == expected
            ):
                filtered_members.sort(
                    key=lambda item: (
                        item[2] is None,
                        item[2] if item[2] is not None else item[3],
                        item[0],
                    )
                )
                member_ids = [pid for pid, _name, _order, _idx in filtered_members]
                member_names = [name for _pid, name, _order, _idx in filtered_members]
                try:
                    position = next(
                        idx for idx, pid in enumerate(member_ids) if pid == player_id
                    )
                except StopIteration:
                    position = None
                if position is not None:
                    return member_ids, member_names, position, target_subgroup

        try:
            global_index = next(i for i, info in enumerate(members) if info[0] == player_id)
        except StopIteration:
            return None

        computed_subgroup = (global_index // expected) + 1
        start_index = (computed_subgroup - 1) * expected
        end_index = start_index + expected
        if end_index > len(members):
            return None

        subgroup_members = members[start_index:end_index]
        member_ids = [pid for pid, _ in subgroup_members]
        member_names = [name for _, name in subgroup_members]
        position = global_index - start_index

        return member_ids, member_names, position, computed_subgroup

    def make_party(self, condition_index=0):
        if condition_index in (0, 2):
            state = getattr(self, "_make_party_condition_state", 0)
            if condition_index == 2:
                return 2 if state == 2 else 0
            return 0 if state == 2 else 2

        if getattr(self, "stop_script", False):
            return self._record_make_party_result(False)

        api = getattr(self, "api", None)
        if api is None:
            print(f"[MEMBER] {self.name} cannot create party because the API is unavailable.")
            return self._record_make_party_result(False)

        try:
            subgroup_index = int(getattr(self, "subgroup_index", 0))
        except (TypeError, ValueError):
            subgroup_index = 0
        if subgroup_index <= 0:
            print(f"[MEMBER] {self.name} cannot create party because subgroup index is undefined.")
            return self._record_make_party_result(False)

        try:
            expected_size = int(getattr(self, "subgroup_member_limit", 0))
        except (TypeError, ValueError):
            expected_size = 0

        if expected_size not in (2, 3):
            print("You cannot create parties with the current number of members per subgroup.")
            return self._record_make_party_result(False)

        membership = self._get_subgroup_membership_info(expected_size, subgroup_index)
        if membership is None:
            print(f"[MEMBER] {self.name} cannot determine subgroup composition for party creation.")
            return self._record_make_party_result(False)

        member_ids, member_names, position, effective_subgroup = membership
        if len(member_ids) != expected_size:
            print(f"[MEMBER] {self.name} cannot create party because subgroup members are incomplete.")
            return self._record_make_party_result(False)

        # reset state before attempting to coordinate party creation
        self._make_party_condition_state = 0

        subgroup_key = effective_subgroup if effective_subgroup > 0 else subgroup_index

        added, ready_count, stored_expected, started, _ = self._register_make_party_ready(
            subgroup_key,
            expected_size,
            member_ids,
        )

        if added:
            print(
                f"[MEMBER] {self.name} Subgroup [{subgroup_key}] have {ready_count} "
                f"member waiting to make party"
            )

        if stored_expected not in (2, 3):
            print("You cannot create parties with the current number of members per subgroup.")
            return self._record_make_party_result(False)

        if ready_count < stored_expected or not started:
            if not self._wait_for_make_party_start(subgroup_key, stored_expected):
                return self._record_make_party_result(False)

        prev_id = member_ids[position - 1] if position > 0 else None
        next_id = member_ids[position + 1] if position < stored_expected - 1 else None
        prev_name = member_names[position - 1] if position > 0 else None
        next_name = member_names[position + 1] if position < stored_expected - 1 else None

        final_stage = 2 if stored_expected == 2 else 4

        if position == 0:
            stage_state = self._wait_for_make_party_stage(subgroup_key, 0)
            if stage_state is None:
                return self._record_make_party_result(False)
            delay = self.randomize_delay(0.75, 1.5)
            if delay > 0:
                time.sleep(delay)
            if next_id is None:
                print(f"[MEMBER] {self.name} cannot find the next member to invite.")
                return self._record_make_party_result(False)
            print(f"[MEMBER] {self.name} invited {next_name} to the party")
            try:
                api.send_packet(f"pjoin 0 {next_id}")
            except Exception as error:
                print(f"[MEMBER] {self.name} failed to invite {next_name}: {error}")
                return self._record_make_party_result(False)
            self._set_make_party_stage(subgroup_key, 1)

        elif position == 1:
            stage_state = self._wait_for_make_party_stage(subgroup_key, 1)
            if stage_state is None:
                return self._record_make_party_result(False)
            delay = self.randomize_delay(1, 2)
            if delay > 0:
                time.sleep(delay)
            if prev_id is None:
                print(f"[MEMBER] {self.name} does not know who invited them to the party.")
                return self._record_make_party_result(False)
            print(
                f"[MEMBER] {self.name} accepted the party invitation from {prev_name}"
            )
            try:
                api.send_packet(f"#pjoin^3^{prev_id}")
            except Exception as error:
                print(f"[MEMBER] {self.name} failed to accept the party invitation: {error}")
                return self._record_make_party_result(False)
            if stored_expected == 2:
                self._set_make_party_stage(subgroup_key, 2, completed=True)
            else:
                self._set_make_party_stage(subgroup_key, 2)
                time.sleep(2)
                if next_id is None:
                    print(f"[MEMBER] {self.name} cannot find the next member to invite.")
                    return self._record_make_party_result(False)
                print(f"[MEMBER] {self.name} invited {next_name} to the party")
                try:
                    api.send_packet(f"pjoin 0 {next_id}")
                except Exception as error:
                    print(f"[MEMBER] {self.name} failed to invite {next_name}: {error}")
                    return self._record_make_party_result(False)
                self._set_make_party_stage(subgroup_key, 3)

        elif position == 2:
            stage_state = self._wait_for_make_party_stage(subgroup_key, 3)
            if stage_state is None:
                return self._record_make_party_result(False)
            delay = self.randomize_delay(1, 2)
            if delay > 0:
                time.sleep(delay)
            if prev_id is None:
                print(f"[MEMBER] {self.name} does not know who invited them to the party.")
                return self._record_make_party_result(False)
            print(
                f"[MEMBER] {self.name} accepted the party invitation from {prev_name}"
            )
            try:
                api.send_packet(f"#pjoin^3^{prev_id}")
            except Exception as error:
                print(f"[MEMBER] {self.name} failed to accept the party invitation: {error}")
                return self._record_make_party_result(False)
            self._set_make_party_stage(subgroup_key, 4, completed=True)

        else:
            print(f"[MEMBER] {self.name} has an unsupported position inside the subgroup.")
            return self._record_make_party_result(False)

        completion_state = self._wait_for_make_party_stage(subgroup_key, final_stage)
        if completion_state is None:
            return self._record_make_party_result(False)

        self._finalize_make_party_state(subgroup_key)
        return self._record_make_party_result(True)

    def rolename(self) -> str:
        """Return a fantasy-style name up to 12 characters."""
        name = random.choice(PREFIXES) + random.choice(ROOTS) + random.choice(SUFFIXES)
        return name[:12]

    def packetlogger(self):
        while self.api.working():
            if not self.api.empty():
                msg = self.api.get_message()
                json_msg = json.loads(msg)
                if json_msg["type"] == phoenix.Type.packet_send.value:
                    packet = json_msg["packet"]
                    splitPacket = packet.split()
                    if splitPacket[0] == "select":
                        gfless_api.close_login_pipe()
                    #print(f"[SEND]: {packet}")
                    if splitPacket[0] == "walk":
                        self.pos_x, self.pos_y = int(splitPacket[1]), int(splitPacket[2])
                    for i, cond in list(enumerate(self.send_packet_conditions)):
                        try:
                            if cond[2]:
                                self.exec_send_packet_condition(
                                    cond[1],
                                    packet,
                                    i,
                                    cond[0],
                                )
                        except Exception as e:
                            self.log(f"Error scheduling send_packet condition: {e}")
                if json_msg["type"] == phoenix.Type.packet_recv.value:
                    packet = json_msg["packet"]
                    splitPacket = packet.split()
                    #print(f"[RECV]: {packet}")
                    if splitPacket[0] == ("stat"):
                        self.current_hp = int(splitPacket[1])
                        self.max_hp = int(splitPacket[2])
                        self.current_mp = int(splitPacket[3])
                        self.max_mp = int(splitPacket[4])
                        self.hp_percent = int((self.current_hp/self.max_hp)*100)
                        self.mp_percent = int((self.current_mp/self.max_mp)*100)
                    if splitPacket[0] == ("c_info"):
                        self.name = splitPacket[1]
                        self.id = splitPacket[6]
                        self.sp = splitPacket[15]
                    if splitPacket[0] == ("at"):
                        self.pos_x, self.pos_y = int(splitPacket[3]), int(splitPacket[4])
                    if splitPacket[0] == ("cond"):
                        self.can_attack = bool(int(splitPacket[3]))
                        self.can_move = bool(int(splitPacket[4]))
                        self.speed = splitPacket[5]
                    if splitPacket[0] == ("c_map"):
                        if splitPacket[3] == "1":
                            t_q = threading.Thread(target=self.queries, args=[1.5, False, False, False, True, ])
                            t_q.start()
                            t_mp = threading.Thread(target=self.update_map_change)
                            t_mp.start()
                            self.map_id = int(splitPacket[2])
                            self.map_array = loadMap(self.map_id)
                    if splitPacket[0] == ("gold"):
                        self.gold = int(splitPacket[1])
                    if splitPacket[0] == ("lev"):
                        self.lvl = splitPacket[1]
                        self.lvl_xp_current = splitPacket[2]
                        self.job_lvl = splitPacket[3]
                        self.job_lvl_xp_current = splitPacket[4]
                        self.lvl_xp_max = splitPacket[5]
                        self.c_lvl_xp_current = splitPacket[9]
                        self.c_lvl = splitPacket[10]
                        self.c_lvl_xp_max = splitPacket[11]
                    if splitPacket[0] == ("ivn"):
                        self.api.query_inventory()
                    if splitPacket[0] == ("ski"):
                        self.api.query_skills_info()
                    if splitPacket[0] == ("get"):
                        for entry in self.items[:]: 
                            if entry['id'] == int(splitPacket[3]):
                                self.items.remove(entry)
                                break
                    if splitPacket[0] == ("out"):
                        entity_type = int(splitPacket[1])
                        entity_id = int(splitPacket[2])

                        if entity_type == 1:
                            for entry in self.players[:]: 
                                if entry['id'] == entity_id:
                                    self.players.remove(entry)
                                    break
                        if entity_type == 2:
                            for entry in self.npcs[:]: 
                                if entry['id'] == entity_id:
                                    self.npcs.remove(entry)
                                    break
                        if entity_type == 3:
                            for entry in self.monsters[:]: 
                                if entry['id'] == entity_id:
                                    self.monsters.remove(entry)
                                    break
                        if entity_type == 9:
                            for entry in self.items[:]: 
                                if entry['id'] == entity_id:
                                    self.items.remove(entry)
                                    break
                    if splitPacket[0] == ("mv"):
                        entity_type = int(splitPacket[1])
                        entity_id = int(splitPacket[2])
                        entity_x = int(splitPacket[3])
                        entity_y = int(splitPacket[4])

                        if entity_type == 1:
                            for entry in self.players[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                        if entity_type == 2:
                            for entry in self.npcs[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                        if entity_type == 9:
                            for entry in self.items[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                    if splitPacket[0] == ("drop"):
                        new_entity = {"id": int(splitPacket[2]), 
                                      "name": "unknown", 
                                      "owner_id": "unknown", 
                                      "quantity": int(splitPacket[5]), 
                                      "vnum": int(splitPacket[1]), 
                                      "x": int(splitPacket[3]), 
                                      "y": int(splitPacket[4])}
                        self.items.append(new_entity)
                    if splitPacket[0] == ("in"):
                        entity_type = int(splitPacket[1])
                        if entity_type == 1:
                            new_entity = {"champion_level": int(splitPacket[39]), 
                                          "family": splitPacket[3], 
                                          "hp_percent": splitPacket[14], 
                                          "id": int(splitPacket[4]), 
                                          "level": int(splitPacket[33]), 
                                          "mp_percent": int(splitPacket[15]), 
                                          "name": splitPacket[2], 
                                          "x": int(splitPacket[5]), 
                                          "y": int(splitPacket[6])}
                            self.players.append(new_entity)
                        if entity_type == 2:
                            new_entity = {"hp_percent": splitPacket[7], 
                                          "id": int(splitPacket[3]), 
                                          "mp_percent": int(splitPacket[8]), 
                                          "name": "unknown",
                                          "vnum": splitPacket[2], 
                                          "x": int(splitPacket[4]), 
                                          "y": int(splitPacket[5])}
                            self.npcs.append(new_entity)
                        if entity_type == 3:
                            new_entity = {"hp_percent": splitPacket[7], 
                                          "id": int(splitPacket[3]), 
                                          "mp_percent": int(splitPacket[8]), 
                                          "name": "unknown",
                                          "vnum": splitPacket[2], 
                                          "x": int(splitPacket[4]), 
                                          "y": int(splitPacket[5])}
                            self.monsters.append(new_entity)
                    if splitPacket[0] == ("su"):
                        attacker_entity_type = int(splitPacket[1])
                        attacker_entity_id = int(splitPacket[2])
                        defender_entity_type = int(splitPacket[3])
                        defender_entity_id = int(splitPacket[4])

                        if defender_entity_type == 3:
                            for entry in self.monsters[:]: 
                                if entry['id'] == defender_entity_id:
                                    entry["hp_percent"] = int(splitPacket[12])
                                    if entry["hp_percent"] == 0:
                                        self.monsters.remove(entry)
                                    break
                    for i, cond in list(enumerate(self.recv_packet_conditions)):
                        try:
                            if cond[2]:
                                self.exec_recv_packet_condition(
                                    cond[1],
                                    packet,
                                    i,
                                    cond[0],
                                )
                        except Exception as e:
                            self.log(f"Error scheduling recv_packet condition: {e}")
                if json_msg["type"] == phoenix.Type.query_player_info.value:
                    player_info = json_msg["player_info"]
                    self.id = player_info["id"]
                    self.name = player_info["name"]
                    self.pos_x = player_info["x"]
                    self.pos_y = player_info["y"]
                    self.map_id = player_info["map_id"]
                    self.level = player_info["level"]
                    self.champion_level = player_info["champion_level"]
                    self.hp_percent = player_info["hp_percent"]
                    self.mp_percent = player_info["mp_percent"]
                    self.is_resting = player_info["is_resting"]
                    self.map_array = loadMap(self.map_id)
                if json_msg["type"] == phoenix.Type.query_inventory.value:
                    inventory = json_msg["inventory"]
                    self.equip = inventory["equip"]
                    self.etc = inventory["etc"]
                    self.gold = inventory["gold"]
                    self.main = inventory["main"]
                if json_msg["type"] == phoenix.Type.query_skills_info.value:
                    self.skills = json_msg["skills"]
                if json_msg["type"] == phoenix.Type.query_map_entities.value:
                    self.items = json_msg["items"]
                    self.monsters = json_msg["monsters"]
                    self.npcs = json_msg["npcs"]
                    self.players = json_msg["players"]
            else:
                time.sleep(0.003)
        self.log(f"{self.name} lost connection")
        self.api.close()
        # purge any queued walk commands to avoid errors after disconnect
        with self.walk_queue.mutex:
            self.walk_queue.queue.clear()
        # attempt to reconnect before giving up
        for delay in (1, 2, 4, 8):
            if self.stop_script:
                break
            try:
                self.api = phoenix.Api(self.port)
                threading.Thread(target=self.packetlogger, daemon=True).start()
                return
            except OSError:
                time.sleep(delay)
        self.stop_script = True
        if callable(self.on_disconnect):
            try:
                self.on_disconnect(self)
            except Exception as e:
                self.log(f"Error in disconnect callback: {e}")

    def _process_walk_queue(self):
        while True:
            func, args = self.walk_queue.get()
            if not self.api.working() or self.stop_script:
                continue
            try:
                func(*args)
            except OSError as e:
                if getattr(e, "winerror", None) == 10053:
                    continue
                self.log(f"Error executing walk command: {e}")
            except Exception as e:
                self.log(f"Error executing walk command: {e}")
    
    async def walk_to_point(self, point, radius=0, walk_with_pet=True, skip=4, timeout=3, proximity=2):
        """Walk the player to ``point`` using non-blocking asyncio primitives.

        ``point`` may be a sequence ``[x, y]`` or an object exposing ``x`` and
        ``y``. ``radius`` adds a random offset to the destination; if the
        resulting point is unreachable, the original coordinates are used as a
        fallback. Parameters ``walk_with_pet``, ``skip`` and ``timeout`` mirror
        the behaviour of the old API. ``skip`` defaults to three nodes (roughly
        four cells between waypoints) and ``timeout`` to three seconds. The
        walk will abort if the map changes during execution. ``proximity``
        defines how close the player must be to a node before it is considered
        reached.
          """

        with self.walk_lock:
            cond = getattr(self._periodic_ctx, "current", None)
            if cond:
                now = time.time()
                last = self._last_periodic_walk.get(cond, 0)
                if cond in self._periodic_walking or now - last < 10:
                    return
                self._periodic_walking.add(cond)

        # Normalise the point into a plain list of coordinates
        if hasattr(point, "x") and hasattr(point, "y"):
            point = [point.x, point.y]
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            point = list(point)
        else:
            raise TypeError("point must be a sequence or expose 'x' and 'y'")

        # Allow ``radius`` to be passed as a string
        if isinstance(radius, str):
            try:
                radius = int(radius)
            except ValueError:
                radius = 0

        target = point[:]  # keep original destination for fallback
        if radius > 0:
            rand_x = random.randint(-radius, radius)
            rand_y = random.randint(-radius, radius)
            point = [point[0] + rand_x, point[1] + rand_y]

        api = self.api
        start_map = self.map_id
        loop = asyncio.get_running_loop()
        try:
            while True:
                player_pos = [self.pos_x, self.pos_y]
                start_time = time.perf_counter()
                Path = await loop.run_in_executor(
                    self._path_executor,
                    findPath,
                    player_pos,
                    [point[0], point[1]],
                    self.map_array,
                    self.map_id,
                )
                elapsed = time.perf_counter() - start_time
                if Path == [] and radius > 0:
                    start_time = time.perf_counter()
                    Path = await loop.run_in_executor(
                        self._path_executor,
                        findPath,
                        player_pos,
                        target,
                        self.map_array,
                        self.map_id,
                    )
                    elapsed = time.perf_counter() - start_time
                    point = target
                if Path == []:
                    self.log("Failed to find a path")
                    break
                self.log(f"Path found in {elapsed:.3f} seconds")
                lastpath = len(Path) - 1
                success = True
                for i in range(0, len(Path), skip):
                    if self.stop_script or self.map_id != start_map:
                        return
                    node = Path[i]
                    if hasattr(node, "x") and hasattr(node, "y"):
                        x, y = node.x, node.y
                    else:
                        x, y = node[0], node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (x, y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (x, y)))
                    startTimer = time.time()
                    resend = max(0.5, timeout / 3)
                    deadline = startTimer + timeout * 4
                    last_send = startTimer
                    while True:
                        if self.map_id != start_map:
                            return
                        if math.hypot(self.pos_x - x, self.pos_y - y) <= proximity:
                            break
                        now = time.time()
                        if now >= deadline:
                            success = False
                            break
                        if self.stop_script:
                            raise SystemExit
                        if now - last_send >= resend:
                            with self.walk_lock:
                                self.walk_queue.put((api.player_walk, (x, y)))
                                if walk_with_pet:
                                    self.walk_queue.put((api.pets_walk, (x, y)))
                            last_send = now
                        await asyncio.sleep(0.05)
                    if not success:
                        break
                if success:
                    last_node = Path[lastpath]
                    if hasattr(last_node, "x") and hasattr(last_node, "y"):
                        last_x, last_y = last_node.x, last_node.y
                    else:
                        last_x, last_y = last_node[0], last_node[1]
                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (last_x, last_y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (last_x, last_y)))
                    break
                else:
                    await asyncio.sleep(resend)
                    continue
        except Exception as e:
            self.log(f"Error in walk_to_point: {e}")
        finally:
            if cond:
                with self.walk_lock:
                    self._periodic_walking.discard(cond)
                    self._last_periodic_walk[cond] = time.time()


    async def walk_and_switch_map(self, point, walk_with_pet=True, skip=3, timeout=3):
        """Walk to ``point`` and wait for a map change using asyncio."""

        # Normalise ``point`` just like in ``walk_to_point``
        if hasattr(point, "x") and hasattr(point, "y"):
            point = [point.x, point.y]
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            point = list(point)
        else:
            raise TypeError("point must be a sequence or expose 'x' and 'y'")

        player_pos = [self.pos_x, self.pos_y]
        api = self.api
        loop = asyncio.get_running_loop()
        try:
            Path = await loop.run_in_executor(
                self._path_executor,
                findPath,
                player_pos,
                [point[0], point[1]],
                self.map_array,
                self.map_id,
            )
            if Path:
                for i in range(skip, len(Path), skip):
                    if self.stop_script:
                        raise SystemExit
                    node = Path[i]
                    if hasattr(node, "x") and hasattr(node, "y"):
                        x, y = node.x, node.y
                    else:
                        x, y = node[0], node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (x, y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (x, y)))
                    startTimer = time.time()
                    resend = max(0.5, timeout / 3)
                    deadline = startTimer + timeout * 4
                    last_send = startTimer
                    while True:
                        if abs(self.pos_x - x) <= 1 and abs(self.pos_y - y) <= 1:
                            break
                        now = time.time()
                        if now >= deadline:
                            break
                        if self.stop_script:
                            raise SystemExit
                        if now - last_send >= resend:
                            with self.walk_lock:
                                self.walk_queue.put((api.player_walk, (x, y)))
                                if walk_with_pet:
                                    self.walk_queue.put((api.pets_walk, (x, y)))
                            last_send = now
                        await asyncio.sleep(0.05)
                start = time.time()
                while not self.map_changed and time.time() - start < 10:
                    random_x = random.choice([-1, 1, 0])
                    random_y = random.choice([-1, 1, 0])
                    last_node = Path[lastpath]
                    if hasattr(last_node, "x") and hasattr(last_node, "y"):
                        base_x, base_y = last_node.x, last_node.y
                    else:
                        base_x, base_y = last_node[0], last_node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (base_x + random_x, base_y + random_y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (base_x + random_x, base_y + random_y)))
                    for _ in range(50):
                        await asyncio.sleep(0.1)
                        if self.map_changed:
                            break
                if not self.map_changed:
                    self.log("timeout waiting for map change")
                else:
                    self.log("reached new map")
            else:
                self.log("Failed to find a path")
        except Exception as e:
            self.log(f"Error in walk_and_switch_map: {e}")

    def use_item(self, item_vnum, inventory_type):
        if inventory_type == "equip":
            for item in self.equip:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"wear {item_position} 0")
                    return True
        if inventory_type == "main":
            for item in self.main:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"u_i 1 {self.id} 1 {item_position} 0 0")
                    return True
        if inventory_type == "etc":
            for item in self.etc:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"u_i 1 {self.id} 2 {item_position} 0 0")
                    return True

        self.log(f"Couldnt find item with vnum: {item_vnum} in inventory: {inventory_type}")
        return False

    def put_items_in_trade(self, items, gold=0):
        inv_blocks = {
            0: self.equip,
            1: self.main,
            2: self.etc,
        }

        packet_parts = ["exc_list", str(int(gold)), "0"]
        for inv_type, vnum, amount in items:
            block = inv_blocks.get(inv_type, [])
            best_slot = None
            best_qty = 0
            for item in block:
                if item.get("vnum") == vnum:
                    slot = item.get("position")
                    qty = item.get("quantity", item.get("amount", item.get("count", 0)))
                    if qty >= amount:
                        best_slot = slot
                        best_qty = amount
                        break
                    elif qty > best_qty:
                        best_slot = slot
                        best_qty = qty
            if best_slot is None or best_qty == 0:
                self.log("Insufficient items to exchange")
                return False
            packet_parts.extend([str(inv_type), str(best_slot), str(best_qty)])

        if gold > 0 or len(packet_parts) > 3:
            self.api.send_packet(" ".join(packet_parts))
            return True
        self.log("Insufficient items to exchange")
        return False

    def put_item_in_trade(self, items, gold=0):
        return self.put_items_in_trade(items, gold=gold)

    def update_map_change(self):
        self.map_changed = True
        time.sleep(0.5)
        self.map_changed = False

    def find_field(self, a, b, a_angle, b_angle):
        return calculate_field_location([int(a[0]), int(a[1])], [int(b[0]), int(b[1])], float(a_angle), float(b_angle), self.map_array)
        
    def find_point_b(self, x, y, angle, offset = 20):
        return calculate_point_B_position(int(x), int(y), float(angle), self.map_array, offset)

    def randomize_delay(self, min_val, max_val, decimals=1000):
        if min_val <= 0 and max_val <= 0:
            return 0
        if min_val > max_val:
            temp_val = min_val
            min_val = max_val
            max_val = temp_val
        if min_val == max_val:
            return min_val

        min_i = int(min_val * decimals)
        max_i = int(max_val * decimals)

        return random.randint(min_i, max_i) / decimals

    def queries(self, delay=1, player_info = True, inventory = True, skills = True, entities = True):
        time.sleep(delay)
        # calling queries
        if player_info:
            self.api.query_player_information()
            time.sleep(delay)
        if inventory:
            self.api.query_inventory()
            time.sleep(delay)
        if skills:
            self.api.query_skills_info()
            time.sleep(delay)
        if entities:
            self.api.query_map_entities()
    
    def exec_recv_packet_condition(self, code, packet, index, cond_name):
        with use_group_console(self.get_console_for_output()):
            try:
                cached = self._compiled_recv_conditions.get(cond_name)
                if not cached or cached[0] != code:
                    func = self._compile_condition(code, with_packet=True)
                    self._compiled_recv_conditions[cond_name] = (code, func)
                else:
                    func = cached[1]
                asyncio.run_coroutine_threadsafe(
                    self._run_packet_condition(
                        cond_name, func, packet, self.recv_packet_conditions, "recv_packet"
                    ),
                    self.loop,
                )
            except Exception as e:
                    try:
                        self.recv_packet_conditions.pop(index)
                        self._compiled_recv_conditions.pop(cond_name, None)
                        self.log(
                            f"\nError executing recv_packet condition: {cond_name}\nError: {e}\nCondition was removed."
                        )
                    except Exception as e2:
                        self.log(f"Error removing faulty recv_packet condition: {e2}")

    def exec_send_packet_condition(self, code, packet, index, cond_name):
        with use_group_console(self.get_console_for_output()):
            try:
                cached = self._compiled_send_conditions.get(cond_name)
                if not cached or cached[0] != code:
                    func = self._compile_condition(code, with_packet=True)
                    self._compiled_send_conditions[cond_name] = (code, func)
                else:
                    func = cached[1]
                asyncio.run_coroutine_threadsafe(
                    self._run_packet_condition(
                        cond_name, func, packet, self.send_packet_conditions, "send_packet"
                    ),
                    self.loop,
                )
            except Exception as e:
                try:
                    self.send_packet_conditions.pop(index)
                    self._compiled_send_conditions.pop(cond_name, None)
                    self.log(
                        f"\nError executing send_packet condition: {cond_name}\nError: {e}\nCondition was removed."
                    )
                except Exception as e2:
                    self.log(f"Error removing faulty send_packet condition: {e2}")

    async def exec_periodic_conditions(self):
        """Schedule active periodical conditions in independent tasks.

        This avoids a global tick loop where every condition is checked on
        each iteration, allowing characters with many conditions to run more
        smoothly and independently."""
        while True:
            with use_group_console(self.get_console_for_output()):
                try:
                    with self._periodic_cond_lock:
                        conds = list(enumerate(self.periodical_conditions))
                    for idx, cond in conds:
                        try:
                            if not cond.active:
                                if cond.task:
                                    cond.task.cancel()
                                    cond.task = None
                                cond.last_error = None
                                continue
                            if cond.func is None or cond._code_cache != cond.code:
                                if cond.task:
                                    cond.task.cancel()
                                    cond.task = None
                                cond.func = None
                                cond._code_cache = ""
                                cond.func = self._compile_condition(cond.code)
                                cond._code_cache = cond.code
                            if cond.task is None or cond.task.done():
                                cond.task = asyncio.create_task(self._run_periodic_loop(cond))
                            cond.last_error = None
                        except Exception as cond_error:
                            error_text = f"{cond_error}"
                            signature = f"{error_text}\n{cond.code}"
                            if cond.task:
                                cond.task.cancel()
                                cond.task = None
                            cond.func = None
                            cond._code_cache = ""
                            if cond.last_error != signature:
                                error_type = type(cond_error).__name__
                                self.log(
                                    f"\nError preparing periodical condition '{cond.name}' "
                                    f"(index {idx}): {error_type}: {cond_error}"
                                )
                                lineno = getattr(cond_error, "lineno", None)
                                offset = getattr(cond_error, "offset", None)
                                if lineno is not None:
                                    location = f"line {lineno}"
                                    if offset is not None:
                                        location += f", column {offset}"
                                    self.log(f"    Reported location: {location}.")
                                code_lines = cond.code.splitlines()
                                if code_lines:
                                    self.log("    Condition source:")
                                    highlight = lineno
                                    for line_no, line_text in enumerate(code_lines, start=1):
                                        marker = "->" if highlight == line_no else "  "
                                        self.log(f"    {marker} {line_no:>4}: {line_text}")
                                else:
                                    self.log("    Condition source is empty.")
                            cond.last_error = signature
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.log(f"Error executing periodic conditions loop: {e}")
                    await asyncio.sleep(0.1)

    async def _run_periodic_loop(self, cond: PeriodicCondition):
        try:
            while True:
                await self._run_periodic_condition(cond.name, cond.func)
                await asyncio.sleep(cond.interval * 0.02)
        except asyncio.CancelledError:
            pass

    def _compile_condition(self, script, with_packet=False):
        """Compile a condition script into an async callable, replacing time.sleep with await asyncio.sleep."""
        func_name = f"_cond_func_{self._cond_counter}"
        self._cond_counter += 1

        tree = ast.parse(script, mode="exec")

        class AwaitTransformer(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                ):
                    # Replace time.sleep with await asyncio.sleep
                    if node.func.value.id == "time" and node.func.attr == "sleep":
                        new_call = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="asyncio", ctx=ast.Load()),
                                attr="sleep",
                                ctx=ast.Load(),
                            ),
                            args=node.args,
                            keywords=node.keywords,
                        )
                        return ast.Await(value=new_call)
                    # Ensure asynchronous Player methods are awaited
                    if node.func.value.id == "self" and node.func.attr in {
                        "walk_to_point",
                        "walk_and_switch_map",
                    }:
                        return ast.Await(value=node)
                    # Offload known blocking Player methods to a thread so
                    # condition execution doesn't block the event loop.
                    if node.func.value.id == "self" and node.func.attr in {
                        "queries",
                        "update_map_change",
                    }:
                        player_method = ast.Attribute(
                            value=ast.Name(id="self", ctx=ast.Load()),
                            attr=node.func.attr,
                            ctx=ast.Load(),
                        )
                        new_call = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="asyncio", ctx=ast.Load()),
                                attr="to_thread",
                                ctx=ast.Load(),
                            ),
                            args=[player_method] + node.args,
                            keywords=node.keywords,
                        )
                        return ast.Await(value=new_call)
                return node

        tree = AwaitTransformer().visit(tree)
        ast.fix_missing_locations(tree)

        args = [ast.arg(arg="self")]
        if with_packet:
            args.append(ast.arg(arg="packet"))

        func_def = ast.AsyncFunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=args,
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=tree.body,
            decorator_list=[],
        )

        module = ast.Module(body=[func_def], type_ignores=[])
        ast.fix_missing_locations(func_def)
        ast.fix_missing_locations(module)
        globs = {
            "asyncio": asyncio,
            "time": self._time_namespace,
            "selfgroup": self._group,
            "selfsubg": self._subgroup,
            "cond": self._cond_control,
            "print": self._console_print,
        }
        exec(compile(module, func_name, "exec"), globs)
        return globs[func_name]

    def _set_condition_running(self, cond_type, name, running):
        with self._condition_state_lock:
            state = self._condition_state.setdefault(cond_type, set())
            if running:
                state.add(name)
            else:
                state.discard(name)

    def get_condition_status(self, cond_type, name):
        with self._condition_state_lock:
            state = self._condition_state.get(cond_type, set())
            if name in state:
                return "current"
        return None

    async def _run_packet_condition(self, name, func, packet, store_list, cond_type):
        with use_group_console(self.get_console_for_output()):
            self._set_condition_running(cond_type, name, True)
            self._record_condition_activity(cond_type, name)
            token = self._condition_ctx.set((cond_type, name))
            try:
                await func(self, packet)
            except Exception as e:
                try:
                    for idx, cond in enumerate(store_list):
                        if cond[0] == name:
                            store_list.pop(idx)
                            break
                    self.log(
                        f"\nError executing {cond_type} condition: {name}\nError: {e}\nCondition was removed."
                    )
                except Exception as e2:
                    self.log(f"Error removing faulty {cond_type} condition: {e2}")
            finally:
                self._condition_ctx.reset(token)
                self._set_condition_running(cond_type, name, False)

    async def _run_periodic_condition(self, name, func):
        with use_group_console(self.get_console_for_output()):
            self._set_condition_running("periodical", name, True)
            self._record_condition_activity("periodical", name)
            self._periodic_ctx.current = name
            token = self._condition_ctx.set(("periodical", name))
            try:
                await func(self)
            except Exception as e:
                try:
                    with self._periodic_cond_lock:
                        for idx, cond in enumerate(self.periodical_conditions):
                            if cond.name == name:
                                if cond.task:
                                    cond.task.cancel()
                                self.periodical_conditions.pop(idx)
                                break
                    self.log(
                        f"\nError executing periodical condition: {name}\nError: {e}\nCondition was removed."
                    )
                except Exception:
                    self.log(
                        f"\nError executing periodical condition: {name}\nError: {e}\nCondition was removed."
                    )
            finally:
                self._condition_ctx.reset(token)
                self._set_condition_running("periodical", name, False)
                self._periodic_ctx.current = None
   
    # there was some issue with calling packet.split directly in some rare cases, hence this function
    def split_packet(self, packet, delimeter = " "):
        return packet.split(delimeter)

    def reset_attrs(self):
        """Reset attr1 through attr99 to 0 and clear leader info."""
        current_group = getattr(self, "attr19", 0)
        try:
            current_group = int(current_group)
        except (TypeError, ValueError):
            current_group = 0
        if current_group > 0:
            with Player._subgroup_var_lock:
                Player._subgroup_vars.pop(current_group, None)
        for i in range(1, 100):
            setattr(self, f'attr{i}', 0)
        self.leadername = ""
        self.leaderID = 0
        self.subgroup_index = None
        self.subgroup_member_limit = 0
        self.party_subgroups = {}
        self.party_subgroup_order = {}

    def reset_group_runtime(self):
        """Stop scripts, cancel condition tasks and clear shared state."""

        self.stop_script = True
        self.script_loaded = False
        self.clear_group_console_buffer()

        cancel_event = threading.Event()

        def _cancel_tasks():
            try:
                if getattr(self, "_periodic_main_task", None):
                    try:
                        self._periodic_main_task.cancel()
                    except Exception:
                        pass
                self._periodic_main_task = None

                with self._periodic_cond_lock:
                    conds = list(self.periodical_conditions)
                    self.periodical_conditions = []

                for cond in conds:
                    task = getattr(cond, "task", None)
                    if task:
                        try:
                            task.cancel()
                        except Exception:
                            pass
                    cond.task = None
                    cond.func = None
                    cond.last_error = None
            finally:
                cancel_event.set()

        loop = getattr(self, "loop", None)
        if loop and loop.is_running():
            try:
                loop.call_soon_threadsafe(_cancel_tasks)
            except RuntimeError:
                _cancel_tasks()
            else:
                cancel_event.wait(0.5)
        else:
            _cancel_tasks()

        self.recv_packet_conditions = []
        self.send_packet_conditions = []
        if hasattr(self, "_compiled_recv_conditions"):
            self._compiled_recv_conditions.clear()
        if hasattr(self, "_compiled_send_conditions"):
            self._compiled_send_conditions.clear()

        self._condition_state = {
            "recv_packet": set(),
            "send_packet": set(),
            "periodical": set(),
        }
        self._cond_counter = 0
        if hasattr(self, "_condition_activity_by_name"):
            self._condition_activity_by_name.clear()
        self._last_condition_activity = time.monotonic()
        self._last_condition_state_change = self._last_condition_activity

        self._periodic_walking.clear()
        self._last_periodic_walk.clear()
        self._periodic_ctx = threading.local()
        try:
            # ensure any lingering context state is cleared without replacing the
            # ContextVar instance so existing tokens remain valid
            self._condition_ctx.set(None)
        except LookupError:
            # nothing was ever set for this context
            pass

        try:
            while True:
                self.walk_queue.get_nowait()
        except Empty:
            pass

        executor = getattr(self, "_cond_executor", None)
        if executor:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._cond_executor = ThreadPoolExecutor(max_workers=4)

        gid = None
        if getattr(self, "leaderID", 0):
            gid = self.leaderID
        elif getattr(self, "_current_gid", None) is not None:
            gid = self._current_gid
        if gid is not None:
            with Player._group_var_lock:
                Player._group_vars.pop(gid, None)
        current_group = getattr(self, "attr19", 0)
        try:
            current_group = int(current_group)
        except (TypeError, ValueError):
            current_group = 0
        if current_group > 0:
            with Player._subgroup_var_lock:
                Player._subgroup_vars.pop(current_group, None)
        self._current_gid = self._unique_group_id
        self.subgroup_index = None
        self.subgroup_member_limit = 0

    def invite_members(self):
        """Invite all stored group members with a 3-second delay between invites."""
        if not isinstance(self.attr51, list):
            return
        for name in self.attr51:
            try:
                self.api.send_packet(f"$Invite {name}")
                time.sleep(3)
            except Exception as e:
                self.log(f"Failed to invite {name}: {e}")

    def close_game(self):
        """Terminate the Nostale client associated with this player."""
        pid = None
        if psutil is not None:
            try:
                for conn in psutil.net_connections(kind="tcp"):
                    if conn.laddr and conn.laddr.port == self.port and conn.pid:
                        pid = conn.pid
                        break
            except Exception:
                pass

        if pid is None:
            try:
                wins = pwc.getWindowsWithTitle("Nostale")
                if wins:
                    pid = wins[0].getPid()
            except Exception:
                pass

        win = None
        if pid:
            try:
                subprocess.check_call(["taskkill", "/PID", str(pid), "/F"])
                return True
            except subprocess.CalledProcessError:
                pass

            try:
                subprocess.check_call([
                    "wmic",
                    "process",
                    "where",
                    f"processid={pid}",
                    "call",
                    "terminate",
                ])
                return True
            except Exception:
                pass

            try:
                wins = pwc.getWindowsWithTitle("Nostale")
                if wins:
                    win = wins[0]
            except Exception:
                pass

            if win:
                try:
                    win.close()
                    return True
                except Exception:
                    pass
        return False


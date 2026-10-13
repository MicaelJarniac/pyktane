"""A bomb being defused: facts, strikes, module instances, and undo.

Everything that changes during a game lives in `BombState`, an immutable,
JSON-serializable snapshot. `Session` wraps a stack of them: every change
pushes a new snapshot, so `undo` is just a pop and saving is just a dump.

Module states are stored as raw JSON and re-validated by their module on
every use. That keeps `BombState` independent of which packs are installed,
and it guarantees from day one that every module's state round-trips.
"""

__all__: tuple[str, ...] = (
    "FORMAT_VERSION",
    "BombState",
    "Instance",
    "SavedSession",
    "Session",
)

from collections.abc import Mapping
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, JsonValue

from pyktane.base import Answer, Frozen
from pyktane.context import Context
from pyktane.edgework import Count
from pyktane.errors import ConflictError, ModuleStateError, UnknownInstanceError
from pyktane.events import Event, ModuleSolved, Strike
from pyktane.packs import Manual, Pack, Ruleset
lazy from pyktane.facts import Fact
lazy from pyktane.module import AnyModule

FORMAT_VERSION: Final = 1


class Instance(Frozen):
    """One module on the bomb.

    Attributes:
        id: Unique within the bomb, e.g. ``"Memory#2"``.
        module: The module ID.
        state: The module's state, as JSON.
        solved: Whether it has been disarmed.
    """

    id: str
    module: str
    state: JsonValue
    solved: bool = False


class BombState(Frozen):
    """Snapshot of everything known about the bomb.

    Attributes:
        facts: Known facts, as canonical JSON, keyed by fact key.
        strikes: Strikes received so far.
        instances: Modules added so far, in order.
        solve_order: IDs of solved modules, oldest first.
    """

    facts: Mapping[str, JsonValue] = {}
    strikes: Count = 0
    instances: tuple[Instance, ...] = ()
    solve_order: tuple[str, ...] = ()

    def instance(self, instance_id: str) -> Instance:
        """Find an instance by ID.

        Raises:
            UnknownInstanceError: There is no such instance.
        """
        for instance in self.instances:
            if instance.id == instance_id:
                return instance
        known = ", ".join(instance.id for instance in self.instances) or "none"
        msg = f"no module instance {instance_id!r} (known: {known})"
        raise UnknownInstanceError(msg)

    def replace_instance(self, new: Instance) -> Self:
        """Return a copy with the instance of the same ID replaced."""
        instances = tuple(new if old.id == new.id else old for old in self.instances)
        return self.model_copy(update={"instances": instances})

    @property
    def context(self) -> Context:
        """What solvers get to see."""
        return Context(facts=self.facts, strikes=self.strikes, solved=self.solve_order)


class SavedSession(Frozen):
    """On-disk format of a session.

    Attributes:
        format_version: Bumped on incompatible changes to this format.
        ruleset: The pinned packs the session was played with.
        history: Every snapshot, oldest first; the last is current.
    """

    format_version: Literal[1] = FORMAT_VERSION
    ruleset: Ruleset
    history: tuple[BombState, ...]


class Session:
    """A bomb being defused, with undo.

    Example:
        >>> from pyktane.vanilla import PACK
        >>> bomb = Session(Manual([PACK]))
        >>> bomb.set_facts(serial="AB3CD5")
        >>> wires = bomb.add_module("wires")
        >>> bomb.solve(wires, {"wires": ["red", "red", "blue", "blue"]}).instruction
        'Cut the 2nd wire (red).'
    """

    def __init__(
        self, manual: Manual | None = None, history: tuple[BombState, ...] = ()
    ) -> None:
        """Start a session, optionally restoring a history of snapshots.

        Args:
            manual: The rules in play. Defaults to every installed pack.
            history: Snapshots to restore, oldest first.

        Raises:
            UnknownModuleError: A snapshot uses a module the manual lacks.
            pydantic.ValidationError: A module state doesn't validate.
        """
        self.manual: Final = Manual.load() if manual is None else manual
        self._history: list[BombState] = list(history) or [BombState()]
        for state in self._history:  # Fail now rather than mid-game.
            for instance in state.instances:
                self._load_state(instance)

    @property
    def state(self) -> BombState:
        """The current snapshot."""
        return self._history[-1]

    @property
    def history(self) -> tuple[BombState, ...]:
        """Every snapshot, oldest first."""
        return tuple(self._history)

    def _push(self, state: BombState) -> None:
        self._history.append(state)

    def undo(self) -> bool:
        """Revert the last change. Returns whether there was one to revert."""
        if len(self._history) == 1:
            return False
        self._history.pop()
        return True

    def missing_facts(self) -> list[Fact[Any]]:
        """Facts no one has provided yet, in the order the manual defines them.

        Not every missing fact will be needed; solvers ask only for those
        their rules use. This helps a frontend gather the usual edgework up
        front to save round trips.
        """
        return [
            fact
            for key, fact in self.manual.facts.items()
            if key not in self.state.facts
        ]

    # Facts

    def set_fact(self, key: str, value: Any) -> None:  # noqa: ANN401 - user input
        """Record a fact, validating it.

        Raises:
            UnknownFactError: No loaded pack defines `key`.
            pydantic.ValidationError: The value is invalid.
        """
        self.set_facts(**{key: value})

    def set_facts(self, **values: Any) -> None:  # noqa: ANN401 - user input
        """Record several facts at once (atomically: all valid, or none set).

        Raises:
            UnknownFactError: No loaded pack defines one of the keys.
            pydantic.ValidationError: A value is invalid.
        """
        validated = {
            key: self.manual.fact(key).to_json(value) for key, value in values.items()
        }
        facts = {**self.state.facts, **validated}
        self._push(self.state.model_copy(update={"facts": facts}))

    def forget_fact(self, key: str) -> None:
        """Remove a recorded fact (e.g. it was misread)."""
        facts = {k: v for k, v in self.state.facts.items() if k != key}
        self._push(self.state.model_copy(update={"facts": facts}))

    # Modules

    def module_of(self, instance_id: str) -> AnyModule:
        """The solver for an instance."""
        return self.manual.module(self.state.instance(instance_id).module)

    def _load_state(self, instance: Instance) -> Frozen:
        module = self.manual.module(instance.module)
        state: Frozen = module.state_type.model_validate(instance.state)
        return state

    def add_module(self, query: str, instance_id: str | None = None) -> str:
        """Add a module to the bomb and return its instance ID.

        Args:
            query: Module ID or name, e.g. ``"Simon"`` or ``"simon says"``.
            instance_id: Explicit ID. Defaults to ``"<ModuleID>#<n>"``.

        Raises:
            UnknownModuleError: No loaded module matches `query`.
            ConflictError: `instance_id` is already taken.
        """
        module = self.manual.module(query)
        taken = {instance.id for instance in self.state.instances}
        if instance_id is None:
            n = 1
            while f"{module.id}#{n}" in taken:
                n += 1
            instance_id = f"{module.id}#{n}"
        elif instance_id in taken:
            msg = f"instance ID {instance_id!r} is already taken"
            raise ConflictError(msg)
        instance = Instance(
            id=instance_id,
            module=module.id,
            state=module.initial_state().model_dump(mode="json"),
        )
        self._push(
            self.state.model_copy(
                update={"instances": (*self.state.instances, instance)}
            )
        )
        return instance_id

    def remove_module(self, instance_id: str) -> None:
        """Remove a module instance (e.g. it was added by mistake)."""
        self.state.instance(instance_id)  # Raise if unknown.
        instances = tuple(i for i in self.state.instances if i.id != instance_id)
        self._push(self.state.model_copy(update={"instances": instances}))

    def solve(self, instance_id: str, data: Mapping[str, Any] | BaseModel) -> Answer:
        """Feed an input to a module and return the expert's answer.

        Nothing changes if this raises, so it is safe to retry after
        providing missing facts.

        Raises:
            UnknownInstanceError: There is no such instance.
            ModuleStateError: The module is solved or can't take this input.
            NeedsInfo: A fact must be provided first.
            pydantic.ValidationError: `data` doesn't fit the module's input.
        """
        instance = self.state.instance(instance_id)
        if instance.solved:
            msg = f"{instance_id} is already solved"
            raise ModuleStateError(msg)
        module = self.manual.module(instance.module)
        parsed = module.input_type.model_validate(data)
        answer, new_state = module.step(
            parsed, self._load_state(instance), self.state.context
        )
        updated = instance.model_copy(
            update={"state": new_state.model_dump(mode="json")}
        )
        self._push(self.state.replace_instance(updated))
        result: Answer = answer
        return result

    # Bomb events

    def _dispatch(self, state: BombState, event: Event) -> BombState:
        instances: list[Instance] = []
        for instance in state.instances:
            module = self.manual.module(instance.module)
            new_state = module.on_event(
                event, self._load_state(instance), instance=instance.id
            )
            instances.append(
                instance.model_copy(update={"state": new_state.model_dump(mode="json")})
            )
        return state.model_copy(update={"instances": tuple(instances)})

    def strike(self, instance_id: str | None = None) -> None:
        """Record a strike, optionally on the module that caused it.

        Raises:
            UnknownInstanceError: `instance_id` is given but unknown.
        """
        if instance_id is not None:
            self.state.instance(instance_id)
        state = self.state.model_copy(update={"strikes": self.state.strikes + 1})
        self._push(self._dispatch(state, Strike(instance=instance_id)))

    def mark_solved(self, instance_id: str) -> None:
        """Record that a module was disarmed.

        Raises:
            UnknownInstanceError: There is no such instance.
            ModuleStateError: It was already solved.
        """
        instance = self.state.instance(instance_id)
        if instance.solved:
            msg = f"{instance_id} is already solved"
            raise ModuleStateError(msg)
        state = self.state.replace_instance(
            instance.model_copy(update={"solved": True})
        ).model_copy(update={"solve_order": (*self.state.solve_order, instance.module)})
        event = ModuleSolved(instance=instance_id, module=instance.module)
        self._push(self._dispatch(state, event))

    # Persistence

    def dump(self) -> SavedSession:
        """Snapshot the whole session, history included."""
        return SavedSession(ruleset=self.manual.ruleset, history=self.history)

    def to_json(self) -> str:
        """Serialize the whole session, history included."""
        return self.dump().model_dump_json()

    @classmethod
    def restore(
        cls, saved: SavedSession, *, available: tuple[Pack, ...] | None = None
    ) -> Self:
        """Rebuild a session, resolving its ruleset against installed packs.

        Raises:
            UnknownPackError: A pack it was played with is not installed.
            pydantic.ValidationError: A module state no longer validates.
        """
        return cls(Manual.load(saved.ruleset, available=available), saved.history)

    @classmethod
    def from_json(
        cls, data: str | bytes, *, available: tuple[Pack, ...] | None = None
    ) -> Self:
        """Load a session saved with `to_json`."""
        return cls.restore(SavedSession.model_validate_json(data), available=available)

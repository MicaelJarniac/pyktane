"""A bomb being defused, kept as a log of actions.

Everything that happens is an action (`pyktane.actions`): facts recorded,
modules added, reports solved, strikes, solves. The session keeps that log
and the `BombState` after each action. Solvers are pure, so replaying the log
always gives the same result, which makes corrections exact:

- **Correcting a report** (`correct`): "6 wires... wait, 5" replaces the
  module's latest report and re-solves it, without advancing stateful
  modules like Memory.
- **Correcting a fact** (`set_facts` on a recorded key) rewrites it where it
  was first recorded, since edgework never changes mid-game.
- **Editing the history** (`replace_action`, `remove_action`,
  `insert_action`): "that wasn't a strike" removes just that action.

After a correction the log is replayed. Answers given since then that came
out differently are reported in `Revision.changed`, because the defuser
already acted on them. Edits that would make a later action impossible are
rejected with `RevisionError`, changing nothing. Every change, corrections
included, can be reverted with `undo`.

Module states are stored as JSON and re-validated by their module on use,
which keeps `BombState` independent of the installed packs.
"""

__all__: tuple[str, ...] = (
    "FORMAT_VERSION",
    "BombState",
    "ChangedAnswer",
    "HistoryEntry",
    "Instance",
    "Revision",
    "SavedSession",
    "Session",
)

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from pyktane.actions import (
    Action,
    AddModule,
    AddStrike,
    ForgetFact,
    MarkSolved,
    RemoveModule,
    SetFacts,
    Solve,
    Splice,
)
from pyktane.base import Answer, Frozen
from pyktane.context import Context
from pyktane.edgework import Count
from pyktane.errors import (
    ConflictError,
    ModuleStateError,
    PyktaneError,
    RevisionError,
    UnknownActionError,
    UnknownFactError,
    UnknownInstanceError,
    UnknownModuleError,
)
from pyktane.events import Event, ModuleSolved, Strike
from pyktane.packs import Manual, Pack, Ruleset
lazy from pyktane.facts import Fact
lazy from pyktane.module import AnyModule

FORMAT_VERSION: Final = 2

_ACTION: Final = TypeAdapter[Action](Action)


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
        solve_order: IDs of solved instances, oldest first.
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
        solved = tuple(self.instance(i).module for i in self.solve_order)
        return Context(facts=self.facts, strikes=self.strikes, solved=solved)


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One action in a session's history.

    Attributes:
        index: Its position, for `replace_action` and friends.
        action: What happened.
        answer: What the expert answered, for `Solve` actions.
    """

    index: int
    action: Action
    answer: Answer | None

    def describe(self) -> str:
        """One line for people (or an AI) to pick the action to edit.

        Example:
            ``"3: strike on Simon#1"`` or
            ``"4: Simon#1 reported {...} -> Press blue."``
        """
        line = f"{self.index}: {self.action.describe()}"
        return line if self.answer is None else f"{line} -> {self.answer.instruction}"


@dataclass(frozen=True, slots=True)
class ChangedAnswer:
    """An answer that came out differently after a correction.

    The defuser may already have acted on `before`, so tell them.

    Attributes:
        index: The `Solve` action's position in the corrected history.
        instance: The module instance it was for.
        before: The answer given at the time.
        after: The answer under the corrected history.
    """

    index: int
    instance: str
    before: Answer
    after: Answer


@dataclass(frozen=True, slots=True, repr=False)
class Revision:
    """The outcome of a change to the session.

    Attributes:
        answers: For each action the change put in the history, its answer
            (`None` for actions that aren't reports).
        changed: Earlier answers that came out differently. Always empty
            when just playing on; filled after corrections.
    """

    answers: tuple[Answer | None, ...] = ()
    changed: tuple[ChangedAnswer, ...] = ()

    @property
    def answer(self) -> Answer | None:
        """The answer to the report this change made, if it made one."""
        return next((answer for answer in self.answers if answer is not None), None)

    def __repr__(self) -> str:
        """Compact, so it doesn't swamp a REPL after every action.

        Example:
            >>> Revision()
            <Revision: 0 answers, 0 changed>
        """
        answers = sum(answer is not None for answer in self.answers)
        return f"<Revision: {answers} answers, {len(self.changed)} changed>"


class SavedSession(Frozen):
    """On-disk format of a session.

    Attributes:
        format_version: Bumped on incompatible changes to this format.
        ruleset: The pinned packs the session was played with.
        actions: The history; replaying it rebuilds the bomb.
        undo: Edits that `undo` reverts, oldest first.
    """

    format_version: Literal[2] = FORMAT_VERSION
    ruleset: Ruleset
    actions: tuple[Action, ...] = ()
    undo: tuple[tuple[Splice, ...], ...] = ()


class Session:
    """A bomb being defused, with corrections and undo.

    Example:
        >>> from pyktane.vanilla import PACK
        >>> bomb = Session(Manual([PACK]))
        >>> bomb.set_facts(serial="AB3CD5")
        <Revision: 0 answers, 0 changed>
        >>> wires = bomb.add_module("wires")
        >>> bomb.solve(wires, {"wires": ["red"] * 6}).instruction
        'Cut the 3rd wire (red).'

        "Wait, there are only 5":

        >>> bomb.correct(wires, {"wires": ["red"] * 5}).answer.instruction
        'Cut the 2nd wire (red).'
    """

    def __init__(
        self,
        manual: Manual | None = None,
        actions: Iterable[Action] = (),
        undo: Iterable[Sequence[Splice]] = (),
    ) -> None:
        """Start a session, optionally replaying a saved history.

        Args:
            manual: The rules in play. Defaults to every installed pack.
            actions: History to replay.
            undo: Edits that `undo` can revert, oldest first.

        Raises:
            PyktaneError: An action in `actions` is no longer valid.
            pydantic.ValidationError: Its data no longer validates.
        """
        self.manual: Final = Manual.load() if manual is None else manual
        self._actions: list[Action] = []
        self._states: list[BombState] = [BombState()]
        self._answers: list[Answer | None] = []
        self._undo: list[tuple[Splice, ...]] = []
        if replay := tuple(actions):
            self._apply_splice(Splice(index=0, inserted=replay))
        self._undo = [tuple(change) for change in undo]

    # Reading

    @property
    def state(self) -> BombState:
        """The bomb as it is now."""
        return self._states[-1]

    @property
    def actions(self) -> tuple[Action, ...]:
        """Everything that happened, oldest first."""
        return tuple(self._actions)

    @property
    def history(self) -> tuple[HistoryEntry, ...]:
        """Every action with its position and answer, oldest first."""
        return tuple(
            HistoryEntry(index=index, action=action, answer=answer)
            for index, (action, answer) in enumerate(
                zip(self._actions, self._answers, strict=True)
            )
        )

    @property
    def can_undo(self) -> bool:
        """Whether `undo` has anything to revert."""
        return bool(self._undo)

    @property
    def last_change(self) -> str:
        """What `undo` would revert, in words; empty if nothing.

        Example:
            ``"add Simon as Simon#1; Simon#1 solved"``.
        """
        if not self._undo:
            return ""
        return "; ".join(_describe_splice(splice) for splice in self._undo[-1])

    def missing_facts(self) -> list[Fact[Any]]:
        """Facts no one has provided yet, in the order the manual defines them.

        Not every missing fact will be needed; solvers ask only for those
        their rules use. This helps a frontend gather the usual edgework up
        front to save round trips. Derived facts (like `has_parallel_port`)
        aren't listed: they're quick questions asked only when needed.
        """
        context = self.state.context
        return [
            fact
            for fact in self.manual.facts.values()
            if fact.derived_from is None and not context.has(fact)
        ]

    def module_of(self, instance_id: str) -> AnyModule:
        """The solver for an instance."""
        return self.manual.module(self.state.instance(instance_id).module)

    # Playing on

    def set_fact(self, key: str, value: Any) -> Revision:  # noqa: ANN401 - user input
        """Record or correct one fact. See `set_facts`."""
        return self.set_facts(**{key: value})

    def set_facts(self, **values: Any) -> Revision:  # noqa: ANN401 - user input
        """Record facts, or correct ones already recorded.

        Facts describe the bomb, which doesn't change during a game, so a new
        value for a recorded fact is a correction: it's rewritten where it was
        first recorded, and answers given since are re-checked (see
        `Revision.changed`). All values are validated first; if any is
        invalid, nothing is recorded.

        Raises:
            UnknownFactError: No loaded pack defines one of the keys.
            pydantic.ValidationError: A value is invalid.
        """
        validated = {
            key: self.manual.fact(key).to_json(value) for key, value in values.items()
        }
        new = {k: v for k, v in validated.items() if k not in self.state.facts}
        fixes = {
            key: value
            for key, value in validated.items()
            if key in self.state.facts and self.state.facts[key] != value
        }
        splices = [self._fact_fix(key, value) for key, value in fixes.items()]
        if new:
            splices.append(self._append_splice(SetFacts(facts=new)))
        return self._change(splices)

    def forget_fact(self, key: str) -> Revision:
        """Remove a recorded fact, e.g. one that shouldn't have been recorded.

        Raises:
            UnknownFactError: The fact isn't recorded.
        """
        return self._change([self._append_splice(ForgetFact(key=key))])

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
        if instance_id is None:
            instance_id = self._next_instance_id(module.id)
        action = AddModule(instance=instance_id, module=module.id)
        self._change([self._append_splice(action)])
        return instance_id

    def remove_module(self, instance_id: str) -> Revision:
        """Remove a module from the bomb, e.g. one added by mistake.

        Its earlier actions stay in the history; to erase them instead,
        remove the `AddModule` action with `remove_action`.

        Raises:
            UnknownInstanceError: There is no such instance.
        """
        return self._change([self._append_splice(RemoveModule(instance=instance_id))])

    def solve(self, instance_id: str, data: Mapping[str, Any] | BaseModel) -> Answer:
        """Report what a module shows and get the expert's answer.

        For a misreport, use `correct` instead: calling `solve` again would
        count as the module's next step (e.g. the next Memory stage).

        Nothing changes if this raises, so it is safe to retry after
        providing missing facts.

        Raises:
            UnknownInstanceError: There is no such instance.
            ModuleStateError: The module is solved or can't take this input.
            NeedsInfo: A fact must be provided first.
            pydantic.ValidationError: `data` doesn't fit the module's input.
        """
        action = Solve(instance=instance_id, data=_as_json(data))
        answer = self._change([self._append_splice(action)]).answer
        assert answer is not None  # noqa: S101 - a solve always answers
        return answer

    def strike(self, instance_id: str | None = None) -> Revision:
        """Record a strike, optionally on the module that caused it.

        Raises:
            UnknownInstanceError: `instance_id` is given but unknown.
        """
        return self._change([self._append_splice(AddStrike(instance=instance_id))])

    def mark_solved(self, target: str) -> Revision:
        """Record that a module was disarmed, by the expert's answers or not.

        A defuser who solves a module on their own just says so: nothing has
        to be reported about it first, and it doesn't even have to have been
        added. `target` is an instance ID, or a module ID or name:

        - with an instance ID, that instance is marked solved;
        - with a module, its one unsolved instance is marked solved, or, if
          it has none (bombs can carry several of a module, and a defuser
          solving one alone may not have mentioned it), a new one is added
          and marked solved, as two actions in one change, so one `undo`
          reverts both.

        Raises:
            UnknownModuleError: `target` is neither an instance nor a module.
            ConflictError: The module has several unsolved instances, so it's
                unclear which one was meant; pass an instance ID.
            ModuleStateError: It's already solved, or it's a needy module
                (those can't be disarmed).
        """
        if any(instance.id == target for instance in self.state.instances):
            return self._change([self._append_splice(MarkSolved(instance=target))])
        try:
            module = self.manual.module(target)
        except UnknownModuleError:
            known = ", ".join(i.id for i in self.state.instances) or "none"
            msg = (
                f"no module instance {target!r} (known: {known}), "
                "and no module by that name"
            )
            raise UnknownInstanceError(msg) from None
        if module.needy:
            raise _needy_error(module)
        unsolved = [
            instance.id
            for instance in self.state.instances
            if instance.module == module.id and not instance.solved
        ]
        if len(unsolved) > 1:
            msg = (
                f"the bomb has several unsolved {module.name} modules "
                f"({', '.join(unsolved)}); say which one"
            )
            raise ConflictError(msg)
        if unsolved:
            return self._change([self._append_splice(MarkSolved(instance=unsolved[0]))])
        instance_id = self._next_instance_id(module.id)
        added = AddModule(instance=instance_id, module=module.id)
        solved = MarkSolved(instance=instance_id)
        return self._change(
            [Splice(index=len(self._actions), inserted=(added, solved))]
        )

    # Correcting

    def correct(
        self, instance_id: str, data: Mapping[str, Any] | BaseModel
    ) -> Revision:
        """Replace a module's latest report, e.g. "6 wires... wait, 5".

        The module is re-solved as if the corrected report had been given in
        the first place: Memory stays on the same stage, and everything after
        it is replayed. `Revision.answer` is the corrected answer.

        Raises:
            ModuleStateError: Nothing was reported for the module yet.
            RevisionError: A later action wouldn't work with the correction.
            NeedsInfo: The corrected report needs a fact first.
            pydantic.ValidationError: `data` doesn't fit the module's input.
        """
        self.state.instance(instance_id)  # Raise if unknown.
        index = next(
            (
                index
                for index in reversed(range(len(self._actions)))
                if isinstance(action := self._actions[index], Solve)
                and action.instance == instance_id
            ),
            None,
        )
        if index is None:
            msg = f"nothing was reported for {instance_id} yet; use solve"
            raise ModuleStateError(msg)
        return self.replace_action(
            index, Solve(instance=instance_id, data=_as_json(data))
        )

    def replace_action(
        self, index: int, action: Action | Mapping[str, Any]
    ) -> Revision:
        """Replace the action at `index` and replay what followed it.

        Raises:
            UnknownActionError: There's no action at `index`.
            RevisionError: A later action wouldn't work after the edit.
            PyktaneError: The new action itself is invalid there.
            pydantic.ValidationError: `action` isn't a valid action.
        """
        old = self._action_at(index)
        splice = Splice(
            index=index, removed=(old,), inserted=(_ACTION.validate_python(action),)
        )
        return self._change([splice])

    def remove_action(self, index: int) -> Revision:
        """Remove the action at `index`, e.g. a strike that wasn't one.

        Raises:
            UnknownActionError: There's no action at `index`.
            RevisionError: A later action depends on it (e.g. reports on a
                module whose `AddModule` would be removed).
        """
        old = self._action_at(index)
        return self._change([Splice(index=index, removed=(old,))])

    def insert_action(self, index: int, action: Action | Mapping[str, Any]) -> Revision:
        """Insert an action before `index`, e.g. a strike that went unreported.

        `index` may equal the history's length, which appends.

        Raises:
            UnknownActionError: `index` is out of range.
            RevisionError: A later action wouldn't work after the edit.
            PyktaneError: The new action itself is invalid there.
            pydantic.ValidationError: `action` isn't a valid action.
        """
        if not 0 <= index <= len(self._actions):
            msg = (
                f"can't insert at {index}: the history has {len(self._actions)} actions"
            )
            raise UnknownActionError(msg)
        inserted = (_ACTION.validate_python(action),)
        return self._change([Splice(index=index, inserted=inserted)])

    def undo(self) -> bool:
        """Revert the last change, corrections included.

        Returns:
            Whether there was a change to revert.
        """
        if not self._undo:
            return False
        for splice in reversed(self._undo.pop()):
            self._apply_splice(splice.inverse())
        return True

    # Persistence

    def dump(self) -> SavedSession:
        """Everything needed to rebuild this session, undo included."""
        return SavedSession(
            ruleset=self.manual.ruleset,
            actions=self.actions,
            undo=tuple(self._undo),
        )

    def to_json(self) -> str:
        """Serialize the whole session, undo included."""
        return self.dump().model_dump_json()

    @classmethod
    def restore(
        cls, saved: SavedSession, *, available: tuple[Pack, ...] | None = None
    ) -> Self:
        """Rebuild a session by replaying it against the installed packs.

        Raises:
            UnknownPackError: A pack it was played with is not installed.
            PyktaneError: An action is no longer valid with these packs.
        """
        manual = Manual.load(saved.ruleset, available=available)
        return cls(manual, saved.actions, saved.undo)

    @classmethod
    def from_json(
        cls, data: str | bytes, *, available: tuple[Pack, ...] | None = None
    ) -> Self:
        """Load a session saved with `to_json`."""
        return cls.restore(SavedSession.model_validate_json(data), available=available)

    # Internals

    def _next_instance_id(self, module_id: str) -> str:
        taken = {instance.id for instance in self.state.instances}
        n = 1
        while f"{module_id}#{n}" in taken:
            n += 1
        return f"{module_id}#{n}"

    def _action_at(self, index: int) -> Action:
        if not 0 <= index < len(self._actions):
            msg = f"no action at {index}: the history has {len(self._actions)} actions"
            raise UnknownActionError(msg)
        return self._actions[index]

    def _append_splice(self, action: Action) -> Splice:
        return Splice(index=len(self._actions), inserted=(action,))

    def _fact_fix(self, key: str, value: JsonValue) -> Splice:
        """Rewrite the action that recorded `key` (it's currently recorded)."""
        index = next(
            index
            for index in reversed(range(len(self._actions)))
            if isinstance(action := self._actions[index], SetFacts)
            and key in action.facts
        )
        old = self._actions[index]
        assert isinstance(old, SetFacts)  # noqa: S101 - just matched above
        fixed = SetFacts(facts={**old.facts, key: value})
        return Splice(index=index, removed=(old,), inserted=(fixed,))

    def _change(self, splices: Sequence[Splice]) -> Revision:
        """Apply `splices` as one undoable change, all or nothing."""
        saved = (self._actions, self._states, self._answers)
        answers: list[Answer | None] = []
        changed: dict[int, ChangedAnswer] = {}
        applied: list[Splice] = []
        try:
            for splice in splices:
                done, revision = self._apply_splice(splice)
                applied.append(done)
                answers.extend(revision.answers)
                for change in revision.changed:
                    first = changed.get(change.index, change)
                    changed[change.index] = ChangedAnswer(
                        index=change.index,
                        instance=change.instance,
                        before=first.before,
                        after=change.after,
                    )
        except BaseException:
            self._actions, self._states, self._answers = saved
            raise
        if applied:
            self._undo.append(tuple(applied))
        return Revision(
            answers=tuple(answers),
            changed=tuple(c for c in changed.values() if c.before != c.after),
        )

    def _apply_splice(self, splice: Splice) -> tuple[Splice, Revision]:
        """Edit the log and replay it from the edit; nothing changes on error.

        Errors from the inserted actions propagate as they are, so callers
        see e.g. `NeedsInfo`; errors from later actions become
        `RevisionError`.
        """
        actions = list(self._actions)
        splice.apply(actions)
        start, end = splice.index, splice.index + len(splice.inserted)
        canonical = actions[:start]
        states = self._states[: start + 1]
        answers = self._answers[:start]
        for index in range(start, len(actions)):
            try:
                action, state, answer = self._apply(states[-1], actions[index])
            except (PyktaneError, ValidationError) as error:
                if index < end:
                    raise
                # Report positions in the history as it was before the edit.
                original = index - len(splice.inserted) + len(splice.removed)
                raise RevisionError(original, actions[index], error) from error
            canonical.append(action)
            states.append(state)
            answers.append(answer)

        # Answers after the edit, compared with what they were. Indexes are
        # in the new history, which is what callers will see.
        shift = len(splice.inserted) - len(splice.removed)
        changed = tuple(
            ChangedAnswer(index=index, instance=action.instance, before=old, after=new)
            for index in range(end, len(canonical))
            if isinstance(action := canonical[index], Solve)
            and (old := self._answers[index - shift]) is not None
            and (new := answers[index]) is not None
            and old != new
        )
        done = splice.model_copy(update={"inserted": tuple(canonical[start:end])})
        self._actions, self._states, self._answers = canonical, states, answers
        return done, Revision(answers=tuple(answers[start:end]), changed=changed)

    def _load_state(self, instance: Instance) -> Frozen:
        module = self.manual.module(instance.module)
        state: Frozen = module.state_type.model_validate(instance.state)
        return state

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

    def _apply(  # noqa: PLR0911 - one branch per kind of action
        self, state: BombState, action: Action
    ) -> tuple[Action, BombState, Answer | None]:
        """Apply one action: its canonical form, the next state, the answer."""
        if isinstance(action, SetFacts):
            facts = {
                key: self.manual.fact(key).to_json(value)
                for key, value in action.facts.items()
            }
            update = {"facts": {**state.facts, **facts}}
            return SetFacts(facts=facts), state.model_copy(update=update), None
        if isinstance(action, ForgetFact):
            if action.key not in state.facts:
                msg = f"fact {action.key!r} isn't recorded"
                raise UnknownFactError(msg)
            facts = {k: v for k, v in state.facts.items() if k != action.key}
            return action, state.model_copy(update={"facts": facts}), None
        if isinstance(action, AddModule):
            return self._add_module(state, action)
        if isinstance(action, RemoveModule):
            state.instance(action.instance)  # Raise if unknown.
            removed = state.model_copy(
                update={
                    "instances": tuple(
                        i for i in state.instances if i.id != action.instance
                    ),
                    "solve_order": tuple(
                        i for i in state.solve_order if i != action.instance
                    ),
                }
            )
            return action, removed, None
        if isinstance(action, Solve):
            return self._solve(state, action)
        if isinstance(action, AddStrike):
            if action.instance is not None:
                state.instance(action.instance)  # Raise if unknown.
            struck = state.model_copy(update={"strikes": state.strikes + 1})
            return (
                action,
                self._dispatch(struck, Strike(instance=action.instance)),
                None,
            )
        return action, self._mark_solved(state, action), None

    def _add_module(
        self, state: BombState, action: AddModule
    ) -> tuple[Action, BombState, None]:
        module = self.manual.module(action.module)
        if any(instance.id == action.instance for instance in state.instances):
            msg = f"instance ID {action.instance!r} is already taken"
            raise ConflictError(msg)
        instance = Instance(
            id=action.instance,
            module=module.id,
            state=module.initial_state().model_dump(mode="json"),
        )
        update = {"instances": (*state.instances, instance)}
        canonical = AddModule(instance=action.instance, module=module.id)
        return canonical, state.model_copy(update=update), None

    def _solve(
        self, state: BombState, action: Solve
    ) -> tuple[Action, BombState, Answer]:
        instance = state.instance(action.instance)
        if instance.solved:
            msg = f"{action.instance} is already solved"
            raise ModuleStateError(msg)
        module = self.manual.module(instance.module)
        parsed = module.input_type.model_validate(action.data)
        answer, new_state = module.step(
            parsed, self._load_state(instance), state.context
        )
        updated = instance.model_copy(
            update={"state": new_state.model_dump(mode="json")}
        )
        canonical = Solve(instance=action.instance, data=_as_json(parsed))
        result: Answer = answer
        return canonical, state.replace_instance(updated), result

    def _mark_solved(self, state: BombState, action: MarkSolved) -> BombState:
        instance = state.instance(action.instance)
        module = self.manual.module(instance.module)
        if module.needy:
            raise _needy_error(module)
        if instance.solved:
            msg = f"{action.instance} is already solved"
            raise ModuleStateError(msg)
        solved = state.replace_instance(
            instance.model_copy(update={"solved": True})
        ).model_copy(update={"solve_order": (*state.solve_order, instance.id)})
        event = ModuleSolved(instance=instance.id, module=instance.module)
        return self._dispatch(solved, event)


def _describe_splice(splice: Splice) -> str:
    """A splice in words: what it added, removed or replaced."""
    added = ", ".join(action.describe() for action in splice.inserted)
    removed = ", ".join(action.describe() for action in splice.removed)
    if added and removed:
        return f"{removed} -> {added}"
    return added or f"removed {removed}"


def _needy_error(module: AnyModule) -> ModuleStateError:
    return ModuleStateError(
        f"{module.name} is a needy module: it can't be disarmed, only tended "
        "each time it activates, so it's never marked solved"
    )


def _as_json(data: Mapping[str, Any] | BaseModel) -> JsonValue:
    """A report as plain JSON, however it was given."""
    if isinstance(data, BaseModel):
        dumped: JsonValue = data.model_dump(mode="json")
        return dumped
    return TypeAdapter[JsonValue](JsonValue).validate_python(dict(data))

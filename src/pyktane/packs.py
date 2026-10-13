"""Module packs, rulesets and plugin discovery.

A `Pack` is a versioned collection of modules (and any extra facts they
need). Packs are discovered through the ``pyktane.packs`` entry point group;
vanilla registers itself there exactly like a third-party pack would::

    [project.entry-points."pyktane.packs"]
    mypack = "mypack:PACK"

A `Ruleset` says which packs are in play. It only stores references, so it
can be saved; `Manual` resolves it into actual modules and facts.

Different manual versions are just different pack versions: a distribution
can register ``vanilla`` version ``1`` and ``2`` side by side, and a ruleset
picks one.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, Final, Self

from pyktane.base import Frozen, normalize
from pyktane.edgework import EDGEWORK_FACTS
from pyktane.errors import (
    ConflictError,
    UnknownFactError,
    UnknownModuleError,
    UnknownPackError,
)
lazy from pyktane.facts import Fact
lazy from pyktane.module import AnyModule

ENTRY_POINT_GROUP: Final = "pyktane.packs"


@dataclass(frozen=True)
class Pack:
    """A versioned collection of module solvers.

    Attributes:
        id: Unique pack identifier, e.g. ``"vanilla"``.
        version: Rules version. Bump it when the rules change, not when the
            code is refactored: saved sessions pin it.
        name: Human-readable name.
        modules: The solvers it provides.
        facts: Extra facts its modules read, beyond the core edgework.
    """

    id: str
    version: str
    name: str
    modules: tuple[AnyModule, ...]
    facts: tuple[Fact[Any], ...] = ()

    def __post_init__(self) -> None:
        """Reject packs that define the same module twice."""
        seen: set[str] = set()
        for module in self.modules:
            if module.id in seen:
                msg = f"pack {self.id!r} defines module {module.id!r} twice"
                raise ConflictError(msg)
            seen.add(module.id)

    @property
    def ref(self) -> PackRef:
        """A pinned reference to this pack."""
        return PackRef(id=self.id, version=self.version)


class PackRef(Frozen):
    """Reference to a pack.

    Attributes:
        id: The pack ID.
        version: The version, or `None` for "the only installed version".
    """

    id: str
    version: str | None = None

    def __str__(self) -> str:
        """``id@version``, or just ``id`` when unpinned."""
        return self.id if self.version is None else f"{self.id}@{self.version}"


class Ruleset(Frozen):
    """Which packs are in play, and which wins when they overlap.

    Attributes:
        packs: The packs to load.
        overrides: Module ID -> pack ID that provides it, for module IDs that
            more than one of the packs define.
    """

    packs: tuple[PackRef, ...]
    overrides: Mapping[str, str] = {}


def installed_packs() -> tuple[Pack, ...]:
    """Load every pack registered under the ``pyktane.packs`` entry point group.

    Raises:
        TypeError: An entry point doesn't point to a `Pack`.
    """
    packs: list[Pack] = []
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        pack = entry_point.load()
        if not isinstance(pack, Pack):
            msg = f"entry point {entry_point.name!r} is not a Pack: {pack!r}"
            raise TypeError(msg)
        packs.append(pack)
    return tuple(packs)


def _resolve(ref: PackRef, available: Iterable[Pack]) -> Pack:
    candidates = [
        pack
        for pack in available
        if pack.id == ref.id and ref.version in {None, pack.version}
    ]
    if not candidates:
        msg = f"pack {ref} is not installed"
        raise UnknownPackError(msg)
    if len(candidates) > 1:
        versions = ", ".join(sorted(pack.version for pack in candidates))
        msg = f"pack {ref.id!r} has several versions installed ({versions}); pin one"
        raise ConflictError(msg)
    return candidates[0]


class Manual:
    """A resolved ruleset: the modules and facts actually in play.

    Core edgework facts are always available, whatever the packs.
    """

    def __init__(
        self, packs: Iterable[Pack], overrides: Mapping[str, str] | None = None
    ) -> None:
        """Combine `packs`, using `overrides` to settle duplicate module IDs.

        Raises:
            ConflictError: Two packs share an ID, a module ID or a fact key
                without an override settling it.
            UnknownPackError: An override names a pack that is not loaded or
                doesn't define that module.
        """
        self.packs: Final = tuple(packs)
        self.overrides: Final = dict(overrides or {})

        pack_ids = [pack.id for pack in self.packs]
        if len(set(pack_ids)) != len(pack_ids):
            msg = f"a pack is loaded more than once: {pack_ids}"
            raise ConflictError(msg)

        self.facts: Final = self._collect_facts()
        self.modules: Final = self._collect_modules()

    def _collect_facts(self) -> dict[str, Fact[Any]]:
        facts: dict[str, Fact[Any]] = {fact.key: fact for fact in EDGEWORK_FACTS}
        for pack in self.packs:
            for fact in pack.facts:
                if facts.setdefault(fact.key, fact) is not fact:
                    msg = f"fact {fact.key!r} from pack {pack.id!r} is already defined"
                    raise ConflictError(msg)
        return facts

    def _collect_modules(self) -> dict[str, AnyModule]:
        providers: dict[str, list[tuple[Pack, AnyModule]]] = {}
        for pack in self.packs:
            for module in pack.modules:
                providers.setdefault(module.id, []).append((pack, module))

        modules: dict[str, AnyModule] = {}
        for module_id, options in providers.items():
            if module_id in self.overrides:
                winner = self.overrides[module_id]
                matches = [module for pack, module in options if pack.id == winner]
                if not matches:
                    msg = f"override for {module_id!r}: {winner!r} doesn't provide it"
                    raise UnknownPackError(msg)
                modules[module_id] = matches[0]
            elif len(options) > 1:
                names = ", ".join(pack.id for pack, _ in options)
                msg = f"module {module_id!r} is defined by {names}; add an override"
                raise ConflictError(msg)
            else:
                modules[module_id] = options[0][1]

        for module_id in self.overrides.keys() - providers.keys():
            msg = f"override for {module_id!r}, but no loaded pack defines it"
            raise UnknownModuleError(msg)
        return modules

    @classmethod
    def load(
        cls, ruleset: Ruleset | None = None, *, available: Iterable[Pack] | None = None
    ) -> Self:
        """Build the manual for `ruleset` from the installed packs.

        Args:
            ruleset: Packs to use. Defaults to every installed pack.
            available: Packs to choose from, instead of the installed ones.
        """
        pool = installed_packs() if available is None else tuple(available)
        if ruleset is None:
            ids = dict.fromkeys(pack.id for pack in pool)
            ruleset = Ruleset(packs=tuple(PackRef(id=pack_id) for pack_id in ids))
        return cls(
            (_resolve(ref, pool) for ref in ruleset.packs),
            ruleset.overrides,
        )

    @property
    def ruleset(self) -> Ruleset:
        """The pinned ruleset this manual was built from, suitable for saving."""
        return Ruleset(
            packs=tuple(pack.ref for pack in self.packs), overrides=self.overrides
        )

    def module(self, query: str) -> AnyModule:
        """Find a module by ID or name, ignoring case and punctuation.

        Example:
            ``manual.module("simon says")`` and ``manual.module("Simon")``
            return the same solver.

        Raises:
            UnknownModuleError: Nothing matches.
        """
        if query in self.modules:
            return self.modules[query]
        key = normalize(query)
        for module in self.modules.values():
            if key in {normalize(module.id), normalize(module.name)}:
                return module
        msg = f"no module matches {query!r}"
        raise UnknownModuleError(msg)

    def fact(self, key: str) -> Fact[Any]:
        """Find a fact by key.

        Raises:
            UnknownFactError: No fact has that key.
        """
        try:
            return self.facts[key]
        except KeyError:
            msg = f"no fact has key {key!r}"
            raise UnknownFactError(msg) from None

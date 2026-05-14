"""Module that defines differnt kinds of data models that control the applications behavior."""

import atexit
import contextlib
import json
import types
import typing
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from loguru import logger
from typing_extensions import Self

T = typing.TypeVar("T")
JsonPodType = bool | int | float | str | None
JsonValueType = JsonPodType | list["JsonValueType"] | dict[str, "JsonValueType"]
JsonListType = list[JsonValueType]
JsonDictType = dict[str, JsonValueType]


def convert_union(value: object, hint: type) -> object:
    """Convert a given object using a union type hint specification."""
    args = typing.get_args(hint)
    for arg in args:
        with contextlib.suppress(TypeError, ValueError):
            return convert(value, arg)
    msg = f"Unable to convert {type(value)} to {hint}"
    raise TypeError(msg)


def convert_list_like(value: object, hint: type) -> object:
    """Convert a given list-like object using a list-like type hint specification."""
    if not isinstance(value, list | set | tuple):
        msg = f"Cannot convert '{type(value).__name__}' into '{hint.__name__}'"
        raise TypeError(msg)

    args = typing.get_args(hint)
    values = []
    for item in value:
        for arg in args:
            with contextlib.suppress(TypeError, ValueError):
                values.append(convert(item, arg))
    return hint(values)


def convert(value: object, hint: type) -> object:
    """Convert a given object using a given type hint specification."""
    if hint is types.NoneType:
        if value is None:
            return None
        msg = f"Type hint defines field to be 'None' but value is of type '{type(value).__name__}'"
        raise TypeError(msg)

    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return convert_union(value, hint)

    if origin in (list, set, tuple):
        return convert_list_like(value, hint)

    if isinstance(value, hint):
        return value

    try:
        return hint(value)
    except Exception as exc:
        msg = f"Cannot convert '{type(value).__name__}' into '{hint.__name__}'"
        raise TypeError(msg) from exc


@typing.overload
def serialize(value: dict) -> JsonDictType: ...


@typing.overload
def serialize(value: list) -> JsonListType: ...


@typing.overload
def serialize(value: JsonPodType) -> JsonPodType: ...


@typing.overload
def serialize(value: T) -> str: ...


def serialize(value: object) -> object:
    """Serialize an object into a JSON dumpable object.

    JSON PODs will be left as is, as they are JSON dumpable.
    dicts and list-likes are serialized recursively, where each value is passed
    into this function as well.
    Everything else will be converted into a string using `__str__`.
    """
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list | set | tuple):
        return [serialize(x) for x in value]
    if isinstance(value, str | int | float | None):
        return value
    return str(value)


@dataclass
class AbstractConfigFile:
    """A base dataclass that can be inherited to define a structure for a config file."""

    def to_dict(self) -> JsonDictType:
        """Serialize the dataclass into a JSON-dumpable dict."""
        return serialize(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        """Create an instance by deserializing the given data based on the type hints of the dataclass fields."""
        type_hints = typing.get_type_hints(Registry)

        converted = {}
        for field_definition in fields(cls):
            value = data.get(field_definition.name)
            if value is None and (alias := field_definition.metadata.get("alias")):
                value = data.get(alias)
            converted[field_definition.name] = convert(value, type_hints[field_definition.name])

        return cls(**converted)

    @classmethod
    def from_file(cls, path: Path, *, raise_on_missing: bool = True, save_on_exit: bool = False) -> Self:
        """Create an instance by reading JSON data from a file."""
        if path.is_file():
            logger.debug(f"Loading '{path}' into '{cls.__name__}'.")
            with path.open(mode="r", encoding="utf-8") as fd:
                data = json.load(fd)
            instance = cls.from_dict(data)
        elif not raise_on_missing:
            instance = cls()
        else:
            msg = f"{path} does not exists"
            raise FileNotFoundError(msg)

        if save_on_exit:
            logger.debug(f"Setting up 'save on exit' for '{cls.__name__}'")
            atexit.register(lambda: path.write_text(json.dumps(instance.to_dict(), indent=4)))

        return instance


@dataclass
class Registry(AbstractConfigFile):
    """Data model that defines the registry.

    The registry is used for switching back and forth between worktrees
    and repositories,
    and as storage for repositories.
    """

    last_worktree: Path | None = field(default=None, metadata={"alias": "last-worktree"})
    last_repository: Path | None = field(default=None, metadata={"alias": "last-repository"})
    repositories: set[Path] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Validate the paths to make sure they are not invalid."""
        if self.last_repository is not None and not self.last_repository.is_dir():
            logger.warning("Stored 'last repository' is invalid. Unsetting it.")
            self.last_repository = None

        if self.last_worktree is not None and not self.last_worktree.is_dir():
            logger.warning("Stored 'last worktree' is invalid. Unsetting it.")
            self.last_worktree = None

        self.repositories = {x for x in self.repositories if x.is_dir()}

    @classmethod
    def load(cls, *, path: Path | None = None) -> Self:
        """Load the config from file."""
        path = path or Path.home().joinpath(".config", "twig", "registry.json")
        return super().from_file(path, raise_on_missing=False, save_on_exit=True)

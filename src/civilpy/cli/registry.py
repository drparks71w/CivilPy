#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Command registry: one declaration drives flags, completion, and docs.

Each CLI command is declared as a :class:`CommandSpec` pointing at a
frozen *input dataclass* (the ``HeadwallInput`` pattern: typed fields,
``Literal`` choices, per-field docs).  :func:`introspect` reads that
dataclass once and everything else is generated from it — argparse flags
in :mod:`civilpy.cli.batch`, Tab-completion and bottom-toolbar docs in
:mod:`civilpy.cli.shell`, and ``/help`` text.  Adding a field to an input
model updates the whole CLI.

Input-model conventions (enforced here):

* fields use ``typing.Optional`` / ``typing.Literal`` (no ``X | Y`` —
  these hints are resolved at runtime on Python 3.9);
* per-field metadata: ``doc`` (help text, required), ``positional``
  (True for the main file argument), ``kind="path"`` + ``exts`` for file
  arguments (drives extension-filtered path completion).

Command modules stay import-light: heavy civilpy imports live inside the
runner functions so the CLI starts fast; a runner needing an optional
extra calls :func:`require` for the friendly install hint.
"""

from __future__ import annotations

import dataclasses
import importlib
from dataclasses import dataclass
from typing import Any, Callable, List, Literal, Optional, Tuple, get_args, get_origin, get_type_hints


class CliError(Exception):
    """A user-facing CLI failure; ``exit_code`` becomes the process exit."""

    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


def require(module: str, extra: str):
    """Import an optional dependency or raise the install-hint error."""
    try:
        return importlib.import_module(module)
    except ImportError:
        raise CliError(
            f"this command needs the '{extra}' extra: "
            f"pip install civilpy[{extra}]  (missing module: {module})"
        )


@dataclass(frozen=True)
class ArgInfo:
    """One CLI argument, derived from one input-dataclass field."""

    name: str                      # dataclass field name (snake_case)
    type: type                     # value converter (str/int/float/bool)
    doc: str
    required: bool
    default: Any = None
    choices: Optional[Tuple[Any, ...]] = None
    positional: bool = False
    is_bool: bool = False
    kind: Optional[str] = None     # "path" for file arguments
    exts: Tuple[str, ...] = ()     # completion filter for kind="path"

    @property
    def flag(self) -> str:
        return "--" + self.name.replace("_", "-")

    @property
    def metavar(self) -> str:
        if self.kind == "path":
            return "FILE"
        return self.name.upper()

    def describe(self) -> str:
        """One-line doc for toolbars and /help: text plus type/choices/
        default."""
        parts = [self.doc]
        if self.choices:
            parts.append("choices: " + ", ".join(str(c) for c in self.choices))
        elif self.is_bool:
            parts.append("flag")
        else:
            parts.append(self.type.__name__)
        if not self.required and not self.positional and self.default is not None:
            parts.append(f"default {self.default}")
        return " — ".join([parts[0], "; ".join(parts[1:])])


def introspect(input_model: type) -> List[ArgInfo]:
    """Read an input dataclass into :class:`ArgInfo` records."""
    hints = get_type_hints(input_model)
    infos: List[ArgInfo] = []
    for f in dataclasses.fields(input_model):
        hint = hints[f.name]
        meta = dict(f.metadata)
        doc = meta.get("doc")
        if not doc:
            raise TypeError(
                f"{input_model.__name__}.{f.name}: input-model fields need "
                "metadata={'doc': ...} so the CLI can document them"
            )
        choices: Optional[Tuple[Any, ...]] = None
        required = (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        )
        default = None if required else f.default

        if get_origin(hint) is Literal:
            choices = get_args(hint)
            base = type(choices[0])
        elif _is_optional(hint):
            base = _optional_arg(hint)
            if get_origin(base) is Literal:
                choices = get_args(base)
                base = type(choices[0])
        else:
            base = hint

        infos.append(
            ArgInfo(
                name=f.name,
                type=base if base in (str, int, float, bool) else str,
                doc=doc,
                required=required,
                default=default,
                choices=choices,
                positional=bool(meta.get("positional")),
                is_bool=base is bool,
                kind=meta.get("kind"),
                exts=tuple(meta.get("exts", ())),
            )
        )
    return infos


def _is_optional(hint) -> bool:  # noqa: ANN001
    return get_origin(hint) is not None and type(None) in get_args(hint)


def _optional_arg(hint):  # noqa: ANN001
    args = [a for a in get_args(hint) if a is not type(None)]
    return args[0]


@dataclass(frozen=True)
class CommandSpec:
    """One CLI command.  ``name`` is the two-level ``"group verb"``;
    ``runner`` is a ``"module:function"`` string imported only when the
    command runs (a runner takes ``(inputs, ctx)`` and returns a
    :class:`civilpy.cli.io_.CommandResult`)."""

    name: str
    summary: str
    input_model: type
    runner: str
    description: str = ""
    requires: Tuple[str, ...] = ()

    @property
    def group(self) -> str:
        return self.name.split()[0]

    @property
    def verb(self) -> str:
        return self.name.split()[1]

    @property
    def args(self) -> List[ArgInfo]:
        return introspect(self.input_model)


#: Command modules under civilpy.cli.commands, each exporting ``SPECS``.
COMMAND_MODULES = ("boring", "odot", "hydro", "road", "snbi", "photos",
                   "report", "spanwire")

_specs_cache: Optional[List[CommandSpec]] = None


def all_specs() -> List[CommandSpec]:
    global _specs_cache
    if _specs_cache is None:
        specs: List[CommandSpec] = []
        for mod_name in COMMAND_MODULES:
            mod = importlib.import_module(f"civilpy.cli.commands.{mod_name}")
            specs.extend(mod.SPECS)
        _specs_cache = specs
    return _specs_cache


def find_spec(group: str, verb: str) -> Optional[CommandSpec]:
    for spec in all_specs():
        if spec.group == group and spec.verb == verb:
            return spec
    return None


def resolve_runner(spec: CommandSpec) -> Callable:
    mod_name, func_name = spec.runner.split(":")
    return getattr(importlib.import_module(mod_name), func_name)


def build_inputs(spec: CommandSpec, values: dict):
    """Instantiate the input dataclass from parsed argument values."""
    names = {f.name for f in dataclasses.fields(spec.input_model)}
    return spec.input_model(**{k: v for k, v in values.items() if k in names})

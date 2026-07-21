#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Registry introspection: input dataclasses → CLI argument metadata."""

from dataclasses import dataclass, field
from typing import Literal, Optional

import pytest

from civilpy.cli.registry import (
    all_specs,
    find_spec,
    introspect,
    resolve_runner,
)


@dataclass(frozen=True)
class SampleInput:
    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".xml",),
        "doc": "the input file",
    })
    mode: Literal["fast", "slow"] = field(default="fast", metadata={
        "doc": "processing mode",
    })
    limit: Optional[float] = field(default=None, metadata={
        "doc": "optional cutoff",
    })
    verbose: bool = field(default=False, metadata={"doc": "chatty output"})


def test_introspect_sample_model():
    args = {a.name: a for a in introspect(SampleInput)}

    assert args["path"].positional and args["path"].required
    assert args["path"].kind == "path" and args["path"].exts == (".xml",)

    assert args["mode"].choices == ("fast", "slow")
    assert args["mode"].type is str and args["mode"].default == "fast"
    assert args["mode"].flag == "--mode"

    assert args["limit"].type is float and not args["limit"].required
    assert args["limit"].default is None

    assert args["verbose"].is_bool and args["verbose"].default is False


def test_introspect_requires_field_docs():
    @dataclass(frozen=True)
    class Undocumented:
        x: int

    with pytest.raises(TypeError, match="doc"):
        introspect(Undocumented)


def test_describe_mentions_choices_and_default():
    args = {a.name: a for a in introspect(SampleInput)}
    text = args["mode"].describe()
    assert "fast" in text and "slow" in text and "default fast" in text


def test_all_specs_are_wellformed():
    specs = all_specs()
    assert specs, "no commands registered"
    names = [s.name for s in specs]
    assert len(names) == len(set(names)), "duplicate command names"
    for spec in specs:
        assert len(spec.name.split()) == 2, spec.name
        assert spec.summary
        assert callable(resolve_runner(spec)), spec.runner
        assert spec.args  # introspection works for every input model


def test_find_spec():
    assert find_spec("hydro", "channel") is not None
    assert find_spec("hydro", "nope") is None

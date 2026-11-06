"""YAML helpers tuned for RPCS3's files.

* RPCS3 config files must round-trip without type coercion (``0x8516...`` must
  stay a string, ``01.22`` must not become a float), so configs are loaded with
  the BaseLoader (everything is a string) and dumped back verbatim.
* RPCS3's official ``patch.yml`` re-uses anchor names, which PyYAML rejects by
  default; ``load_patch_yaml`` tolerates that the same way yaml-cpp does
  (a later anchor simply shadows the earlier one).
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import yaml
from yaml.composer import Composer
from yaml.events import AliasEvent, ScalarEvent, SequenceStartEvent, MappingStartEvent
from yaml.nodes import ScalarNode, SequenceNode, MappingNode


class _DupAnchorComposer(Composer):
    def compose_node(self, parent, index):  # noqa: D401 - PyYAML override
        if self.check_event(AliasEvent):
            event = self.get_event()
            anchor = event.anchor
            if anchor not in self.anchors:
                raise yaml.composer.ComposerError(None, None, f"found undefined alias {anchor!r}", event.start_mark)
            return self.anchors[anchor]
        event = self.peek_event()
        anchor = event.anchor
        # NOTE: no duplicate-anchor check here, later definitions win.
        self.descend_resolver(parent, index)
        if self.check_event(ScalarEvent):
            node = self.compose_scalar_node(anchor)
        elif self.check_event(SequenceStartEvent):
            node = self.compose_sequence_node(anchor)
        elif self.check_event(MappingStartEvent):
            node = self.compose_mapping_node(anchor)
        self.ascend_resolver()
        return node


class PatchLoader(yaml.reader.Reader, yaml.scanner.Scanner, yaml.parser.Parser, _DupAnchorComposer,
                  yaml.constructor.SafeConstructor, yaml.resolver.Resolver):
    def __init__(self, stream):
        yaml.reader.Reader.__init__(self, stream)
        yaml.scanner.Scanner.__init__(self)
        yaml.parser.Parser.__init__(self)
        _DupAnchorComposer.__init__(self)
        yaml.constructor.SafeConstructor.__init__(self)
        yaml.resolver.Resolver.__init__(self)


class StrLoader(yaml.reader.Reader, yaml.scanner.Scanner, yaml.parser.Parser, _DupAnchorComposer,
                yaml.constructor.BaseConstructor, yaml.resolver.BaseResolver):
    """Everything is a str (like RPCS3's own cfg parser)."""

    def __init__(self, stream):
        yaml.reader.Reader.__init__(self, stream)
        yaml.scanner.Scanner.__init__(self)
        yaml.parser.Parser.__init__(self)
        _DupAnchorComposer.__init__(self)
        yaml.constructor.BaseConstructor.__init__(self)
        yaml.resolver.BaseResolver.__init__(self)


def load_patch_yaml(path: str | os.PathLike) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        # StrLoader: keeps app versions like 01.22 as strings (SafeLoader would yield 1.22)
        data = yaml.load(f, Loader=StrLoader)
    return data or {}


def load_cfg(path: str | os.PathLike) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8-sig") as f:
        data = yaml.load(f, Loader=StrLoader)
    return data if isinstance(data, dict) else {}


class _CfgDumper(yaml.emitter.Emitter, yaml.serializer.Serializer, yaml.representer.SafeRepresenter,
                 yaml.resolver.BaseResolver):
    """No implicit typing -> plain scalars are never quoted just because they look
    like bools/numbers (RPCS3 writes `Write Color Buffers: true`, not 'true')."""

    def __init__(self, stream, default_style=None, default_flow_style=False, canonical=None, indent=None,
                 width=None, allow_unicode=None, line_break=None, encoding=None, explicit_start=None,
                 explicit_end=None, version=None, tags=None, sort_keys=True):
        yaml.emitter.Emitter.__init__(self, stream, canonical=canonical, indent=indent, width=width,
                                      allow_unicode=allow_unicode, line_break=line_break)
        yaml.serializer.Serializer.__init__(self, encoding=encoding, explicit_start=explicit_start,
                                            explicit_end=explicit_end, version=version, tags=tags)
        yaml.representer.SafeRepresenter.__init__(self, default_style=default_style,
                                                  default_flow_style=default_flow_style, sort_keys=sort_keys)
        yaml.resolver.BaseResolver.__init__(self)


def _str_presenter(dumper, value: str):
    # Quote only when needed so the file stays readable and RPCS3-compatible;
    # empty strings must be "" (a bare `key:` would be read as null).
    if value == "":
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_CfgDumper.add_representer(str, _str_presenter)
_CfgDumper.add_representer(bool, lambda d, v: d.represent_scalar("tag:yaml.org,2002:bool", "true" if v else "false"))


def _stringify(obj: Any) -> Any:
    """Convert python values to the strings RPCS3 expects."""
    if isinstance(obj, dict):
        return {str(k): _stringify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_stringify(v) for v in obj]
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if obj is None:
        return ""
    return str(obj)


def dump_cfg(data: dict[str, Any]) -> str:
    return yaml.dump(_stringify(data), Dumper=_CfgDumper, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=4096)


def dump_yaml(data: Any) -> str:
    """Typed dump (used for patch_config.yml where bools/floats matter)."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=4096)


def atomic_write(path: str | os.PathLike, text: str) -> None:
    path = os.fspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

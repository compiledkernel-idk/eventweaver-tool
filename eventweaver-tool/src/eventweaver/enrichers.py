from __future__ import annotations

import importlib
from typing import Callable, Iterable, List

from .models import Event


def load_enrichers(paths: Iterable[str]) -> List[Callable[[Event], Event | None]]:
    enrichers: List[Callable[[Event], Event | None]] = []
    for spec in paths:
        if not spec:
            continue
        module_name, _, attr = spec.partition(":")
        if not module_name:
            raise ValueError(f"Invalid enricher specification: '{spec}'")
        module = importlib.import_module(module_name)
        attr_name = attr or "enrich"
        candidate = getattr(module, attr_name)
        if not callable(candidate):
            raise TypeError(f"Enricher {spec} is not callable")
        enrichers.append(candidate)
    return enrichers

from __future__ import annotations

import heapq
from itertools import count
from typing import Callable, Iterable, Iterator, List, Optional, Sequence

from .analysis import run_all_heuristics
from .config import Config
from .dsl import compile_expression
from .enrichers import load_enrichers
from .models import Event, Insight
from .sources import SourceLoader


def build_loaders(config: Config) -> List[SourceLoader]:
    enrichers = load_enrichers(config.enrichers)
    return [SourceLoader(source, config.defaults, enrichers) for source in config.sources]


def fuse_events(
    loaders: Sequence[SourceLoader],
    predicate: Optional[Callable[[Event], bool]] = None,
) -> Iterator[Event]:
    iterators = [iter(loader.iter_events()) for loader in loaders]
    heap: List[tuple] = []
    ticket = count()

    for idx, it in enumerate(iterators):
        try:
            event = next(it)
        except StopIteration:
            continue
        heapq.heappush(heap, (event.timestamp, next(ticket), idx, event))

    while heap:
        _, _, idx, event = heapq.heappop(heap)
        if predicate is None or predicate(event):
            yield event
        try:
            next_event = next(iterators[idx])
        except StopIteration:
            continue
        heapq.heappush(heap, (next_event.timestamp, next(ticket), idx, next_event))


def stream_events(
    config: Config,
    *,
    expression: Optional[str] = None,
) -> Iterator[Event]:
    predicate: Optional[Callable[[Event], bool]] = None
    if expression:
        predicate = compile_expression(expression)
    loaders = build_loaders(config)
    return fuse_events(loaders, predicate)


def collect_events(config: Config, expression: Optional[str] = None) -> List[Event]:
    return list(stream_events(config, expression=expression))


def generate_insights(config: Config, expression: Optional[str] = None) -> List[Insight]:
    events = collect_events(config, expression=expression)
    heuristics = config.heuristics
    return run_all_heuristics(
        events,
        gap_ms=heuristics.gap_ms,
        burst_window_ms=heuristics.burst_window_ms,
        burst_threshold=heuristics.burst_threshold,
        severity_horizon=heuristics.severity_horizon,
        severity_delta=heuristics.severity_delta,
    )

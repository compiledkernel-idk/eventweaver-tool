from __future__ import annotations

from collections import deque
from datetime import timedelta
from typing import Iterable, List

from .models import Event, Insight


def detect_time_gaps(events: Iterable[Event], threshold_ms: int) -> List[Insight]:
    events = list(sorted(events, key=lambda e: e.timestamp))
    insights: List[Insight] = []
    if len(events) < 2 or threshold_ms <= 0:
        return insights

    threshold = timedelta(milliseconds=threshold_ms)
    for prev, current in zip(events, events[1:]):
        delta = current.timestamp - prev.timestamp
        if delta >= threshold:
            insights.append(
                Insight(
                    kind="time_gap",
                    summary=f"Gap of {int(delta.total_seconds())}s between {prev.source} and {current.source}",
                    start=prev.timestamp,
                    end=current.timestamp,
                    evidence=[prev, current],
                    metadata={"gap_seconds": delta.total_seconds()},
                )
            )
    return insights


def detect_bursts(events: Iterable[Event], window_ms: int, threshold: int) -> List[Insight]:
    events = list(sorted(events, key=lambda e: e.timestamp))
    insights: List[Insight] = []
    if window_ms <= 0 or threshold <= 1:
        return insights

    window = deque()
    span = timedelta(milliseconds=window_ms)
    last_report_end = None

    for event in events:
        window.append(event)
        while window and (event.timestamp - window[0].timestamp) > span:
            window.popleft()
        if len(window) >= threshold:
            start_event = window[0]
            end_event = window[-1]
            if last_report_end and start_event.timestamp <= last_report_end:
                continue
            insights.append(
                Insight(
                    kind="burst",
                    summary=f"{len(window)} events within {window_ms}ms window",
                    start=start_event.timestamp,
                    end=end_event.timestamp,
                    evidence=list(window),
                    metadata={
                        "count": len(window),
                        "window_ms": window_ms,
                        "sources": sorted({evt.source for evt in window}),
                    },
                )
            )
            last_report_end = end_event.timestamp
    return insights


def detect_severity_regressions(events: Iterable[Event], horizon: int, delta: float) -> List[Insight]:
    events = list(sorted(events, key=lambda e: e.timestamp))
    if horizon <= 1:
        return []

    buffer: deque[Event] = deque(maxlen=horizon)
    insights: List[Insight] = []
    previous_mean: float | None = None

    for event in events:
        if event.severity is None:
            continue
        buffer.append(event)
        if len(buffer) < buffer.maxlen:
            continue
        values = [evt.severity for evt in buffer if evt.severity is not None]
        if not values:
            continue
        current_mean = sum(values) / len(values)
        if previous_mean is not None and (current_mean - previous_mean) >= delta:
            insights.append(
                Insight(
                    kind="severity_regression",
                    summary=(
                        f"Rolling severity mean worsened by {current_mean - previous_mean:.2f}"
                    ),
                    start=buffer[0].timestamp,
                    end=buffer[-1].timestamp,
                    evidence=list(buffer),
                    metadata={
                        "previous_mean": previous_mean,
                        "current_mean": current_mean,
                        "horizon": horizon,
                    },
                )
            )
        previous_mean = current_mean

    return insights


def run_all_heuristics(
    events: Iterable[Event],
    *,
    gap_ms: int | None = None,
    burst_window_ms: int | None = None,
    burst_threshold: int | None = None,
    severity_horizon: int | None = None,
    severity_delta: float = 0.5,
) -> List[Insight]:
    events_list = list(events)
    insights: List[Insight] = []
    if gap_ms:
        insights.extend(detect_time_gaps(events_list, gap_ms))
    if burst_window_ms and burst_threshold:
        insights.extend(detect_bursts(events_list, burst_window_ms, burst_threshold))
    if severity_horizon:
        insights.extend(detect_severity_regressions(events_list, severity_horizon, severity_delta))
    insights.sort(key=lambda insight: (insight.start, insight.kind))
    return insights

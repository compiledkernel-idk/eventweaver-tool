"""EventWeaver package."""

from .models import Event, Insight
from .timeline import fuse_events, stream_events

__all__ = ["Event", "Insight", "fuse_events", "stream_events"]

__version__ = "0.1.0"

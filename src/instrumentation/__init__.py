"""Instrumentation layer.

Cattura in modo trasparente le evidenze osservabili per le tre macro-dimensioni
di ricerca (Control Flow, Data Flow, Comportamentale), come descritte nel
documento "Sonde ed evidenze per le tre macro-dimensioni". Non emette alcun
giudizio di verificabilità: solo raccolta, tipizzazione e aggregazione.
"""

from .events import EventKind, MacroCategory, TraceEvent, ChannelId  # noqa: F401
from .session import RunSessionManager  # noqa: F401
from .store import EventStore, ExperimentStore  # noqa: F401
from .aggregator import Aggregator, CHANNEL_LABELS  # noqa: F401
from .recorder import Recorder  # noqa: F401

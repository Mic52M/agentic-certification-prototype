"""Schema unificato per gli eventi di trace.

Ogni evento cattura una osservazione atomica in un punto architetturale del
sistema. Ogni evento è taggato con:

- la macro-dimensione di ricerca a cui contribuisce (control_flow, data_flow,
  behavioral);
- il canale AgentLeak (C1..C7) quando applicabile, per il data-flow;
- un tipo semantico (event_type) che identifica l'evidenza specifica.

L'evento è deliberatamente auto-descrittivo: ogni istanza porta con sé abbastanza
metadati da essere ispezionabile senza risalire al contesto di esecuzione.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =========================================================================
# Enumerazioni: rendono espliciti i valori ammessi.
# =========================================================================
class MacroCategory(str, Enum):
    """Le tre macro-dimensioni di ricerca."""
    CONTROL_FLOW = "control_flow"
    DATA_FLOW = "data_flow"
    BEHAVIORAL = "behavioral"


class ChannelId(str, Enum):
    """I sette canali di comunicazione del framework AgentLeak."""
    C1_FINAL_OUTPUT = "C1"       # output finale verso l'utente
    C2_INTER_AGENT = "C2"        # messaggi tra agenti
    C3_TOOL_INPUT = "C3"         # input dei tool
    C4_TOOL_OUTPUT = "C4"        # output dei tool
    C5_SHARED_MEMORY = "C5"      # memoria condivisa (workspace)
    C6_REASONING_TRACE = "C6"    # log e reasoning traces
    C7_ARTIFACT = "C7"           # artefatti persistenti


class EventKind(str, Enum):
    """Tipo semantico dell'evidenza raccolta.

    I prefissi CF/DF/BH mappano alle evidenze del documento di riferimento
    (A1-A4 control flow, B1-B4 data flow, C1-C4 behavioral). Sono nomi
    tecnici stabili: non cambiarli senza aggiornare l'aggregator.
    """
    # --- Control Flow (evidenze A1-A4) ---
    ORCHESTRATOR_DECISION = "orchestrator_decision"   # A1
    PLANNING_SPAN = "planning_span"                    # A2
    REPLANNING = "replanning"                          # A2 bis
    HANDOFF = "handoff"                                # A3
    PATH_METRIC = "path_metric"                        # A4

    # --- Data Flow (evidenze B1-B4, canali AgentLeak) ---
    CHANNEL_EMISSION = "channel_emission"              # B1 (generico su C1-C7)
    TOOL_CALL = "tool_call"                            # C3
    TOOL_RESULT = "tool_result"                        # C4
    INTER_AGENT_MSG = "inter_agent_message"            # C2
    SHARED_MEMORY_WRITE = "shared_memory_write"        # C5
    SHARED_MEMORY_READ = "shared_memory_read"          # C5
    FINAL_OUTPUT = "final_output"                      # C1
    ARTIFACT_PRODUCED = "artifact_produced"            # C7
    REASONING_STEP = "reasoning_step"                  # C6

    # --- Behavioral (evidenze C1-C4) ---
    STATE_SNAPSHOT = "state_snapshot"                  # per state<->output
    DECISION_POINT = "decision_point"                  # per intention-behavior
    TRAJECTORY_STEP = "trajectory_step"                # timeline unificata

    # --- Meta ---
    RUN_METADATA = "run_metadata"
    RUN_END = "run_end"
    ERROR = "error"


# Mapping evento -> macro-dimensioni a cui contribuisce (una evidenza può
# essere rilevante per più di una macro; per esempio un handoff informa sia
# il control flow sia il data flow via il payload trasferito).
KIND_TO_MACROS: dict[EventKind, tuple[MacroCategory, ...]] = {
    EventKind.ORCHESTRATOR_DECISION: (MacroCategory.CONTROL_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.PLANNING_SPAN:         (MacroCategory.CONTROL_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.REPLANNING:            (MacroCategory.CONTROL_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.HANDOFF:               (MacroCategory.CONTROL_FLOW, MacroCategory.DATA_FLOW),
    EventKind.PATH_METRIC:           (MacroCategory.CONTROL_FLOW,),
    EventKind.CHANNEL_EMISSION:      (MacroCategory.DATA_FLOW,),
    EventKind.TOOL_CALL:             (MacroCategory.DATA_FLOW, MacroCategory.CONTROL_FLOW),
    EventKind.TOOL_RESULT:           (MacroCategory.DATA_FLOW,),
    EventKind.INTER_AGENT_MSG:       (MacroCategory.DATA_FLOW,),
    EventKind.SHARED_MEMORY_WRITE:   (MacroCategory.DATA_FLOW,),
    EventKind.SHARED_MEMORY_READ:    (MacroCategory.DATA_FLOW,),
    EventKind.FINAL_OUTPUT:          (MacroCategory.DATA_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.ARTIFACT_PRODUCED:     (MacroCategory.DATA_FLOW,),
    EventKind.REASONING_STEP:        (MacroCategory.DATA_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.STATE_SNAPSHOT:        (MacroCategory.BEHAVIORAL,),
    EventKind.DECISION_POINT:        (MacroCategory.BEHAVIORAL, MacroCategory.CONTROL_FLOW),
    EventKind.TRAJECTORY_STEP:       (MacroCategory.BEHAVIORAL,),
    EventKind.RUN_METADATA:          (MacroCategory.CONTROL_FLOW, MacroCategory.DATA_FLOW,
                                      MacroCategory.BEHAVIORAL),
    EventKind.RUN_END:               (MacroCategory.CONTROL_FLOW, MacroCategory.BEHAVIORAL),
    EventKind.ERROR:                 (MacroCategory.CONTROL_FLOW,),
}


# Mapping evento -> canale AgentLeak di default (dove si emette).
KIND_TO_CHANNEL: dict[EventKind, ChannelId | None] = {
    EventKind.FINAL_OUTPUT:        ChannelId.C1_FINAL_OUTPUT,
    EventKind.INTER_AGENT_MSG:     ChannelId.C2_INTER_AGENT,
    EventKind.TOOL_CALL:           ChannelId.C3_TOOL_INPUT,
    EventKind.TOOL_RESULT:         ChannelId.C4_TOOL_OUTPUT,
    EventKind.SHARED_MEMORY_WRITE: ChannelId.C5_SHARED_MEMORY,
    EventKind.SHARED_MEMORY_READ:  ChannelId.C5_SHARED_MEMORY,
    EventKind.REASONING_STEP:      ChannelId.C6_REASONING_TRACE,
    EventKind.PLANNING_SPAN:       ChannelId.C6_REASONING_TRACE,
    EventKind.REPLANNING:          ChannelId.C6_REASONING_TRACE,
    EventKind.ARTIFACT_PRODUCED:   ChannelId.C7_ARTIFACT,
    EventKind.CHANNEL_EMISSION:    None,  # canale specificato caso per caso
    EventKind.ORCHESTRATOR_DECISION: None,
    EventKind.HANDOFF:             None,
    EventKind.PATH_METRIC:         None,
    EventKind.STATE_SNAPSHOT:      None,
    EventKind.DECISION_POINT:      None,
    EventKind.TRAJECTORY_STEP:     None,
    EventKind.RUN_METADATA:        None,
    EventKind.RUN_END:              None,
    EventKind.ERROR:                None,
}


# =========================================================================
# TraceEvent: dataclass unica per ogni evento raccolto.
# =========================================================================
def _new_event_id() -> str:
    return uuid.uuid4().hex[:16]


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class TraceEvent:
    """Un evento nella trace, unico schema per tutte le macro-dimensioni."""

    # --- identificatori ---
    event_id: str = field(default_factory=_new_event_id)
    run_id: str = ""
    experiment_id: str = ""

    # --- tipizzazione ---
    macro_categories: list[MacroCategory] = field(default_factory=list)
    event_type: EventKind = EventKind.TRAJECTORY_STEP
    channel_id: ChannelId | None = None  # canale AgentLeak se applicabile

    # --- localizzazione architetturale ---
    agent_id: str = ""              # chi ha prodotto/subito l'evento
    source_component: str = ""      # componente sorgente (es. "orchestrator")
    target_component: str | None = None  # componente destinatario (es. "planner")
    tool_name: str | None = None    # nome del tool per gli eventi tool

    # --- timing ---
    timestamp_start: int = field(default_factory=_now_ms)
    timestamp_end: int = field(default_factory=_now_ms)
    duration_ms: int = 0

    # --- payload ---
    # summary è quello che si mostra in UI (breve, leggibile)
    payload_summary: str = ""
    # redacted è la versione ridotta/mascherata del payload (senza contenuti sensibili)
    payload_redacted: dict[str, Any] = field(default_factory=dict)
    # metadata è per la struttura (numero step, iteration, snapshot key, ecc.)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "macro_categories": [m.value for m in self.macro_categories],
            "event_type": self.event_type.value,
            "channel_id": self.channel_id.value if self.channel_id else None,
            "agent_id": self.agent_id,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "tool_name": self.tool_name,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "duration_ms": self.duration_ms,
            "payload_summary": self.payload_summary,
            "payload_redacted": self.payload_redacted,
            "metadata": self.metadata,
        }


def build_event(
    event_type: EventKind,
    *,
    run_id: str,
    experiment_id: str,
    agent_id: str = "",
    source_component: str = "",
    target_component: str | None = None,
    tool_name: str | None = None,
    payload_summary: str = "",
    payload_redacted: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    duration_ms: int = 0,
    channel_id: ChannelId | None = None,
) -> TraceEvent:
    """Costruisce un TraceEvent riempiendo automaticamente i tag di macro
    e canale a partire dal tipo di evento (KIND_TO_MACROS / KIND_TO_CHANNEL)."""
    now = _now_ms()
    ch = channel_id if channel_id is not None else KIND_TO_CHANNEL.get(event_type)
    return TraceEvent(
        run_id=run_id,
        experiment_id=experiment_id,
        macro_categories=list(KIND_TO_MACROS.get(event_type, ())),
        event_type=event_type,
        channel_id=ch,
        agent_id=agent_id,
        source_component=source_component,
        target_component=target_component,
        tool_name=tool_name,
        timestamp_start=now,
        timestamp_end=now,
        duration_ms=duration_ms,
        payload_summary=payload_summary,
        payload_redacted=payload_redacted or {},
        metadata=metadata or {},
    )

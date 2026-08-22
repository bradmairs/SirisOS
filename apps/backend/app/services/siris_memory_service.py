from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.services.ollama_service import OllamaChatClient
from app.services.ollama_service import chat_client as _default_chat_client

MemoryClass = Literal["fact", "preference", "episode", "decision", "observation", "conversation"]
MEMORY_CLASSES: tuple[MemoryClass, ...] = (
    "fact",
    "preference",
    "episode",
    "decision",
    "observation",
    "conversation",
)
MAX_MEMORY_RECORDS = 1000

# Only these three classes are ever auto-suggested from a conversation --
# "episode"/"decision"/"conversation" describe things that happened (a
# session, a choice made), which this single-exchange extraction has no
# reliable way to summarise correctly; a person adding one by hand (as the
# existing manual "add memory" dialog already lets them) makes that call
# with full context this extraction step doesn't have.
SUGGESTABLE_MEMORY_CLASSES = ("fact", "preference", "observation")
MAX_SUGGESTIONS_PER_EXCHANGE = 3

# Unlike every other Ollama-touching feature in this app (a deterministic
# service computes real facts, Ollama only phrases them), there is no
# ground-truth tool result for a memory suggestion to check against -- the
# "fact" IS the extraction. The one thing that keeps this honest: the
# extraction is scoped to a single real message the user already saw on
# screen, with an explicit "only what was literally said, never inferred"
# instruction, and nothing is ever persisted from it without the user
# tapping Save (ADR 103) -- the same review step the pre-existing manual
# "add memory" dialog already requires for a human-authored memory.
#
# Deliberately built from the athlete's message ALONE, never Siris's reply:
# live testing against the real 3B model found that including Siris's reply
# -- especially SirisAgent's own scoped-topic refusal ("I can only answer
# questions about...") -- made the model treat the whole exchange as
# out-of-scope and return [] even when the athlete's message plainly stated
# a fact, 100% reproducible across repeated runs. Rewording the prompt to
# explicitly tell the model to ignore Siris's reply did not fix this (still
# 100% empty) -- the same lesson as ADR 098's search_knowledge redesign:
# a small local model's unreliability on a judgment task is fixed by
# changing what data it's given, not by tuning instructions further.
MEMORY_SUGGESTION_SYSTEM_PROMPT = (
    "You extract memory-worthy facts from one message an athlete sent to Siris, an "
    "assistant inside SirisOS. Extract ONLY specific, standalone facts about the athlete "
    "personally or their homelab/environment that were ACTUALLY STATED in the message "
    "-- never infer, generalise, or invent anything not literally said. Do not extract "
    "training/health/homelab DATA already tracked elsewhere as structured data (step "
    "counts, strength scores, container status, project names, readiness scores) -- only "
    "qualitative personal context Siris has nowhere else to remember: who the athlete "
    "is, their preferences, and durable facts about their setup.\n\n"
    "Reply with ONLY a JSON array, nothing else -- no prose, no markdown fences. Each "
    'item: {"memory_class": one of "fact", "preference", or "observation", "content": a '
    "short, standalone sentence not referencing \"the athlete\" or \"they\" -- write it "
    "as a direct statement, e.g. \"Works as a civil engineer\" not \"The athlete works "
    "as a civil engineer\"}. If there is nothing memory-worthy in the message, reply "
    "with exactly []. Never return more than 3 items.\n\n"
    "Example message -- \"I'm a civil engineer and my NAS is called vault\" -- correct "
    'reply: [{"memory_class": "fact", "content": "Works as a civil engineer."}, '
    '{"memory_class": "fact", "content": "Their NAS is named \\"vault\\"."}]\n'
    "Example message -- \"how strong am I?\" -- correct reply: [] (a question asking for "
    "already-tracked structured data, not a new personal fact)."
)


def _default_memory_path() -> Path:
    return Path(os.getenv("SIRISOS_MEMORY_PATH", "/app/data/siris-memory.json"))


def _atomic_json_write(path: Path, payload: object, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=prefix, suffix=".tmp", delete=False
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        raise MemoryStoreUnavailableError("Unable to persist Siris memory.") from exc


class MemoryStoreUnavailableError(Exception):
    pass


class MemoryNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class Memory:
    id: str
    memory_class: MemoryClass
    content: str
    source: str | None
    created_at: str


@dataclass(frozen=True)
class MemorySuggestion:
    memory_class: MemoryClass
    content: str


class SirisMemoryService:
    def __init__(self, memory_path: Path | None = None, chat_client: OllamaChatClient | None = None) -> None:
        self._memory_path = memory_path or _default_memory_path()
        self._chat_client = chat_client or _default_chat_client

    def list_memory(self, *, memory_class: MemoryClass | None = None) -> list[Memory]:
        records = self._load()
        if memory_class is not None:
            records = [item for item in records if item.memory_class == memory_class]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records

    def create_memory(
        self, *, memory_class: MemoryClass, content: str, source: str | None = None
    ) -> Memory:
        records = self._load()
        record = Memory(
            id=str(uuid.uuid4()),
            memory_class=memory_class,
            content=content.strip(),
            source=(source.strip() or None) if source else None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        records.append(record)
        self._save(records[-MAX_MEMORY_RECORDS:])
        return record

    def delete_memory(self, record_id: str) -> None:
        records = self._load()
        remaining = [item for item in records if item.id != record_id]
        if len(remaining) == len(records):
            raise MemoryNotFoundError(f"Memory record '{record_id}' not found.")
        self._save(remaining)

    async def suggest(self, *, user_message: str, assistant_message: str) -> list[MemorySuggestion]:
        # assistant_message is accepted (the caller has it on hand from the
        # chat turn it's suggesting from) but deliberately not sent to the
        # model -- see the module docstring above MEMORY_SUGGESTION_SYSTEM_PROMPT.
        del assistant_message
        if not self._chat_client.enabled:
            return []
        try:
            raw = await self._chat_client.complete(
                system=MEMORY_SUGGESTION_SYSTEM_PROMPT, prompt=user_message.strip()
            )
        except Exception:  # noqa: BLE001 - a suggestion failure must never break the chat turn
            return []
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if not isinstance(parsed, list):
            return []

        existing_content = {item.content.strip().lower() for item in self._load()}
        suggestions: list[MemorySuggestion] = []
        for item in parsed[:MAX_SUGGESTIONS_PER_EXCHANGE]:
            if not isinstance(item, dict):
                continue
            memory_class = item.get("memory_class")
            content = item.get("content")
            if memory_class not in SUGGESTABLE_MEMORY_CLASSES:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            content = content.strip()
            if content.lower() in existing_content:
                continue
            suggestions.append(MemorySuggestion(memory_class=memory_class, content=content))
        return suggestions

    def _load(self) -> list[Memory]:
        if not self._memory_path.exists():
            return []
        try:
            raw = json.loads(self._memory_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("Siris memory store root must be a list")
            return [Memory(**item) for item in raw]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MemoryStoreUnavailableError("Siris memory store is unavailable.") from exc

    def _save(self, records: list[Memory]) -> None:
        _atomic_json_write(self._memory_path, [item.__dict__ for item in records], ".siris-memory-")

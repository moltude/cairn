"""
Machine-parseable tracing for transformations.

Trace files are JSON Lines (one JSON object per line). They are intentionally
not optimized for human reading; they are optimized for replay and diffing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional


class TraceWriter:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._fh = self._path.open("w", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def emit(self, event: Dict[str, Any]) -> None:
        # Add a timestamp if caller didn't.
        if "ts" not in event:
            event = dict(event)
            event["ts"] = datetime.now(timezone.utc).isoformat()

        def default(o: Any) -> Any:
            if is_dataclass(o):
                return asdict(o)
            return str(o)

        self._fh.write(json.dumps(event, ensure_ascii=False, default=default) + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class TraceReader:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


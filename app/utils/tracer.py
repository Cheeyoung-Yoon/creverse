
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional


class _NoopObj:
    id: str = ""

    def update(self, **_: Any) -> None:
        return None


class _NoopClient:
    def trace(self, **_: Any) -> _NoopObj:
        return _NoopObj()

    def span(self, **_: Any) -> _NoopObj:
        return _NoopObj()

    def generation(self, **_: Any) -> _NoopObj:
        return _NoopObj()

    def score(self, **_: Any) -> None:
        return None

    def flush(self) -> None:
        return None


class Tracer:
    """Lightweight Langfuse wrapper with safe no-op fallback.

    Env vars used when available:
      - LANGFUSE_PUBLIC_KEY
      - LANGFUSE_SECRET_KEY
      - LANGFUSE_BASE_URL (optional)
      - LANGFUSE_ENABLED ("1"/"true" to force on, "0"/"false" to force off)
    """

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = self._resolve_enabled(enabled)
        self._client = self._build_client() if self._enabled else _NoopClient()

    def _resolve_enabled(self, enabled: Optional[bool]) -> bool:
        if enabled is not None:
            return enabled
        flag = os.getenv("LANGFUSE_ENABLED")
        if flag is not None:
            return flag.lower() in {"1", "true", "yes", "on"}
        # Default: enable only if credentials are present and import works
        have_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
        if not have_keys:
            return False
        # Try import to confirm availability
        try:
            from langfuse import Langfuse  # type: ignore
            _ = Langfuse  # silence linter
            return True
        except Exception:
            return False

    def _build_client(self):  # type: ignore[no-untyped-def]
        try:
            from langfuse import Langfuse  # type: ignore
        except Exception:
            return _NoopClient()

        return Langfuse(
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            host=os.getenv("LANGFUSE_BASE_URL", None),
        )

    @property
    def enabled(self) -> bool:
        return not isinstance(self._client, _NoopClient)

    def flush(self) -> None:
        self._client.flush()

    # High-level helpers -------------------------------------------------
    def start_trace(
        self,
        *,
        name: str,
        input: Any | None = None,
        user_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        return self._client.trace(
            name=name,
            input=input,
            user_id=user_id,
            metadata=metadata,
            tags=tags,
        )

    def start_span(
        self,
        *,
        trace_id: str,
        name: str,
        input: Any | None = None,
        metadata: Dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        return self._client.span(
            trace_id=trace_id,
            name=name,
            input=input,
            metadata=metadata,
            tags=tags,
        )

    def log_generation(
        self,
        *,
        trace_id: str,
        name: str,
        model: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        usage: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        return self._client.generation(
            trace_id=trace_id,
            name=name,
            model=model,
            input=input,
            output=output,
            usage=usage,
            metadata=metadata,
            tags=tags,
        )

    def log_score(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        self._client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
            metadata=metadata,
        )

    # Context managers ---------------------------------------------------
    @contextmanager
    def traced(self, *, name: str, input: Any | None = None, user_id: str | None = None):
        trace = self.start_trace(name=name, input=input, user_id=user_id)
        try:
            yield trace
        finally:
            self.flush()


_GLOBAL: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = Tracer()
    return _GLOBAL


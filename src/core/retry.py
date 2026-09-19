from collections.abc import Awaitable, Callable

from src.utils.file_logger import log_structured_event


async def retry_async(
    operation: Callable[[], Awaitable[object]],
    *,
    attempts: int,
    stage: str,
    event: str,
    context: dict[str, object],
):
    """Retries an async operation and emits structured retry logs."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            log_structured_event(
                stage,
                event,
                attempt=attempt,
                attempts=attempts,
                error=str(exc),
                **context,
            )
            if attempt >= attempts:
                raise
    if last_error:
        raise last_error
    raise RuntimeError("Retry operation failed without an error.")

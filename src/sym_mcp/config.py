from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    pool_size: int = 10
    exec_timeout_sec: float = 3.0
    memory_limit_mb: int = 150
    queue_wait_sec: float = 2.0
    log_level: str = "INFO"
    max_output_chars: int = 1200
    hint_level: str = "medium"


def load_settings() -> Settings:
    return Settings(
        pool_size=int(os.getenv("SYMMCP_POOL_SIZE", "10")),
        exec_timeout_sec=float(os.getenv("SYMMCP_EXEC_TIMEOUT_SEC", "3")),
        memory_limit_mb=int(os.getenv("SYMMCP_MEMORY_LIMIT_MB", "150")),
        queue_wait_sec=float(os.getenv("SYMMCP_QUEUE_WAIT_SEC", "2")),
        log_level=os.getenv("SYMMCP_LOG_LEVEL", "INFO"),
        max_output_chars=max(100, int(os.getenv("SYMMCP_MAX_OUTPUT_CHARS", "1200"))),
        hint_level=os.getenv("SYMMCP_HINT_LEVEL", "medium"),
    )

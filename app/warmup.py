from __future__ import annotations

import logging
import time

from app.api.deps import AppContainer

logger = logging.getLogger(__name__)


def warm_up(container: AppContainer) -> None:
    if not container.settings.warmup_enabled:
        return
    started = time.perf_counter()
    try:
        container.repository.get_geography(container.settings.nation_geo_id)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "warm-up completed",
            extra={"warmup_ms": round(elapsed_ms, 2)},
        )
    except Exception as exc:
        logger.warning("warm-up failed: %s", exc)

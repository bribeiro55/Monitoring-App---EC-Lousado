from __future__ import annotations

from typing import Callable, Dict, Optional

from .callbacks_filters import register_otkph_filter_callbacks
from .callbacks_selection import register_otkph_selection_callbacks
from .callbacks_table import register_otkph_table_callbacks
from .callbacks_visuals import register_otkph_visual_callbacks


def register_otkph_callbacks(
    app,
    *,
    step_colors: Dict[int, str],
    find_log_path: Callable[[str], Optional[str]],
    cached_parse: Callable[[str], object],
) -> None:
    deps = dict(
        step_colors=step_colors,
        find_log_path=find_log_path,
        cached_parse=cached_parse,
    )
    register_otkph_filter_callbacks(app, **deps)
    register_otkph_selection_callbacks(app, **deps)
    register_otkph_visual_callbacks(app, **deps)
    register_otkph_table_callbacks(app, **deps)


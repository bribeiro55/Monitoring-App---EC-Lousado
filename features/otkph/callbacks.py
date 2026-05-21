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
    rows_to_df: Callable,
    find_log_path: Callable[[str], Optional[str]],
    cached_parse: Callable[[str], object],
    serialize_df_rows: Callable,
) -> None:
    deps = dict(
        step_colors=step_colors,
        rows_to_df=rows_to_df,
        find_log_path=find_log_path,
        cached_parse=cached_parse,
        serialize_df_rows=serialize_df_rows,
    )
    register_otkph_filter_callbacks(app, **deps)
    register_otkph_selection_callbacks(app, **deps)
    register_otkph_visual_callbacks(app, **deps)
    register_otkph_table_callbacks(app, **deps)


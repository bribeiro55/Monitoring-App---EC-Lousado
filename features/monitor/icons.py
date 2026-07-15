from __future__ import annotations

import urllib.parse


def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg)


_ICON_EMPTY_CHART = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" '
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 17v-2m3 2v-4m3 4v-6M3 21h18M3 3h18"/></svg>'
)
_ICON_EXPAND = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/></svg>'
)
_ICON_DOWNLOAD = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>'
)
_ICON_CSV = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h8M8 9h3"/></svg>'
)
_ICON_TAB_MONITOR = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>'
)
_ICON_TAB_ANALYSIS = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 17v-2m3 2v-4m3 4v-6M3 21h18M3 3h18"/></svg>'
)
_ICON_TAB_OTKPH = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>'
    '<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
)

_img_tab_style: dict = {"width": "14px", "height": "14px", "display": "block", "opacity": "0.85"}

ICON_CLOCK = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/>'
    '<polyline points="12 6 12 12 16 14"/></svg>'
)
ICON_REGISTRY = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></svg>'
)
_ICON_END = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-6"/></svg>'
)
ICON_SYNC = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>'
    '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>'
)

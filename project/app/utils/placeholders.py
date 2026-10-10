"""Generates colourful SVG artwork for demo products/categories (no downloads needed)."""

GLYPHS = {
    "headphones": '<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>',
    "watch": '<circle cx="12" cy="12" r="7"/><polyline points="12 9 12 12 13.5 13.5"/><path d="M16.51 17.35l-.35 3.83a2 2 0 0 1-2 1.82H9.83a2 2 0 0 1-2-1.82l-.35-3.83m.01-10.7l.35-3.83A2 2 0 0 1 9.83 1h4.35a2 2 0 0 1 2 1.82l.35 3.83"/>',
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    "coffee": '<path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    "bag": '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>',
}

_BLOBS = {
    1: [(610, 190, 250), (170, 640, 190)],
    2: [(190, 210, 230), (640, 610, 210)],
    3: [(420, 110, 190), (150, 520, 250), (660, 670, 150)],
}


def artwork_svg(glyph: str, hue: int, variant: int = 1) -> str:
    """Return an 800x800 SVG: soft gradient, blobs and a centred line icon."""
    hue %= 360
    h2 = (hue + 35) % 360
    blobs = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="hsla({h2},80%,76%,.45)"/>'
        for x, y, r in _BLOBS.get(variant, _BLOBS[1])
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue},85%,94%)"/><stop offset="1" stop-color="hsl({h2},75%,84%)"/>'
        "</linearGradient></defs>"
        '<rect width="800" height="800" fill="url(#g)"/>'
        f"{blobs}"
        '<circle cx="400" cy="400" r="240" fill="hsla(0,0%,100%,.6)"/>'
        f'<g transform="translate(400 400) scale(13) translate(-12 -12)" fill="none" '
        f'stroke="hsl({hue},45%,28%)" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">'
        f"{GLYPHS.get(glyph, GLYPHS['bag'])}</g></svg>"
    )

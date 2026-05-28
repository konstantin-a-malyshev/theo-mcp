from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def _generate_test_svg(vb_width: int = 680, vb_height: int = 200) -> str:
    """Generate a simple test SVG with shapes and text — no external deps.

    Uses width="100%" so the image scales to fit the widget, with a fixed
    viewBox of 680×200 as the coordinate space.  Includes role/title/desc
    for accessibility.
    """
    cx, cy = vb_width // 2, vb_height // 2
    r = min(vb_width, vb_height) // 6
    stripe_y = vb_height // 3
    stripe_h = vb_height // 3

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     width="100%" viewBox="0 0 {vb_width} {vb_height}"
     role="img" aria-labelledby="svg-title svg-desc">
  <title id="svg-title">SVG render test</title>
  <desc id="svg-desc">A 680×200 test graphic: red-to-blue gradient background,
    a teal stripe across the middle third, diagonal cross-lines, a circle,
    and a centred label. Used to verify SVG display in MCP clients.</desc>

  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#e63946"/>
      <stop offset="50%"  stop-color="#457b9d"/>
      <stop offset="100%" stop-color="#1d3557"/>
    </linearGradient>
  </defs>

  <!-- background -->
  <rect width="{vb_width}" height="{vb_height}" fill="url(#bg)" rx="10"/>

  <!-- teal stripe — middle third -->
  <rect x="0" y="{stripe_y}" width="{vb_width}" height="{stripe_h}"
        fill="#2a9d8f" opacity="0.6"/>

  <!-- diagonal cross-lines -->
  <line x1="0" y1="0" x2="{vb_width}" y2="{vb_height}"
        stroke="white" stroke-width="1.5" opacity="0.4"/>
  <line x1="{vb_width}" y1="0" x2="0" y2="{vb_height}"
        stroke="white" stroke-width="1.5" opacity="0.4"/>

  <!-- centre circle -->
  <circle cx="{cx}" cy="{cy}" r="{r}"
          fill="none" stroke="white" stroke-width="2.5"/>

  <!-- label -->
  <text x="{cx}" y="{cy + 6}" text-anchor="middle"
        font-family="monospace" font-size="18" fill="white" font-weight="bold">
    SVG test
  </text>
</svg>"""


def register_test_image_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_test_svg() -> str:
        """
        Return a small test SVG as a plain string to verify that this MCP
        client can receive and render inline SVG content.
        The SVG is 200×120 px and contains a gradient background, a green
        stripe, diagonal lines, a circle, and a text label.
        """
        return _generate_test_svg()

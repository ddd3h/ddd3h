#!/usr/bin/env python3
"""Generate the animated SVG assets for the ddd3h GitHub profile README.

Every animation is pure SMIL, so it plays inside GitHub's <img> proxy
(no JavaScript, no external fonts, no external resources).  Output is
deterministic: the RNG is seeded, so re-running produces identical files.

Usage:
    python3 scripts/build_svgs.py            # writes ./assets/*.svg
    python3 scripts/build_svgs.py out_dir    # writes into out_dir
"""
from __future__ import annotations

import math
import os
import random
import sys
import unicodedata
from xml.sax.saxutils import escape

# ----------------------------------------------------------------- palette
BG = "#05070d"
PANEL = "#0d1117"
PANEL2 = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
WHITE = "#f8fafc"
CYAN = "#38bdf8"
VIOLET = "#a78bfa"
GREEN = "#34d399"
ORANGE = "#fb923c"
PINK = "#f472b6"
YELLOW = "#fbbf24"
RED = "#f87171"

MONO = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

SVG_NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'


def fmt(v: float) -> str:
    """Compact float formatting for attribute values."""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg {SVG_NS} width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}">'
    )


def char_adv(ch: str, fs: float) -> float:
    """Advance width on the monospace grid (CJK glyphs are double-width)."""
    wide = unicodedata.east_asian_width(ch) in ("W", "F")
    return fs * (1.0 if wide else 0.6)


class Typer:
    """Lays text on a fixed monospace grid and optionally types it out.

    Each glyph is its own <text> element so that its position does not
    depend on the font the viewer happens to have installed.  Typed
    glyphs start hidden and are revealed with a SMIL <set>.
    """

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.caret: list[tuple[float, float, float]] = []  # (time, x, baseline)

    def mark(self, t: float, x: float, y: float) -> None:
        self.caret.append((t, x, y))

    def text(
        self,
        x: float,
        y: float,
        segs: list[tuple[str, str]],
        fs: float,
        start: float | None = None,
        cps: float = 0.05,
        jitter: float = 0.0,
        rng: random.Random | None = None,
        weight: str | None = None,
        family: str = MONO,
        reveal_at: float | None = None,
    ) -> tuple[float, float | None]:
        """Draw segments [(string, color), ...].

        start=None  -> static text (or revealed all at once at `reveal_at`)
        start=t     -> typed character by character from time t
        Returns (x_end, t_end).
        """
        cx = x
        t = start
        out: list[str] = []
        if t is not None:
            self.mark(t, cx, y)
        weight_attr = f' font-weight="{weight}"' if weight else ""
        for s, color in segs:
            out.append(f'<g font-family="{family}" font-size="{fs}" fill="{color}"{weight_attr}>')
            for ch in s:
                w = char_adv(ch, fs)
                if ch != " ":
                    if t is None:
                        out.append(f'<text x="{fmt(cx)}" y="{fmt(y)}">{escape(ch)}</text>')
                    else:
                        out.append(
                            f'<text x="{fmt(cx)}" y="{fmt(y)}" opacity="0">'
                            f'<set attributeName="opacity" to="1" begin="{fmt(t)}s" fill="freeze"/>'
                            f"{escape(ch)}</text>"
                        )
                cx += w
                if t is not None:
                    dt = cps
                    if rng is not None and jitter:
                        dt += rng.uniform(-jitter, jitter)
                    t += dt
                    self.mark(t, cx, y)
            out.append("</g>")
        body = "".join(out)
        if reveal_at is not None and start is None:
            body = (
                f'<g opacity="0"><set attributeName="opacity" to="1" begin="{fmt(reveal_at)}s" fill="freeze"/>'
                f"{body}</g>"
            )
        self.parts.append(body)
        return cx, t

    def caret_svg(self, w: float, h: float, color: str, blink_dur: float = 1.0) -> str:
        """A caret rect that hops along the recorded typing positions and blinks."""
        if not self.caret:
            return ""
        pts = sorted(self.caret)
        if pts[0][0] > 0:
            pts.insert(0, (0.0, pts[0][1], pts[0][2]))
        total = pts[-1][0]
        xs = ";".join(fmt(x) for _, x, _ in pts)
        ys = ";".join(fmt(y - h * 0.8) for _, _, y in pts)
        kt = ";".join(fmt(t / total) for t, _, _ in pts)
        return (
            f'<rect x="{fmt(pts[0][1])}" y="{fmt(pts[0][2] - h * 0.8)}" width="{fmt(w)}" height="{fmt(h)}" fill="{color}">'
            f'<animate attributeName="x" values="{xs}" keyTimes="{kt}" calcMode="discrete" dur="{fmt(total)}s" fill="freeze"/>'
            f'<animate attributeName="y" values="{ys}" keyTimes="{kt}" calcMode="discrete" dur="{fmt(total)}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="1;1;0;0" dur="{fmt(blink_dur)}s" repeatCount="indefinite"/>'
            f"</rect>"
        )

    def svg(self) -> str:
        return "".join(self.parts)


# ------------------------------------------------------------ shared bits
def starfield(n: int, w: int, h: int, rng: random.Random) -> str:
    out = []
    for _ in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.choice([0.6, 0.7, 0.9, 1.1, 1.4, 1.8])
        o = rng.uniform(0.3, 0.95)
        dur = rng.uniform(1.6, 5.5)
        beg = -rng.uniform(0, 5)
        col = rng.choice(["#ffffff", "#ffffff", "#ffffff", "#e0f2fe", "#ede9fe", "#fef3c7"])
        out.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{r}" fill="{col}" opacity="{fmt(o)}">'
            f'<animate attributeName="opacity" values="{fmt(o)};0.05;{fmt(o)}" dur="{fmt(dur)}s" '
            f'begin="{fmt(beg)}s" repeatCount="indefinite"/></circle>'
        )
    return "".join(out)


def shooting_star(x0: float, y0: float, x1: float, y1: float, dur: float, begin: float) -> str:
    return (
        f'<g opacity="0">'
        f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;0.05;0.16;1" dur="{fmt(dur)}s" begin="{fmt(begin)}s" repeatCount="indefinite"/>'
        f'<animateTransform attributeName="transform" type="translate" values="{fmt(x0)} {fmt(y0)};{fmt(x1)} {fmt(y1)};{fmt(x1)} {fmt(y1)}" keyTimes="0;0.16;1" dur="{fmt(dur)}s" begin="{fmt(begin)}s" repeatCount="indefinite"/>'
        f'<line x1="0" y1="0" x2="-90" y2="30" stroke="url(#shoot)" stroke-width="2" stroke-linecap="round"/>'
        f'<circle r="1.8" fill="#fff"/>'
        f"</g>"
    )


def signal_bars(x: float, y: float, color: str, n: int = 5, step: float = 0.18) -> str:
    """Little cell-signal bars that light up in sequence."""
    out = []
    for i in range(n):
        h = 4 + i * 3
        out.append(
            f'<rect x="{fmt(x + i * 7)}" y="{fmt(y - h)}" width="4" height="{h}" rx="1" fill="{color}" opacity="0.25">'
            f'<animate attributeName="opacity" values="0.25;1;1;0.25" keyTimes="0;0.2;0.6;1" dur="2.2s" begin="{fmt(i * step)}s" repeatCount="indefinite"/>'
            f"</rect>"
        )
    return "".join(out)


def rocket(scale: float = 1.0) -> str:
    """Rocket pointing up, origin at the flame root (0,0); body extends upward."""
    return (
        f'<g transform="scale({fmt(scale)})">'
        # exhaust flame (scaled from the origin so it flickers from the nozzle)
        f'<g><animateTransform attributeName="transform" type="scale" values="1 1;1 1.45;1 0.8;1 1.3;1 0.95;1 1" dur="0.42s" repeatCount="indefinite"/>'
        f'<path d="M-6,0 C-7,10 -3,18 0,26 C3,18 7,10 6,0 Z" fill="url(#flame)"/>'
        f'<path d="M-3,0 C-3.5,6 -1.5,10 0,14 C1.5,10 3.5,6 3,0 Z" fill="#fff" opacity="0.9"/>'
        f"</g>"
        # nozzle
        f'<path d="M-7,0 L7,0 L5,-5 L-5,-5 Z" fill="#475569"/>'
        # body
        f'<path d="M0,-52 C11,-40 12,-18 10,-5 L-10,-5 C-12,-18 -11,-40 0,-52 Z" fill="#e2e8f0"/>'
        f'<path d="M0,-52 C5,-40 6,-18 5,-5 L0,-5 Z" fill="#cbd5e1"/>'
        # nose cone
        f'<path d="M0,-52 C6,-46 9,-40 10,-34 L-10,-34 C-9,-40 -6,-46 0,-52 Z" fill="{RED}"/>'
        # window
        f'<circle cy="-24" r="4" fill="{CYAN}" stroke="#94a3b8" stroke-width="1.2"/>'
        # fins
        f'<path d="M-10,-16 L-19,-2 L-10,-5 Z" fill="{RED}"/>'
        f'<path d="M10,-16 L19,-2 L10,-5 Z" fill="{RED}"/>'
        f"</g>"
    )


# ------------------------------------------------------------------ header
def build_header() -> str:
    W, H = 1200, 420
    rng = random.Random(20260603)
    px, py = 940, 215  # planet centre

    o = [svg_open(W, H, "Daisuke Nishihama - Astrophysicist, Aerospace & Systems Engineer, CTO")]
    o.append(
        "<defs>"
        f'<radialGradient id="bg" cx="72%" cy="38%" r="85%"><stop offset="0" stop-color="#101a33"/><stop offset="0.55" stop-color="#080c18"/><stop offset="1" stop-color="{BG}"/></radialGradient>'
        f'<linearGradient id="name" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="0.6" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>'
        f'<radialGradient id="planet" cx="34%" cy="32%" r="78%"><stop offset="0" stop-color="#8b7cf8"/><stop offset="0.45" stop-color="#3b2f8f"/><stop offset="1" stop-color="#0b0a24"/></radialGradient>'
        f'<linearGradient id="ring" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}" stop-opacity="0.05"/><stop offset="0.5" stop-color="{CYAN}" stop-opacity="0.9"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0.05"/></linearGradient>'
        f'<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="{YELLOW}"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="shoot" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>'
        '<filter id="glow" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"/></filter>'
        '<filter id="halo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>'
        f'<clipPath id="round"><rect width="{W}" height="{H}" rx="18"/></clipPath>'
        f'<clipPath id="ringfront"><rect x="{px - 220}" y="{py}" width="440" height="200" transform="rotate(-18 {px} {py})"/></clipPath>'
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#ffffff" opacity="0.025"/></pattern>'
        "</defs>"
    )
    o.append('<g clip-path="url(#round)">')
    o.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # nebulae
    o.append(f'<ellipse cx="300" cy="80" rx="260" ry="110" fill="{VIOLET}" opacity="0.10" filter="url(#soft)"/>')
    o.append(f'<ellipse cx="1050" cy="380" rx="300" ry="120" fill="{CYAN}" opacity="0.08" filter="url(#soft)"/>')
    o.append(starfield(150, W, H, rng))
    o.append(shooting_star(520, 30, 760, 120, 9.0, 1.5))
    o.append(shooting_star(1100, 60, 1240, 150, 13.0, 6.0))

    # orbit guides
    for rx, ry, op in ((215, 62, 0.35), (300, 90, 0.15)):
        o.append(
            f'<ellipse cx="{px}" cy="{py}" rx="{rx}" ry="{ry}" fill="none" stroke="{CYAN}" stroke-opacity="{op}" '
            f'stroke-width="1" stroke-dasharray="3 6" transform="rotate(-18 {px} {py})"/>'
        )
    # planet + rings
    o.append(f'<circle cx="{px}" cy="{py}" r="112" fill="{VIOLET}" opacity="0.25" filter="url(#halo)"/>')
    o.append(f'<ellipse cx="{px}" cy="{py}" rx="175" ry="40" fill="none" stroke="url(#ring)" stroke-width="10" transform="rotate(-18 {px} {py})"/>')
    o.append(f'<circle cx="{px}" cy="{py}" r="95" fill="url(#planet)"/>')
    # planet surface bands
    o.append(
        f'<g clip-path="url(#planetclip)">'
        f'<clipPath id="planetclip"><circle cx="{px}" cy="{py}" r="95"/></clipPath>'
        f'<ellipse cx="{px - 20}" cy="{py + 25}" rx="120" ry="14" fill="#c4b5fd" opacity="0.12" transform="rotate(-12 {px} {py})"/>'
        f'<ellipse cx="{px + 10}" cy="{py - 30}" rx="120" ry="9" fill="#c4b5fd" opacity="0.10" transform="rotate(-12 {px} {py})"/>'
        f'<ellipse cx="{px}" cy="{py + 60}" rx="130" ry="12" fill="#000" opacity="0.25" transform="rotate(-12 {px} {py})"/>'
        f"</g>"
    )
    o.append(f'<g clip-path="url(#ringfront)"><ellipse cx="{px}" cy="{py}" rx="175" ry="40" fill="none" stroke="url(#ring)" stroke-width="10" transform="rotate(-18 {px} {py})"/></g>')

    # satellite on the inner orbit
    rx, ry = 215, 62
    path = f"M {px + rx},{py} A {rx},{ry} 0 1 1 {px - rx},{py} A {rx},{ry} 0 1 1 {px + rx},{py}"
    o.append(
        f'<g transform="rotate(-18 {px} {py})"><g>'
        f'<animateMotion dur="18s" repeatCount="indefinite" rotate="auto" path="{path}"/>'
        f'<circle r="5" fill="none" stroke="{CYAN}" stroke-width="1.2"><animate attributeName="r" values="5;40" dur="2.4s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.9;0" dur="2.4s" repeatCount="indefinite"/></circle>'
        f'<circle r="5" fill="none" stroke="{CYAN}" stroke-width="1.2"><animate attributeName="r" values="5;40" dur="2.4s" begin="-1.2s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.9;0" dur="2.4s" begin="-1.2s" repeatCount="indefinite"/></circle>'
        f'<rect x="-30" y="-3.5" width="20" height="7" fill="#2563eb" stroke="#93c5fd" stroke-width="0.8"/>'
        f'<rect x="10" y="-3.5" width="20" height="7" fill="#2563eb" stroke="#93c5fd" stroke-width="0.8"/>'
        f'<path d="M-25,-3.5 V3.5 M-20,-3.5 V3.5 M-15,-3.5 V3.5 M15,-3.5 V3.5 M20,-3.5 V3.5 M25,-3.5 V3.5" stroke="#93c5fd" stroke-width="0.6" opacity="0.7"/>'
        f'<rect x="-8" y="-6" width="16" height="12" rx="2" fill="#e2e8f0" stroke="#94a3b8" stroke-width="0.8"/>'
        f'<circle cy="-9" r="3.5" fill="#cbd5e1" stroke="#64748b" stroke-width="0.8"/>'
        f'<line x1="0" y1="-9" x2="0" y2="-14" stroke="#94a3b8" stroke-width="1"/>'
        f'<circle cy="8" r="1.6" fill="{RED}"><animate attributeName="opacity" values="1;0.1;1" dur="0.9s" repeatCount="indefinite"/></circle>'
        f"</g></g>"
    )

    # ground station, bottom right
    gx, gy = 1128, 372
    o.append(
        f'<g transform="translate({gx} {gy})">'
        f'<rect x="-14" y="14" width="28" height="4" rx="1" fill="#475569"/>'
        f'<rect x="-2" y="-2" width="4" height="16" fill="#64748b"/>'
        f'<path d="M-18,-6 Q0,-30 18,-6 Z" fill="#94a3b8"/>'
        f'<line x1="0" y1="-14" x2="0" y2="-26" stroke="#cbd5e1" stroke-width="1.2"/>'
        f'<circle cy="-26" r="1.8" fill="{CYAN}"/>'
        + "".join(
            f'<path d="M {fmt(-r * 0.87)},{fmt(-26 - r * 0.5)} A {r},{r} 0 0 1 {fmt(r * 0.87)},{fmt(-26 - r * 0.5)}" fill="none" stroke="{CYAN}" stroke-width="1.4" opacity="0.15">'
            f'<animate attributeName="opacity" values="0.15;1;0.15" dur="1.8s" begin="{fmt(i * 0.45)}s" repeatCount="indefinite"/></path>'
            for i, r in enumerate((10, 18, 26))
        )
        + "</g>"
    )

    # rocket rising between the text block and the planet
    o.append(
        f'<g><animateTransform attributeName="transform" type="translate" values="812 500;790 -120" dur="9s" begin="0.8s" repeatCount="indefinite"/>'
        f'<g transform="rotate(4)">{rocket(0.9)}</g></g>'
    )

    # ---- text block --------------------------------------------------
    ty = Typer()
    # status pill
    o.append(
        f'<g transform="translate(60 52)">'
        f'<rect x="0" y="-14" width="170" height="24" rx="12" fill="{PANEL2}" stroke="{BORDER}"/>'
        f'<circle cx="16" cy="-2" r="4" fill="{GREEN}"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<circle cx="16" cy="-2" r="4" fill="none" stroke="{GREEN}"><animate attributeName="r" values="4;11" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.8;0" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="30" y="2" font-family="{MONO}" font-size="12" fill="{GREEN}" letter-spacing="1">SYSTEMS NOMINAL</text>'
        f"</g>"
    )
    o.append(
        f'<text x="{W - 60}" y="56" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">// github.com/ddd3h</text>'
    )
    # name
    o.append(
        f'<g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.9s" begin="0.2s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" values="0 22;0 0" dur="0.9s" begin="0.2s" fill="freeze"/>'
        f'<text x="58" y="182" font-family="{SANS}" font-size="56" font-weight="800" letter-spacing="1" fill="url(#name)" filter="url(#glow)">DAISUKE NISHIHAMA</text>'
        f'<text x="60" y="222" font-family="{SANS}" font-size="20" fill="{MUTED}">@ddd3h  ·  西濱 大将  ·  Osaka, Japan</text>'
        f"</g>"
    )
    # typed subtitle
    ty.text(
        60, 272,
        [("Astrophysicist", CYAN), ("  ·  ", MUTED), ("Aerospace & Systems Engineer", WHITE), ("  ·  ", MUTED), ("CTO", VIOLET)],
        fs=20, start=1.3, cps=0.045, jitter=0.015, rng=rng,
    )
    o.append(ty.svg())
    o.append(ty.caret_svg(11, 22, CYAN))
    # meta line
    o.append(
        f'<g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.8s" begin="4.2s" fill="freeze"/>'
        f'<text x="60" y="312" font-family="{MONO}" font-size="13" fill="{MUTED}">'
        f'<tspan fill="{GREEN}">▸</tspan> CTO &amp; Rocket Development Lead @ Chart Inc.   '
        f'<tspan fill="{GREEN}">▸</tspan> Ph.D. Astrophysics @ The University of Osaka</text>'
        f'<text x="60" y="336" font-family="{MONO}" font-size="13" fill="{MUTED}">'
        f'<tspan fill="{GREEN}">▸</tspan> rockets · satellites · space networks · HPC simulation · full-stack · security</text>'
        f"</g>"
    )
    # signal bars + coordinates
    o.append(f'<text x="60" y="376" font-family="{MONO}" font-size="11" fill="{MUTED}" letter-spacing="1">UPLINK</text>')
    o.append(signal_bars(118, 377, CYAN))
    o.append(f'<text x="166" y="376" font-family="{MONO}" font-size="11" fill="{MUTED}">34.69°N 135.50°E  ·  UTC+9</text>')

    o.append(f'<rect width="{W}" height="{H}" fill="url(#scan)"/>')
    o.append("</g>")
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{BORDER}"/>')
    o.append("</svg>")
    return "".join(o)


# ---------------------------------------------------------------- terminal
def build_terminal() -> str:
    W = 900
    fs, lh = 15, 24
    x0, top = 26, 42
    rng = random.Random(3)
    ty = Typer()

    prompt = [("daisuke", GREEN), ("@", MUTED), ("ddd3h", CYAN), (":", MUTED), ("~", VIOLET), ("$ ", TEXT)]
    script: list[tuple[str, list[list[tuple[str, str]]]]] = [
        ("whoami", [
            [("Daisuke Nishihama", WHITE), ("  —  ", MUTED), ("CTO & Rocket Development Lead ", TEXT), ("@ Chart Inc.", CYAN)],
            [("                   ", TEXT), ("Ph.D. student · Astrophysics ", TEXT), ("@ The University of Osaka", CYAN)],
        ]),
        ("cat ~/.mission", [
            [("Build things that ", TEXT), ("fly", ORANGE), (", ", TEXT), ("compute", GREEN), (", and ", TEXT), ("talk across space", CYAN), (".", TEXT)],
        ]),
        ("ls ~/domains", [
            [("aerospace/", CYAN), ("   ", TEXT), ("space-comms/", CYAN), ("   ", TEXT), ("defense-systems/", CYAN), ("   ", TEXT), ("hpc-simulation/", CYAN)],
            [("fullstack/", CYAN), ("   ", TEXT), ("security/", CYAN), ("   ", TEXT), ("data-ml/", CYAN), ("   ", TEXT), ("clustering/", CYAN), ("   ", TEXT), ("fluid-dynamics/", CYAN)],
        ]),
        ("cat ~/.langs", [
            [("C", YELLOW), ("  ·  ", MUTED), ("C++", YELLOW), ("  ·  ", MUTED), ("Rust", ORANGE), ("  ·  ", MUTED), ("Python", GREEN),
             ("  ·  ", MUTED), ("Julia", VIOLET), ("  ·  ", MUTED), ("TypeScript", CYAN), ("  ·  ", MUTED), ("Next.js", WHITE)],
        ]),
        ("uptime", [
            [("shipping code since 2018", TEXT), ("  ·  ", MUTED), ("40+ public repos", TEXT), ("  ·  ", MUTED), ("load avg: ", MUTED), ("rockets, sims, satellites", PINK)],
        ]),
    ]

    y = top + lh
    t = 0.7
    lines = 0
    for cmd, outputs in script:
        xe, _ = ty.text(x0, y, prompt, fs, reveal_at=t)
        _, t = ty.text(xe, y, [(cmd, WHITE)], fs, start=t, cps=0.055, jitter=0.02, rng=rng)
        t += 0.35
        y += lh
        lines += 1
        for seg in outputs:
            ty.text(x0, y, seg, fs, reveal_at=t)
            t += 0.12
            ty.mark(t, x0, y + lh)
            y += lh
            lines += 1
        t += 0.55
    xe, _ = ty.text(x0, y, prompt, fs, reveal_at=t)
    ty.mark(t, xe, y)
    lines += 1
    H = top + lines * lh + 26

    o = [svg_open(W, H, "Terminal session: whoami, mission, domains, languages, uptime")]
    o.append(
        "<defs>"
        f'<clipPath id="win"><rect width="{W}" height="{H}" rx="14"/></clipPath>'
        f'<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c2129"/><stop offset="1" stop-color="{PANEL2}"/></linearGradient>'
        "</defs>"
    )
    o.append('<g clip-path="url(#win)">')
    o.append(f'<rect width="{W}" height="{H}" fill="{PANEL}"/>')
    o.append(f'<rect width="{W}" height="{top - 6}" fill="url(#bar)"/>')
    o.append(f'<line x1="0" y1="{top - 6}" x2="{W}" y2="{top - 6}" stroke="{BORDER}"/>')
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        o.append(f'<circle cx="{20 + i * 20}" cy="{(top - 6) / 2}" r="6" fill="{c}"/>')
    o.append(
        f'<text x="{W / 2}" y="{(top - 6) / 2 + 4}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{MUTED}">daisuke@ddd3h: ~ — zsh</text>'
    )
    o.append(ty.svg())
    o.append(ty.caret_svg(9, 17, TEXT))
    o.append("</g>")
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{BORDER}"/>')
    o.append("</svg>")
    return "".join(o)


# ----------------------------------------------------------------- domains
def icon_rocket(accent: str) -> str:
    return (
        f'<g transform="translate(32 44)">'
        f'<animateTransform attributeName="transform" type="translate" values="32 44;32 40;32 44" dur="2.4s" repeatCount="indefinite"/>'
        f'{rocket(0.72)}</g>'
    )


def icon_antenna(accent: str) -> str:
    arcs = []
    for i, r in enumerate((11, 18, 25)):
        a0, a1 = math.radians(-135), math.radians(-45)
        x0, y0 = r * math.cos(a0), r * math.sin(a0)
        x1, y1 = r * math.cos(a1), r * math.sin(a1)
        arcs.append(
            f'<path d="M {fmt(x0)},{fmt(y0)} A {r},{r} 0 0 1 {fmt(x1)},{fmt(y1)}" fill="none" stroke="{accent}" stroke-width="2" stroke-linecap="round" opacity="0.15">'
            f'<animate attributeName="opacity" values="0.15;1;0.15" dur="1.8s" begin="{fmt(i * 0.4)}s" repeatCount="indefinite"/></path>'
        )
    return (
        f'<g transform="translate(32 34)">'
        f'<rect x="-13" y="20" width="26" height="4" rx="1" fill="#475569"/>'
        f'<rect x="-2.5" y="4" width="5" height="17" fill="#64748b"/>'
        f'<path d="M-17,2 Q0,-22 17,2 Z" fill="#94a3b8"/>'
        f'<line x1="0" y1="-8" x2="0" y2="-18" stroke="#e2e8f0" stroke-width="1.5"/>'
        f'<circle cy="-18" r="2" fill="{accent}"/>'
        f'<g transform="translate(0 -18)">{"".join(arcs)}</g>'
        f"</g>"
    )


def icon_shield(accent: str) -> str:
    shape = "M32,8 L52,16 C52,36 44,50 32,56 C20,50 12,36 12,16 Z"
    return (
        f'<clipPath id="shieldclip"><path d="{shape}"/></clipPath>'
        f'<path d="{shape}" fill="#1e293b" stroke="{accent}" stroke-width="2"/>'
        f'<g clip-path="url(#shieldclip)">'
        f'<rect x="12" y="8" width="40" height="5" fill="{accent}" opacity="0.7"><animate attributeName="y" values="4;56" dur="2.2s" repeatCount="indefinite"/></rect>'
        f'<rect x="12" y="8" width="40" height="14" fill="{accent}" opacity="0.18"><animate attributeName="y" values="-10;56" dur="2.2s" repeatCount="indefinite"/></rect>'
        f"</g>"
        f'<polyline points="22,32 29,39 43,25" fill="none" stroke="{GREEN}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="40" stroke-dashoffset="40">'
        f'<animate attributeName="stroke-dashoffset" values="40;0;0;40" keyTimes="0;0.3;0.8;1" dur="3.2s" repeatCount="indefinite"/></polyline>'
    )


def icon_cluster(accent: str) -> str:
    pts = [(16 + 16 * c, 16 + 16 * r) for r in range(3) for c in range(3)]
    o = []
    for r in range(3):
        for c in range(3):
            x, y = 16 + 16 * c, 16 + 16 * r
            if c < 2:
                o.append(f'<line x1="{x}" y1="{y}" x2="{x + 16}" y2="{y}" stroke="{accent}" stroke-width="1.2" opacity="0.35"/>')
            if r < 2:
                o.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + 16}" stroke="{accent}" stroke-width="1.2" opacity="0.35"/>')
    for i, (x, y) in enumerate(pts):
        r, c = divmod(i, 3)
        o.append(
            f'<circle cx="{x}" cy="{y}" r="4.5" fill="{PANEL2}" stroke="{accent}" stroke-width="1.5">'
            f'<animate attributeName="fill" values="{PANEL2};{accent};{PANEL2}" dur="1.8s" begin="{fmt((r + c) * 0.18)}s" repeatCount="indefinite"/></circle>'
        )
    return "".join(o)


def icon_bars(accent: str) -> str:
    o = []
    base = 52
    for i, h in enumerate((16, 28, 22, 40, 32)):
        x = 9 + i * 10
        col = accent if i % 2 == 0 else VIOLET
        o.append(
            f'<rect x="{x}" y="{base - h}" width="7" height="{h}" rx="1.5" fill="{col}">'
            f'<animate attributeName="height" values="0;{h};{h};0" keyTimes="0;0.3;0.8;1" dur="3.4s" begin="{fmt(i * 0.14)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{base};{base - h};{base - h};{base}" keyTimes="0;0.3;0.8;1" dur="3.4s" begin="{fmt(i * 0.14)}s" repeatCount="indefinite"/>'
            f"</rect>"
        )
    o.append(f'<line x1="6" y1="{base + 1}" x2="58" y2="{base + 1}" stroke="{MUTED}" stroke-width="1"/>')
    return "".join(o)


def icon_window(accent: str) -> str:
    o = [
        f'<rect x="8" y="10" width="48" height="44" rx="5" fill="{PANEL2}" stroke="{BORDER}" stroke-width="1.5"/>',
        f'<line x1="8" y1="20" x2="56" y2="20" stroke="{BORDER}" stroke-width="1"/>',
        f'<circle cx="14" cy="15" r="1.8" fill="{RED}"/><circle cx="19.5" cy="15" r="1.8" fill="{YELLOW}"/><circle cx="25" cy="15" r="1.8" fill="{GREEN}"/>',
    ]
    for i, (w, col, indent) in enumerate(((24, accent, 0), (32, VIOLET, 6), (18, GREEN, 6), (28, CYAN, 0))):
        o.append(
            f'<rect x="{13 + indent}" y="{26 + i * 7}" width="{w}" height="3.5" rx="1.5" fill="{col}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.85;1" dur="3.8s" begin="{fmt(i * 0.35)}s" repeatCount="indefinite"/></rect>'
        )
    o.append(
        f'<g transform="translate(46 44)">'
        f'<rect x="-6" y="-2" width="12" height="9" rx="2" fill="{PANEL}" stroke="{accent}" stroke-width="1.5"/>'
        f'<path d="M-3.5,-2 V-5 A3.5,3.5 0 0 1 3.5,-5 V-2" fill="none" stroke="{accent}" stroke-width="1.5"/>'
        f'<circle cy="2.5" r="1.2" fill="{accent}"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>'
        f"</g>"
    )
    return "".join(o)


DOMAINS = [
    dict(title="Rockets & Avionics", tag="$ launch --hybrid --cansat", accent=ORANGE, icon=icon_rocket,
         desc=["Hybrid rockets, CanSats & flight computers.",
               "Telemetry, recovery systems and 6-DOF flight",
               "simulation from launch pad to touchdown."],
         pills=["C/C++", "Avionics", "6-DOF Sim", "Recovery"]),
    dict(title="Space Comms & Networks", tag="$ uplink --lora --sat-net", accent=CYAN, icon=icon_antenna,
         desc=["LoRa image links from the stratosphere,",
               "ground-station software, satellite & space",
               "network protocol design."],
         pills=["LoRa", "Telemetry", "Satellite", "Protocols"]),
    dict(title="Defense-Grade Systems", tag="$ harden --secure --resilient", accent=VIOLET, icon=icon_shield,
         desc=["Secure communication software and resilient,",
               "mission-critical systems built to keep",
               "working when everything else fails."],
         pills=["Secure Comms", "Fault-Tolerant", "Real-time"]),
    dict(title="HPC & Simulation", tag="$ mpirun -np 4096 ./universe", accent=GREEN, icon=icon_cluster,
         desc=["Cosmological simulations (CROCODILE), N-body",
               "& CFD solvers, cluster computing tuned for",
               "supercomputers."],
         pills=["MPI/HPC", "N-body", "CFD", "HDF5", "Julia"]),
    dict(title="Data Analysis & ML", tag="$ python analyze.py --hdf5", accent=PINK, icon=icon_bars,
         desc=["HDF5 pipelines, ML (LightGBM · Optuna ·",
               "MLflow) and scientific analysis turned into",
               "clear, publishable visuals."],
         pills=["NumPy", "LightGBM", "Optuna", "MLflow"]),
    dict(title="Full-Stack Systems", tag="$ pnpm dev && cargo run", accent=YELLOW, icon=icon_window,
         desc=["Next.js, Rust, Tauri, FastAPI — frontend to",
               "backend, shipped with a security mindset",
               "and an eye for clean architecture."],
         pills=["Next.js", "Rust", "Tauri", "FastAPI"]),
]


def build_domains() -> str:
    W = 1200
    cw, ch, gap, m = 372, 250, 20, 22
    rows = 2
    H = m * 2 + rows * ch + (rows - 1) * gap
    o = [svg_open(W, H, "Mission domains: rockets & avionics, space comms, defense-grade systems, HPC & simulation, data & ML, full-stack")]
    o.append(
        "<defs>"
        f'<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="{YELLOW}"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>'
        "</defs>"
    )
    o.append(f'<rect width="{W}" height="{H}" fill="none"/>')
    for i, d in enumerate(DOMAINS):
        r, c = divmod(i, 3)
        x = m + c * (cw + gap)
        y = m + r * (ch + gap)
        acc = d["accent"]
        o.append(f'<g transform="translate({x} {y})">')
        o.append(
            f'<rect width="{cw}" height="{ch}" rx="14" fill="{PANEL}" stroke="{BORDER}" stroke-width="1">'
            f'<animate attributeName="stroke" values="{BORDER};{acc};{BORDER}" keyTimes="0;0.5;1" dur="1.6s" begin="{fmt(0.6 + i * 1.6)}s;{fmt(0.6 + i * 1.6 + 9.6)}s" repeatCount="indefinite"/>'
            f"</rect>"
        )
        # accent top line
        o.append(f'<rect x="20" y="0" width="60" height="3" rx="1.5" fill="{acc}"/>')
        # icon box
        o.append(f'<rect x="22" y="24" width="64" height="64" rx="12" fill="{PANEL2}" stroke="{acc}" stroke-opacity="0.45"/>')
        o.append(f'<g transform="translate(22 24)">{d["icon"](acc)}</g>')
        o.append(f'<text x="104" y="50" font-family="{SANS}" font-size="17" font-weight="700" fill="{WHITE}">{escape(d["title"])}</text>')
        o.append(f'<text x="104" y="72" font-family="{MONO}" font-size="12" fill="{acc}">{escape(d["tag"])}</text>')
        for j, line in enumerate(d["desc"]):
            assert len(line) <= 46, line
            o.append(f'<text x="22" y="{118 + j * 20}" font-family="{SANS}" font-size="13.5" fill="{TEXT}">{escape(line)}</text>')
        px = 22
        for p in d["pills"]:
            pw = len(p) * 6.9 + 18
            o.append(
                f'<rect x="{fmt(px)}" y="196" width="{fmt(pw)}" height="24" rx="12" fill="{PANEL2}" stroke="{acc}" stroke-opacity="0.35"/>'
                f'<text x="{fmt(px + pw / 2)}" y="212" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="{acc}">{escape(p)}</text>'
            )
            px += pw + 8
        assert px - 8 <= cw - 22, (d["title"], px)
        o.append("</g>")
    o.append("</svg>")
    return "".join(o)


# ----------------------------------------------------------------- divider
def build_divider() -> str:
    W, H = 1200, 44
    period = 120
    amp = 9
    pts = []
    for x in range(0, W + 2 * period + 1, 8):
        y = H / 2 + amp * math.sin(2 * math.pi * x / period)
        pts.append(f"{'M' if not pts else 'L'} {x},{fmt(y)}")
    path = " ".join(pts)
    mpath = " ".join(
        f"{'M' if i == 0 else 'L'} {x},{fmt(H / 2 + amp * math.sin(2 * math.pi * x / period))}"
        for i, x in enumerate(range(0, W + 1, 8))
    )
    o = [svg_open(W, H, "signal divider")]
    o.append(
        "<defs>"
        f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.15" stop-color="#fff"/><stop offset="0.85" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="wave" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="0.5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>'
        f'<mask id="fade"><rect width="{W}" height="{H}" fill="url(#edge)"/></mask>'
        "</defs>"
    )
    o.append('<g mask="url(#fade)">')
    o.append(f'<line x1="0" y1="{H / 2}" x2="{W}" y2="{H / 2}" stroke="{BORDER}" stroke-dasharray="2 6"/>')
    o.append(
        f'<g><animateTransform attributeName="transform" type="translate" values="0 0;-{period * 2} 0" dur="3s" repeatCount="indefinite"/>'
        f'<path d="{path}" fill="none" stroke="url(#wave)" stroke-width="2" stroke-linecap="round" opacity="0.9"/>'
        f'<path d="{path}" fill="none" stroke="url(#wave)" stroke-width="6" stroke-linecap="round" opacity="0.15"/>'
        f"</g>"
    )
    for col, dur, beg in ((CYAN, 6, 0), (PINK, 6, 3)):
        o.append(
            f'<circle r="3.5" fill="{col}"><animateMotion dur="{dur}s" begin="{beg}s" repeatCount="indefinite" path="{mpath}"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.9;1" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></circle>'
        )
    o.append("</g>")
    o.append("</svg>")
    return "".join(o)


# ------------------------------------------------------------------ footer
def build_footer() -> str:
    W, H = 1200, 150
    rng = random.Random(1961)
    o = [svg_open(W, H, "End of transmission")]
    o.append(
        "<defs>"
        f'<linearGradient id="fbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="#0f172a"/></linearGradient>'
        f'<linearGradient id="fline" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset="0.5" stop-color="{CYAN}"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="{YELLOW}"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="fround"><rect width="{W}" height="{H}" rx="18"/></clipPath>'
        "</defs>"
    )
    o.append('<g clip-path="url(#fround)">')
    o.append(f'<rect width="{W}" height="{H}" fill="url(#fbg)"/>')
    o.append(starfield(70, W, H, rng))
    o.append(f'<rect x="0" y="0" width="{W}" height="2" fill="url(#fline)"/>')
    # tiny rocket crossing
    o.append(
        f'<g><animateTransform attributeName="transform" type="translate" values="-60 120;1260 20" dur="14s" begin="2s" repeatCount="indefinite"/>'
        f'<g transform="rotate(80)">{rocket(0.45)}</g></g>'
    )
    ty = Typer()
    ty.text(0, 0, [], 1)  # no-op to keep structure simple
    o.append(
        f'<text x="{W / 2}" y="66" text-anchor="middle" font-family="{MONO}" font-size="15" fill="{MUTED}" letter-spacing="4" opacity="0">'
        f'<animate attributeName="opacity" values="0;1" dur="1.2s" begin="0.3s" fill="freeze"/>// END OF TRANSMISSION</text>'
    )
    o.append(
        f'<text x="{W / 2}" y="98" text-anchor="middle" font-family="{SANS}" font-size="15" fill="{TEXT}" opacity="0">'
        f'<animate attributeName="opacity" values="0;1" dur="1.2s" begin="1.1s" fill="freeze"/>Per aspera ad astra — thanks for stopping by.</text>'
    )
    o.append(f'<text x="60" y="{H - 26}" font-family="{MONO}" font-size="11" fill="{MUTED}" letter-spacing="1">UPLINK</text>')
    o.append(signal_bars(118, H - 25, CYAN))
    o.append(
        f'<text x="{W - 60}" y="{H - 26}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">ddd3h.com  ·  Osaka, JP  ·  UTC+9</text>'
    )
    o.append("</g>")
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{BORDER}"/>')
    o.append("</svg>")
    return "".join(o)


# -------------------------------------------------------------------- main
def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)
    files = {
        "header.svg": build_header(),
        "terminal.svg": build_terminal(),
        "domains.svg": build_domains(),
        "divider.svg": build_divider(),
        "footer.svg": build_footer(),
    }
    for name, body in files.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"wrote {path} ({len(body.encode('utf-8')) // 1024} KB)")


if __name__ == "__main__":
    main()

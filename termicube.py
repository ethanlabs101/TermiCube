#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  RUBIK  --  a 3D Rubik's Cube that spins forever and quietly solves itself
================================================================================
A real 3x3x3 cube state (54 stickers), rendered in 3D with perspective,
lighting, backface culling and depth sorting -- no curses, no dependencies
beyond the Python 3 standard library.

It scrambles itself with a random sequence of quarter turns, then plays that
exact sequence backwards (each move inverted) to solve it -- which is
mathematically guaranteed to return to a solved cube, so it always finishes
clean. The whole cube tumbles continuously in 3D the entire time.

Cycle: scramble (quick) -> pause -> solve (slow, eased turns) -> hold solved
-> new scramble -> repeat, forever.

Run it:  python3 termicube.py
Quit:    Q or Esc
Extras:  +/- = speed
================================================================================
"""

from __future__ import annotations

import math
import os
import random
import select
import signal
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import termios
    import tty
except ImportError:  # pragma: no cover
    termios = None
    tty = None

ESC = "\x1b"
ENTER_ALT = f"{ESC}[?1049h"
EXIT_ALT = f"{ESC}[?1049l"
HIDE_CUR = f"{ESC}[?25l"
SHOW_CUR = f"{ESC}[?25h"
CLEAR = f"{ESC}[2J"
HOME = f"{ESC}[H"
RESET = f"{ESC}[0m"
EOL = f"{ESC}[K"

RGB = Tuple[int, int, int]
Vec3 = Tuple[float, float, float]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class TerminalSession:
    def __enter__(self):
        if termios is None or tty is None or not sys.stdout.isatty():
            raise RuntimeError(
                "Run this in a real POSIX terminal (Linux/macOS/BSD/WSL)."
            )
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        sys.stdout.write(ENTER_ALT + HIDE_CUR + CLEAR)
        sys.stdout.flush()
        self.resized = False

        if hasattr(signal, "SIGWINCH"):
            signal.signal(
                signal.SIGWINCH,
                lambda *_: setattr(self, "resized", True),
            )

        return self

    def poll_resize(self) -> bool:
        if self.resized:
            self.resized = False
            return True
        return False

    def __exit__(self, *exc):
        try:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
        finally:
            sys.stdout.write(SHOW_CUR + RESET + EXIT_ALT)
            sys.stdout.flush()

        return False


def read_key(timeout: float = 0.0) -> Optional[str]:
    if not select.select([sys.stdin], [], [], timeout)[0]:
        return None

    ch = sys.stdin.read(1)

    if ch == "\x1b":
        if select.select([sys.stdin], [], [], 0.001)[0]:
            sys.stdin.read(1)

            if select.select([sys.stdin], [], [], 0.001)[0]:
                sys.stdin.read(1)

        return "esc"

    return ch


FACE_NORMAL: Dict[str, Vec3] = {
    "U": (0, 1, 0),
    "D": (0, -1, 0),
    "F": (0, 0, 1),
    "B": (0, 0, -1),
    "R": (1, 0, 0),
    "L": (-1, 0, 0),
}

FACE_RIGHT: Dict[str, Vec3] = {
    "F": (1, 0, 0),
    "B": (-1, 0, 0),
    "R": (0, 0, -1),
    "L": (0, 0, 1),
    "U": (1, 0, 0),
    "D": (1, 0, 0),
}

FACE_UP: Dict[str, Vec3] = {
    "F": (0, 1, 0),
    "B": (0, 1, 0),
    "R": (0, 1, 0),
    "L": (0, 1, 0),
    "U": (0, 0, -1),
    "D": (0, 0, 1),
}

FACE_COLOR: Dict[str, RGB] = {
    "U": (245, 245, 245),
    "D": (255, 209, 0),
    "F": (0, 158, 96),
    "B": (0, 81, 186),
    "R": (196, 30, 45),
    "L": (255, 89, 0),
}

MOVE_AXIS: Dict[str, Tuple[str, int]] = {
    "U": ("y", 1),
    "D": ("y", -1),
    "F": ("z", 1),
    "B": ("z", -1),
    "R": ("x", 1),
    "L": ("x", -1),
}

SPACING = 0.66
STICKER_HALF = 0.27
AXIS_IDX = {"x": 0, "y": 1, "z": 2}


def v_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rot_axis(p: Vec3, axis: str, theta: float) -> Vec3:
    x, y, z = p
    c, s = math.cos(theta), math.sin(theta)

    if axis == "x":
        return (x, y * c - z * s, y * s + z * c)

    if axis == "y":
        return (x * c + z * s, y, -x * s + z * c)

    return (x * c - y * s, x * s + y * c, z)


def sticker_center(face: str, i: int, j: int) -> Vec3:
    n, r, u = FACE_NORMAL[face], FACE_RIGHT[face], FACE_UP[face]

    return v_add(
        n,
        v_add(
            v_scale(r, i * SPACING),
            v_scale(u, j * SPACING),
        ),
    )


def sticker_corners(face: str, i: int, j: int) -> List[Vec3]:
    r, u = FACE_RIGHT[face], FACE_UP[face]
    c = sticker_center(face, i, j)
    hw = STICKER_HALF
    out = []

    for cu, cv in (
        (-1, -1),
        (1, -1),
        (1, 1),
        (-1, 1),
    ):
        out.append(
            v_add(
                c,
                v_add(
                    v_scale(r, cu * hw),
                    v_scale(u, cv * hw),
                ),
            )
        )

    return out


class Sticker:
    __slots__ = ("face", "i", "j", "color")

    def __init__(self, face: str, i: int, j: int, color: RGB):
        self.face = face
        self.i = i
        self.j = j
        self.color = color


class Cube:
    def __init__(self):
        self.stickers: List[Sticker] = []

        for f in FACE_NORMAL:
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    self.stickers.append(
                        Sticker(
                            f,
                            i,
                            j,
                            FACE_COLOR[f],
                        )
                    )

    def is_solved(self) -> bool:
        return all(
            s.color == FACE_COLOR[s.face]
            for s in self.stickers
        )

    def layer_stickers(self, face: str) -> List[Sticker]:
        axis, layer = MOVE_AXIS[face]
        idx = AXIS_IDX[axis]

        return [
            s
            for s in self.stickers
            if layer
            * sticker_center(
                s.face,
                s.i,
                s.j,
            )[idx]
            > 0.3
        ]

    def finalize(self, face: str, direction: int) -> None:
        axis, _ = MOVE_AXIS[face]
        theta = direction * math.pi / 2

        for s in self.layer_stickers(face):
            newpos = rot_axis(
                sticker_center(
                    s.face,
                    s.i,
                    s.j,
                ),
                axis,
                theta,
            )

            best_f, best_d = "U", -9.0

            for f, n in FACE_NORMAL.items():
                d = v_dot(newpos, n)

                if d > best_d:
                    best_d = d
                    best_f = f

            resid = v_sub(
                newpos,
                FACE_NORMAL[best_f],
            )

            ni = round(
                v_dot(
                    resid,
                    FACE_RIGHT[best_f],
                ) / SPACING
            )

            nj = round(
                v_dot(
                    resid,
                    FACE_UP[best_f],
                ) / SPACING
            )

            s.face = best_f
            s.i = int(clamp(ni, -1, 1))
            s.j = int(clamp(nj, -1, 1))


def random_scramble(
    rng: random.Random,
    n: int,
) -> List[Tuple[str, int]]:
    faces = list(MOVE_AXIS)
    seq: List[Tuple[str, int]] = []
    last = None

    for _ in range(n):
        f = rng.choice(faces)

        while f == last:
            f = rng.choice(faces)

        last = f
        seq.append(
            (
                f,
                rng.choice((1, -1)),
            )
        )

    return seq


def invert_sequence(
    seq: List[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    return [
        (f, -d)
        for f, d in reversed(seq)
    ]


def notate(face: str, direction: int) -> str:
    return face if direction == 1 else face + "'"


def ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def fill_quad(
    buf: List[List[Tuple[str, int, int, int]]],
    w: int,
    h: int,
    pts: List[Tuple[float, float]],
    ch: str,
    color: RGB,
) -> None:
    ys = [p[1] for p in pts]
    y0 = max(
        0,
        int(math.floor(min(ys))),
    )
    y1 = min(
        h - 1,
        int(math.ceil(max(ys))),
    )
    n = len(pts)

    for y in range(y0, y1 + 1):
        xs = []

        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]

            if (ay <= y < by) or (by <= y < ay):
                xs.append(
                    ax
                    + (y - ay)
                    * (bx - ax)
                    / (by - ay)
                )

        xs.sort()

        for k in range(
            0,
            len(xs) - 1,
            2,
        ):
            x0 = max(
                0,
                int(round(xs[k])),
            )
            x1 = min(
                w - 1,
                int(round(xs[k + 1])),
            )
            row_color = (ch, *color)

            for x in range(
                x0,
                x1 + 1,
            ):
                buf[y][x] = row_color


class Show:
    LIGHT = (0.45, 0.65, 0.62)

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.cube = Cube()
        self.w = self.h = 0
        self.t = 0.0
        self.yaw = 0.0
        self.pitch = 0.4
        self.stars: List[
            Tuple[int, int, float]
        ] = []

        self.phase = "scramble"
        self.phase_timer = 0.4

        self.queue: List[
            Tuple[str, int]
        ] = random_scramble(
            rng,
            22,
        )

        self.move_i = 0
        self.cur_move: Optional[
            Tuple[str, int]
        ] = None

        self.move_t = 0.0
        self.move_dur = 0.16
        self.solve_seq: List[
            Tuple[str, int]
        ] = []

        self.status = "Scrambling..."
        self.speed = 1.0

    def resize(
        self,
        w: int,
        h: int,
    ) -> None:
        self.w, self.h = w, h
        n = max(
            20,
            (w * h) // 140,
        )

        self.stars = [
            (
                self.rng.randrange(w),
                self.rng.randrange(h),
                self.rng.uniform(
                    0.05,
                    0.25,
                ),
            )
            for _ in range(n)
        ]

    def _start_next_move(self) -> None:
        if self.move_i >= len(self.queue):
            self.cur_move = None

            if self.phase == "scramble":
                self.solve_seq = invert_sequence(
                    self.queue
                )
                self.phase = "pause"
                self.phase_timer = 0.9
                self.status = "Scrambled. Solving..."

            elif self.phase == "solve":
                self.phase = "hold"
                self.phase_timer = self.rng.uniform(
                    3.0,
                    4.5,
                )
                self.status = "SOLVED"

            return

        self.cur_move = self.queue[self.move_i]
        self.move_t = 0.0

    def _force_new_scramble(self) -> None:
        self.queue = random_scramble(
            self.rng,
            22,
        )
        self.move_i = 0
        self.cur_move = None
        self.move_dur = 0.16
        self.phase = "scramble"
        self.phase_timer = 0.0
        self.status = "Scrambling..."

    def update(self, dt: float) -> None:
        dt *= self.speed
        self.t += dt
        self.yaw += dt * 0.55
        self.pitch = (
            0.42
            + 0.22
            * math.sin(
                self.t * 0.18
            )
        )

        if self.phase == "pause":
            self.phase_timer -= dt

            if self.phase_timer <= 0:
                self.queue = self.solve_seq
                self.move_i = 0
                self.move_dur = 0.62
                self.phase = "solve"
                self.cur_move = None

            return

        if self.phase == "hold":
            self.phase_timer -= dt

            if self.phase_timer <= 0:
                self._force_new_scramble()

            return

        if self.cur_move is None:
            self._start_next_move()

            if self.cur_move is None:
                return

        self.move_t += dt

        if self.move_t >= self.move_dur:
            face, direction = self.cur_move

            self.cube.finalize(
                face,
                direction,
            )

            self.move_i += 1
            self.cur_move = None

            if (
                self.phase == "solve"
                and self.move_i < len(self.queue)
            ):
                nxt = self.queue[
                    self.move_i
                ]

                self.status = (
                    f"Solving... "
                    f"{self.move_i}/{len(self.queue)}"
                    f"  ({notate(*nxt)})"
                )

            self._start_next_move()

    def _project(
        self,
        p: Vec3,
    ) -> Tuple[float, float, float]:
        x, y, z = rot_axis(
            rot_axis(
                p,
                "x",
                self.pitch,
            ),
            "y",
            self.yaw,
        )

        dist = 4.4
        f = dist / (dist - z)
        scale = (
            min(self.w, self.h)
            * 0.92
        )

        sx = (
            self.w / 2.0
            + x
            * f
            * scale
            * 0.5
        )

        sy = (
            self.h / 2.0
            - y
            * f
            * scale
            * 0.25
        )

        return sx, sy, z

    def render(
        self,
        buf: List[
            List[
                Tuple[str, int, int, int]
            ]
        ],
    ) -> None:
        w, h = self.w, self.h

        for x, y, b in self.stars:
            buf[y][x] = (
                ".",
                int(255 * b),
                int(255 * b),
                int(255 * b),
            )

        face, direction = (
            self.cur_move
            if self.cur_move
            else (None, 0)
        )

        moving: List[Sticker] = (
            self.cube.layer_stickers(
                face
            )
            if face
            else []
        )

        moving_set = set(
            id(s)
            for s in moving
        )

        angle = 0.0
        axis = "y"

        if face:
            axis, _ = MOVE_AXIS[face]

            angle = (
                direction
                * (math.pi / 2.0)
                * ease(
                    clamp(
                        self.move_t
                        / self.move_dur,
                        0.0,
                        1.0,
                    )
                )
            )

        drawn = []

        for s in self.cube.stickers:
            corners3 = sticker_corners(
                s.face,
                s.i,
                s.j,
            )

            normal3 = FACE_NORMAL[
                s.face
            ]

            if id(s) in moving_set:
                corners3 = [
                    rot_axis(
                        c,
                        axis,
                        angle,
                    )
                    for c in corners3
                ]

                normal3 = rot_axis(
                    normal3,
                    axis,
                    angle,
                )

            proj = [
                self._project(c)
                for c in corners3
            ]

            nrm = rot_axis(
                rot_axis(
                    normal3,
                    "x",
                    self.pitch,
                ),
                "y",
                self.yaw,
            )

            if nrm[2] <= 0.02:
                continue

            avg_z = sum(
                p[2]
                for p in proj
            ) / 4.0

            brightness = (
                0.42
                + 0.58
                * max(
                    0.0,
                    v_dot(
                        nrm,
                        self.LIGHT,
                    ),
                )
            )

            color = (
                int(
                    s.color[0]
                    * brightness
                ),
                int(
                    s.color[1]
                    * brightness
                ),
                int(
                    s.color[2]
                    * brightness
                ),
            )

            drawn.append(
                (
                    avg_z,
                    [
                        (p[0], p[1])
                        for p in proj
                    ],
                    color,
                )
            )

        drawn.sort(
            key=lambda d: d[0]
        )

        for _, pts, color in drawn:
            fill_quad(
                buf,
                w,
                h,
                pts,
                "#",
                color,
            )

        status = self.status
        y = h - 1

        for i, ch in enumerate(
            status[:max(0, w - 2)]
        ):
            buf[y][1 + i] = (
                ch,
                190,
                190,
                190,
            )


def render_frame(
    buf,
    w: int,
    h: int,
) -> str:
    lines = []

    for y in range(h):
        row = buf[y]
        parts = []
        last = None

        for x in range(w):
            ch, r, g, b = row[x]
            key = (r, g, b)

            if key != last:
                parts.append(
                    f"{ESC}[38;2;"
                    f"{r};{g};{b}m"
                )
                last = key

            parts.append(ch)

        parts.append(
            RESET + EOL
        )

        lines.append(
            "".join(parts)
        )

    return (
        HOME
        + "\r\n".join(lines)
    )


def main() -> int:
    rng = random.Random()

    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except Exception:
        pass

    show = Show(rng)

    try:
        with TerminalSession() as term:
            w, h = os.get_terminal_size()
            show.resize(w, h)

            fps = 30
            interval = 1.0 / fps
            last = time.perf_counter()
            last_resize = last

            while True:
                now = time.perf_counter()
                dt = now - last

                if dt < interval:
                    time.sleep(
                        max(
                            0.0,
                            interval - dt,
                        )
                    )
                    continue

                last = now

                if (
                    term.poll_resize()
                    or now - last_resize > 1.0
                ):
                    last_resize = now
                    nw, nh = os.get_terminal_size()

                    if (nw, nh) != (w, h):
                        w, h = nw, nh
                        show.resize(w, h)

                key = read_key(0)

                if key in (
                    "q",
                    "Q",
                    "esc",
                ):
                    break

                if key == "+":
                    show.speed = min(
                        4.0,
                        show.speed * 1.25,
                    )

                if key == "-":
                    show.speed = max(
                        0.25,
                        show.speed / 1.25,
                    )

                show.update(
                    min(dt, 0.05)
                )

                buf = [
                    [
                        (" ", 0, 0, 0)
                    ] * w
                    for _ in range(h)
                ]

                show.render(buf)

                sys.stdout.write(
                    render_frame(
                        buf,
                        w,
                        h,
                    )
                )

                sys.stdout.flush()

    except RuntimeError as e:
        print(
            f"rubik: {e}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)

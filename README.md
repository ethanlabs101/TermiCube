# TermiCube

### A 3D Rubik's Cube, rendered entirely in your terminal.

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square\&logo=python\&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/Dependencies-None-00D4FF?style=flat-square)](#requirements)
[![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)](#license)

---

## What is TermiCube?

**TermiCube** is a dependency-free 3D Rubik's Cube animation that runs directly inside your terminal.

It generates a randomized scramble, animates the cube in real time, then slowly solves it before starting over.

No graphics libraries.
No external dependencies.
Just Python and your terminal.

---

## Features

* 🎲 Randomized cube scrambles
* 🔄 Animated layer rotations
* 🧩 Real 54-sticker cube state
* 🧠 Automatic inverse-sequence solving
* 🎥 3D perspective projection
* 💡 Dynamic lighting and shading
* ◼️ Backface culling
* 📐 Depth sorting
* 🌈 Truecolor ANSI rendering
* 🖥️ Terminal resize handling
* ⚡ 30 FPS animation loop
* 📦 Zero external Python dependencies

---

## Preview

![TermiCube Preview GIF](https://github.com/ethanlabs101/TermiCube/blob/main/demo.gif)

---

## Requirements

* Python 3
* A terminal with ANSI escape sequence support
* Truecolor support recommended

No `pip install` required.

---

## Run

Clone the repository:

```bash
git clone https://github.com/ethanlabs101/termicube.git
cd termicube
```

Run it:

```bash
python3 termicube.py
```

That's it.

---

## Controls

| Key         | Action                              |
| ----------- | ----------------------------------- |
| `Q` / `Esc` | Quit                                |
| `Space`     | Skip the current move               |
| `+` / `-`   | Increase / decrease animation speed |
| `R`         | Generate a new scramble             |

---

## How It Works

TermiCube isn't simply printing pre-made frames.

The cube maintains an internal state containing all **54 stickers**. Scramble moves are applied to that state, while the renderer projects the resulting 3D geometry into the terminal.

The animation pipeline handles:

```text
Cube State
    ↓
Layer Rotation
    ↓
3D Geometry
    ↓
Perspective Projection
    ↓
Backface Culling
    ↓
Depth Sorting
    ↓
Lighting / Shading
    ↓
ANSI Truecolor Frame
    ↓
Terminal
```

After the scramble finishes, the same sequence is inverted and played backwards, returning the cube to its solved state.

Then it starts over.

---

## Zero Dependencies

TermiCube intentionally uses only Python's standard library.

The renderer, cube state, animation system, terminal handling, input handling, projection, lighting, and frame generation are all contained in the project itself.

No third-party graphics engine is required.

---

## Why?

Because apparently a terminal needed a Rubik's Cube.

That's basically it.

I wanted to see how far a dependency-free Python terminal animation could be pushed, and this happened.

---

## Project Structure

```text
TermiCube/
├── LICENSE
├── termicube.py
├── README.md
└── demo.gif
```

The project is intentionally small and self-contained.

---

## License

MIT License.

See `LICENSE` for details.

---

<p align="center">
  <b>TermiCube</b><br>
  A Rubik's Cube for people who apparently weren't satisfied with normal terminals.
</p>

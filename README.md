# stlrapps

`stlrapps` is a collection of tools built on [`stlrcore`](https://github.com/lilellia/stlrcore) to work with timed audio
transcription data.

## Installation

**Requires: Python ≥3.11**

Simply clone/download this repository, then install its dependencies:

```bash
python3 -m pip install stlrcore ttkbootstrap loguru matplotlib
```

## astral

Designed to work with individual voice clips for a visual novel. Astral can help automate open/mouth frame animation,
generating ATL code.

## selene

Designed for automatic subtitle generation. Supports export to SRT format.

Her current design is a prototype for on-screen subtitle generation. See [Issue: **selene | on-screen subtitles
**](https://github.com/lilellia/stlrapps/issues/1).

## stlrapp

Designed to provide simple text transcriptions in Ren'Py's `say` dialogue format.
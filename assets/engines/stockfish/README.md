# Embedded Stockfish

This project ships Stockfish as a compressed asset to avoid GitHub single-file limits.

## Layout

- `packages/macos-arm64/stockfish-sf18-macos-arm64.xz`: bundled archive (tracked)
- `bin/macos-arm64/stockfish`: extracted runtime binary (generated at runtime, ignored by git)
- `LICENSE-Stockfish.txt`: upstream license text (GPL-3.0-or-later)

## Runtime behavior

`ai.stockfish_engine.ensure_embedded_stockfish()` will:

1. detect current platform
2. find matching bundled package
3. unpack the binary on first run
4. set executable bit automatically

If no bundled engine is available, the app falls back to `PATH` and common system paths.

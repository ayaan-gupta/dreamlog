# Dreamlog: working notes for Claude Code

Project 4 of 11 from "Project PRDs: 11 Builds for Claude Code". Slug `dreamlog`.

## Commands

- `make dev` starts Postgres (Docker, port 5504), the API (8104) and the web app (4104). Ports 3000, 8000 and 5432 are taken on this machine.
- `make test` runs everything, including tests that load the real Whisper and MiniLM models. `make test-fast` skips those.
- `make lint` runs ruff, mypy (strict) and tsc.
- `make seed` loads the 30 sample dreams. `make art` redraws `assets/interim`.
- `make demo` records `docs/demo.gif` and `make shots` retakes the screenshots, both against a running `make dev`.
- `.venv/bin/python scripts/calibrate_threshold.py` prints how the canonicalisation threshold was chosen.
- `cd api && ../.venv/bin/python -m dreamlog.cli key` prints a fresh encryption key.

## Layout

- `api/dreamlog/` is the FastAPI service. `service.py` holds every operation; `main.py` is routes only.
- `api/dreamlog/illustrate/` is the painter: `glyphs.py`, `procedural.py`, `atlas.py`.
- `api/dreamlog/data/` holds the 30 fixture dreams and the calibration pairs.
- `web/` is the Next.js client. It talks to the API only through the `/api` rewrite.
- `assets/prompts.md` is the image request log; `assets/interim` is code-drawn art.

## Shared conventions

- **Repo:** one repo per project, named by its slug, MIT license, README.md with a demo GIF and a one-command quickstart.
- **Default stack:** TypeScript with Vite or Next.js for web, Python (FastAPI) for ML and audio services, SQLite for local data and Postgres for hosted, deployed on Vercel or Fly.io. A PRD overrides this where it says so.
- **Creative direction:** these are portfolio pieces, so every project should feel designed. Generated imagery is a core part of the product, and each project gets a distinct visual identity from its style bible.
- **Image requests:** Claude Code does not generate images. Every image is requested from Ayaan with a numbered asset ID and short name, the exact generation prompt, size, aspect ratio, transparency and format, the exact save path under `/assets/generated`, and what the asset is for. Requests are batched per milestone and logged in `/assets/prompts.md` with a status.
- **Runtime image generation:** where an app generates images for its users, build it as an API integration behind an adapter with a built-in fallback image.
- **Quality bar:** typed code, at least 3 automated tests per milestone, no secrets in git (`.env.example` only), and an ARCHITECTURE.md of at most one page.
- **Definition of done:** runs from a clean clone with one command, passes all acceptance tests, deployed or recorded demo, README lists limitations and the next three ideas.

## How the image rule was applied here

Two kinds of image. The eleven design-time images (logo, onboarding, empty states) are requested in `assets/prompts.md` without waiting for delivery; code-drawn files in `assets/interim` stand in, and a file saved under `assets/generated` at the same path replaces its twin with no rebuild. The per-entry illustrations and the monthly atlas are runtime images: the built-in painter makes them by default, and `ApiIllustrator` sends the prompt to an image API when a key is set.

## Writing

No em dashes anywhere, in docs, comments or UI copy. README prose should sound like a person: varied sentences, no rule-of-three lists, no "it's not X, it's Y" constructions.

The UI must keep saying that Dreamlog reports patterns only. Never add copy that says what a symbol means.

## Things that will bite

- `resvg_py` 0.5.0 displaces by scale squared over two, not scale over two. `procedural._disp` takes the square root. Do not upgrade resvg without reading `test_resvg_displacement_still_behaves_as_measured`.
- resvg holds the GIL. Painting many pictures at once needs processes (`load_fixtures` uses a pool), not threads.
- faster-whisper 1.2.1 cannot open audio with PyAV 19. Audio is decoded in `audio.py` and handed over as an array. Keep both pins.
- pgvector's psycopg adapter returns its own `Vector` type. Go through `db.as_array`.
- Changing anything that consumes the scene's random stream changes every picture. Entries keep the image they were saved with; only new and edited ones repaint.
- Never add a word-to-word mapping to make a merge happen. `canonical.py` is checked for it by a test.
- Killing the API process started by `make dev` takes the web server down with it. Restart `make dev`.

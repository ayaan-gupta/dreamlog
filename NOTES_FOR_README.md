# Notes for the README

Facts for whoever writes the README. Every number here was measured in the build session on 2026-10-12, on an Apple M5 Pro with 24 GB running macOS 26.5.1, while other projects were building on the same machine (load average around 20 at the end). The command behind each number is given.

## Quickstart

- One command: `make dev`, then open http://localhost:4104.
- Needs: Docker (for Postgres), Python 3.12, Node 22, make. Nothing else, no keys.
- What it does: creates `.venv` and installs `api/requirements-dev.txt`, runs `npm ci` in `web/`, starts `pgvector/pgvector:pg16` with plain `docker run` as container `dreamlog-db`, starts the API and the web dev server.
- Measured from a fresh `git clone` into an empty directory with no container and no model cache: 73 seconds from `make dev` to `/api/health` reporting `models_ready: true`. That includes pip, npm, creating the database container and downloading both models (228 MB in `.cache/models`).
- `make test` in that same fresh clone: 76 Python tests in 110.6 s, then typecheck and 21 web tests. 97 tests, all passing.
- `npm run build` in the fresh clone succeeds (9 routes).
- `make help` lists the other targets: `test-fast`, `lint`, `seed`, `art`, `demo`, `shots`, `stop`, `clean`.
- Why `make dev` and not `docker compose up`: this machine runs Docker through colima with no compose plugin (`docker: unknown command: docker compose`), so compose could not be tested. A `docker-compose.yml` for the database alone is included and says in its header that it has not been run.

## Ports

- Web 4104 (`WEB_PORT`), API 8104 (`API_PORT`), Postgres 5504 on the host (`DB_PORT`). All three bind to 127.0.0.1.
- The browser only talks to 4104. `/api/*` is rewritten to the API by `web/next.config.ts`.

## Environment variables

All optional. `.env.example` has every one with its default.

- `WEB_PORT`, `API_PORT`, `DB_PORT`, `WEB_HOST` (default 127.0.0.1), `DREAMLOG_API_URL`
- `DREAMLOG_DATABASE_URL`, `DREAMLOG_TEST_DATABASE_URL`
- `DREAMLOG_DATA_DIR` (object store and generated key), `DREAMLOG_MODEL_CACHE_DIR`
- `DREAMLOG_ENCRYPTION_KEY` (base64 of 32 bytes; empty means generate one into the data directory)
- `DREAMLOG_KEEP_AUDIO` (default false)
- `DREAMLOG_TRANSCRIBER` (`faster-whisper` or `fake`), `DREAMLOG_WHISPER_MODEL` (default `base.en`), `DREAMLOG_WHISPER_COMPUTE_TYPE` (default `int8`)
- `DREAMLOG_EMBEDDER` (`fastembed` or `hash`), `DREAMLOG_EMBEDDING_MODEL`, `DREAMLOG_CANONICAL_THRESHOLD` (default 0.60)
- `DREAMLOG_EXTRACTOR` (`auto`, `lexicon`, `anthropic`), `DREAMLOG_LLM_MODEL` (default `claude-sonnet-5-5`), `ANTHROPIC_API_KEY`
- `DREAMLOG_ILLUSTRATOR` (`auto`, `procedural`, `api`), `DREAMLOG_IMAGE_API_URL`, `DREAMLOG_IMAGE_API_KEY`, `DREAMLOG_IMAGE_MODEL`
- `DREAMLOG_SEARCH_LIMIT` (default 10), `DREAMLOG_SEARCH_FLOOR` (default 0.2)

## What each milestone delivered

- **M1, record, transcribe, edit, save.** One-tap recorder on the home screen (MediaRecorder, WebM/Opus on Chrome, MP4/AAC on Safari), upload, local Whisper, entry saved in one request, transcript editable afterwards, typed entry as a fallback. Transcripts stored as AES-256-GCM ciphertext bound to the entry id. Audio deleted after transcription unless retention is on. 14 tests.
- **M2, symbols.** Offline extractor (581 lexicon entries in seven kinds, plus a determiner pattern for nouns it does not know), mood tags from cue words with negation, an Anthropic extractor behind the same interface, embeddings with all-MiniLM-L6-v2 through ONNX Runtime, canonicalisation by embedding similarity in pgvector, 30 fixture dreams with labels. 18 tests.
- **M3, pictures and timeline.** A procedural watercolour painter: 41 hand-written glyphs, 11 mood palettes, SVG filters for washes, rasterised by resvg to WebP. An image API adapter that falls back to the painter. Timeline grouped by month, entry page with picture, transcript and symbols. 25 tests.
- **M4, patterns.** Recurrence graph (deterministic force layout written for this, no graph library), HDBSCAN clusters with deterministic names, hybrid search, monthly atlas poster with PNG download, export as a zip, delete-all, a privacy screen that says what runs where. 18 tests, plus the latency test and 21 web tests.

## Acceptance tests

| PRD test | Status | Measured | Where |
|---|---|---|---|
| "water" and "ocean" merge into one canonical symbol on the 30-dream fixture | Met, on a fixture I wrote | cosine("a water", "an ocean") = 0.653 against a threshold of 0.60. The symbol is named "water", holds lake, ocean, river, sea and water, and is on 8 of the 8 dreams labelled as water imagery (precision 1.00, recall 1.00). Same result in 5 different orderings of the dreams. | `api/tests/test_m2_symbols.py::test_water_and_ocean_merge_into_one_canonical_symbol`, `::test_merging_really_is_by_similarity`, `::test_the_canonical_list_does_not_depend_on_the_order_of_the_dreams` |
| Semantic search for "being chased" returns the dreams tagged with pursuit | Met, on a fixture I wrote | 10 results returned. All 7 pursuit dreams are in ranks 1 to 7. Precision 0.70, recall 1.00, average precision 1.00, precision in the first 7 is 1.00. Only one of the seven contains the string "chas". | `api/tests/test_m4_patterns.py::test_search_for_being_chased_returns_the_pursuit_dreams` |
| Delete-all removes every row, file and embedding | Met | Before: 32 entries, 119 symbols, 163 aliases, 211 links, 314 stored vectors, 7 files (pictures, thumbnails, audio, atlas). After: 0 rows in every table in the public schema, 0 non-null values in all 3 vector columns, table files 0 bytes, no file left under the data directory except the key. | `api/tests/test_m4_patterns.py::test_delete_all_removes_every_row_file_and_embedding` |
| Stop-recording to saved entry under 20 s for a 60 s clip | Met, on synthetic speech | 60.9 s clip, real `faster-whisper base.en` on CPU, 3 warm runs each time. First measurement: median 4.35 s, slowest 4.76 s. Fresh clone, load average about 20: median 5.84 s, slowest 6.69 s. During the full suite with other builds running: median 7.80 s, slowest 9.68 s. Last run by stage: transcribe 2.7 s, paint 1.9 s, embed 0.07 s, canonicalise 0.01 s, extract under 1 ms. Through the web proxy with curl in the fresh clone: 5.57 s and 5.16 s. | `api/tests/test_latency.py` (`cd api && ../.venv/bin/python -m pytest tests/test_latency.py -s`) |

Caveats on that table, all of which belong in the README:

- The 30 dreams and their labels are fiction written for this project. Nobody dreamed them. The search and merge numbers say the pipeline works on that fixture.
- The speech is the macOS `say` voice Samantha, not a person who has just woken up. Whisper got every word (word match 1.000). Real speech will transcribe worse; it will not take longer.
- The latency is for a warm server. The first request after start also loads the models.
- Whisper `tiny.en` took 1.27 s and `small.en` 6.4 s for the same clip (transcription only, measured once each).

## The interesting problems

- **resvg applies a displacement map's scale twice.** The first render had no sky: every wash had vanished. I bisected the filter and found `feDisplacementMap` alone erased a 160 px circle at scale 30. A flat map with a known colour settled it: scales 2, 4, 8, 16 moved a square 2, 8, 32, 128 px where the spec says 1, 2, 4, 8. So the shift is scale squared over two. A noise map with a transparent alpha channel also dragged everything down and right, so the map is made opaque first. The painter now asks for the square root of what it wants (`procedural._disp`), `resvg_py` is pinned to 0.5.0, and `test_resvg_displacement_still_behaves_as_measured` fails if an upgrade changes it. The SVG is therefore only correct when rendered by this resvg; a browser would show less wobble.
- **Choosing the embedding model and threshold.** 100 hand-labelled pairs (40 that should merge, 60 that should not), deliberately without water/ocean. Five models, three phrasings each. all-MiniLM-L6-v2 with an article ("a door") gave AUC 0.978; the bare word gave 0.952; bge-small gave 0.972 but bunched its scores together (pairs that should stay apart had a median similarity of 0.76). Maximum F1 is 0.951 at 0.60 (precision 0.93, recall 0.97), flat from 0.60 to 0.62. Water/ocean, held out, scored 0.653. `scripts/calibrate_threshold.py` reprints all of it.
- **The calibration set had a blind spot.** It had synonyms and siblings (dog/cat) but nothing merely associated. On the fixture the model merged dentist into tooth (0.80), teacher into school (0.63) and radio into station (0.68). No threshold separates those from water/ocean at 0.653. The fix is structural: only symbols of the same kind may merge, so a person never joins an object.
- **Canonicalisation depended on the order of the dreams, and I found out by accident.** The first version compared a new word with each symbol's name and joined the nearest. The latency test happened to print its symbols, and "ocean" and "water" were both there as separate symbols: a warm-up clip had mentioned a river, water joined river (0.68), and ocean, 0.60 short of river, was left alone. Rewrote it as connected components of the same-kind similarity graph, maintained incrementally, with merges when a new word bridges two symbols. A test now loads the 30 dreams in five orders and requires the identical partition. The price is chaining: house, home, apartment, room, bedroom, hall, hotel, attic and roof are one symbol.
- **Sentence-level search was worse, not better.** I assumed scoring a dream by its best sentence would beat one embedding per dream. For "being chased" it gave average precision 0.52 against 1.00 for whole transcripts: "She kept running ahead and coming back" (a dog) and "I chased a red kite" outranked real pursuit dreams. Kept whole transcripts. The ranking is clean but the margin is not: the seventh pursuit dream scores 0.345 and the best non-pursuit dream 0.336, so there is no honest cut-off and the app shows a top ten. Mean-centring the vectors did not widen the gap.
- **faster-whisper 1.2.1 and PyAV 19 do not work together.** The first transcription died inside the library with `open() got an unexpected keyword argument 'metadata_errors'`. Audio is now decoded in `api/dreamlog/audio.py` (PyAV, resampled to 16 kHz mono) and passed to Whisper as an array.

## Things that surprised me or that I got wrong first

- `.gitignore` had a bare `data` line, which also ignored `api/dreamlog/data/`. Everything passed locally. The fresh-clone run was the first thing to notice: loading the sample dreams failed with `FileNotFoundError` because the fixture had never been committed.
- resvg holds the GIL. Eight pictures on four threads took 13.98 s, the same as one after another. Loading the samples uses a process pool and takes 13 to 15 s for 30 pictures.
- `say` will not speak slower than a floor: rates 128, 132 and 136 all produced 53.5 s. The 60 s clip needed `[[slnc 700]]` pauses between sentences.
- Headless Chromium feeds its fake microphone slower than real time while screenshots are being taken: a hold of at least 11.4 s recorded only 10 s of a 10.4 s clip, and the transcript ended at "standing in the sa-".
- pgvector's psycopg adapter returns its own `Vector` type, not a numpy array.
- The mood colour for the October atlas came out red ("angry") from an alphabetical tie-break among five moods with one dream each. The rule is now: commonest mood, ties to the more recent dream.
- Showing the canonical name on an entry was wrong: a dream about a grandfather was labelled "grandmother". Entries now show the word that was said; the grouping only shows on the patterns screen.

## Limitations, bluntly

- Nothing here was tested on real dreams or real morning speech. English only.
- The offline extractor is a word list and one grammar pattern. It finds things, not events: "being chased" is not a symbol, which is why that query is answered by meaning alone. Its 0.927 precision and 1.000 recall are on dreams written by the person who wrote the word list.
- Symbol merging over-merges. On the fixture, 163 surface forms become 119 symbols through 19 merged groups. By my own reading 7 are right (water with ocean, sea, lake, river; coat with jacket; child with baby), 6 have a right core with something chained on that should not be there (house with hotel; street with city; sun with sunflower), and 6 are wrong (mother, father and both grandparents as one symbol; brother with sister; kettle with tea; animal, bird, dog and wolf). There is no way to split or merge by hand.
- Deleting or editing a dream removes its words but never splits a symbol that a deleted word had bridged.
- The Anthropic extractor, the Anthropic cluster namer and the image API adapter have never run against the real services. There was no key. They are tested with stub clients only.
- Search has no relevance threshold worth the name. Precision at ten for the pursuit query is 0.70.
- HDBSCAN leaves about half the symbols unclustered (56 of 119 in the demo database) and names each cluster after its most central member, which gives labels like "seat" for aisle, bed, cabin, seat, ticket.
- Privacy has edges. Embeddings, symbol names, mood tags and dates are not encrypted, so a copy of the database shows which symbols recur and roughly what each dream was about. With no key configured, the key is generated and stored next to the data. The recording sits unencrypted in a temp file for the seconds transcription takes. Delete-all does not scrub Postgres WAL or backups. There are no accounts: anyone who can reach the port can read everything, which is why both servers bind to localhost.
- A phone can only record over HTTPS or localhost, and no HTTPS setup is provided, so recording has only been exercised on this machine, in headless Chromium with a fake microphone.
- The service worker registers only in a production build and caches the shell only. A dream cannot be recorded offline.
- Atlas months are cut in UTC on the server; the timeline groups in the browser's time zone.
- A picture takes 1.8 to 2.3 s to paint and the first request for an atlas poster about 5 s (2.6 MB PNG), cached afterwards. No pagination anywhere. The graph and clusters are recomputed on each request.
- The painter knows 41 glyphs. Anything else becomes a small floating light. People are never drawn; they become standing stones.
- `docker compose` and the GitHub Actions workflow have not been run. CI uses `tiny.en` so the latency test fits on a two-core runner.
- Not deployed.

## Next three ideas

- Let the owner split and merge symbols, and feed those decisions back into canonicalisation as must-link and cannot-link constraints.
- An offline queue: keep a recording in IndexedDB when the server is unreachable and process it later, plus a local HTTPS certificate so a phone can record.
- Derive the key from a passphrase in the browser and decrypt there, so the server never holds plaintext, and look at what can replace plaintext embeddings.

## Real and stand-in

- Real, and exercised: Whisper transcription (faster-whisper `base.en`, local), MiniLM embeddings (fastembed, ONNX Runtime, no PyTorch), pgvector storage and similarity queries, HDBSCAN (scikit-learn), AES-256-GCM encryption, the procedural painter (the default by design), the browser recording path (driven for real in the demo).
- Offline default standing in for an LLM: symbol and mood extraction (lexicon), cluster naming (most central member).
- Written but never run against the real thing: `AnthropicExtractor`, `AnthropicNamer`, `ApiIllustrator`.
- Synthetic data: the 30 dreams and their labels, the three speech clips (`say`), the 100 calibration pairs.
- Interim art: all 11 design-time images in `assets/interim` are drawn in code; each is requested in `assets/prompts.md`. None delivered.

## Files in docs/

- `demo.gif`: 30 s, 390 by 760, 0.72 MB. The real app in headless Chromium: record with a fake microphone, Whisper transcript and painting appear, keep the entry, timeline, patterns with water selected, search for "being chased", atlas.
- `record-phone.png`: the home screen at phone width, one record button.
- `timeline-phone.png`: the timeline with thumbnails, moods and symbols.
- `entry-desktop.png`: one entry, picture beside transcript and symbols.
- `patterns-desktop.png`: the recurrence graph with "water" selected, and the patterns-only notice.
- `search-desktop.png`: results for "being chased" with similarity scores.
- `atlas-desktop.png`: the September 2026 atlas with its six symbols and the download button.
- `privacy-phone.png`: the privacy screen, what runs where and what is encrypted.
- `illustrations.jpg`: eight entry illustrations side by side, one per mood colour.
- `atlas-2026-09.jpg`: the September poster on its own.

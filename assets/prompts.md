# Image requests

11 images requested, 0 delivered.

These are the design-time assets: the logo, the onboarding pictures and the empty states. Save each file at the path given and it is picked up on the next request, with no rebuild: the `/art/...` route in `web/src/app/art/[...path]/route.ts` serves a file from `assets/generated` in preference to the code-drawn file of the same name in `assets/interim`, one file at a time. The interim files are painted by `scripts/build_art.py` with the same code that illustrates entries.

Not requested here: the per-entry illustrations and the monthly atlas posters. Those are runtime images. The app paints them itself, or sends a prompt built by `api/dreamlog/illustrate/prompt.py` to an image API when one is configured.

**Style bible (from the PRD):** soft watercolour with dreamlike scale distortions, one dominant colour per mood, no text, no recognisable real people.

**Mood colours used by the app:** calm `#6fa8b4`, joyful `#eebf5b`, anxious `#b9b565`, fearful `#5a5f9e`, sad `#8a9bb3`, nostalgic `#cfa77c`, awed `#9478bd`, confused `#93b592`, angry `#cf6b5c`, tender `#e7a6b0`, neutral `#b3adbd`. Paper `#f7f2e8`, warm light `#f8dc9c`.

## DL-001 app mark

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** A flat, crisp app icon, not a painting. A rounded square in deep indigo #2b2760. Inside it a cream #f7f2e8 crescent moon opening to the right, and in the hollow of the crescent three amber #f6cf7e dots of different sizes joined by two thin amber lines, like a small constellation. No text, no gradients, no shadows, generous margin.
- **Spec:** 1024x1024 px, 1:1, transparent outside the rounded square, PNG.
- **Save to:** `assets/generated/logo.png`
- **Used for:** The mark beside the wordmark in the header, and the browser tab icon. The interim file is drawn in SVG by scripts/build_art.py. Without it the interim file at `assets/interim/logo.png` is shown.

## DL-002 install icon, 512

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** The same mark as DL-001, exported at this size. Not a new drawing.
- **Spec:** 512x512 px, 1:1, transparent outside the rounded square, PNG.
- **Save to:** `assets/generated/icon-512.png`
- **Used for:** The installed PWA icon on Android and desktop. Without it the interim file at `assets/interim/icon-512.png` is shown.

## DL-003 install icon, 192

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** The same mark as DL-001, exported at this size. Not a new drawing.
- **Spec:** 192x192 px, 1:1, transparent outside the rounded square, PNG.
- **Save to:** `assets/generated/icon-192.png`
- **Used for:** The home screen icon and the Apple touch icon. Without it the interim file at `assets/interim/icon-192.png` is shown.

## DL-004 maskable install icon

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** The same mark as DL-001 on a full-bleed deep indigo #2b2760 square with no rounded corners, with the moon and dots scaled to sit inside the central 78 percent so a circular mask does not clip them.
- **Spec:** 512x512 px, 1:1, opaque, PNG.
- **Save to:** `assets/generated/icon-maskable.png`
- **Used for:** The icon Android crops to its own shape. Without it the interim file at `assets/interim/icon-maskable.png` is shown.

## DL-005 onboarding: say it

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, deep indigo, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. A small bed under an enormous pale moon at night, a lit window hanging in the sky where no wall is, a few stars. Quiet, just woken.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/onboarding-record.png`
- **Used for:** First of three cards on the empty home screen, under the record button: one tap, then talk. Without it the interim file at `assets/interim/onboarding-record.png` is shown.

## DL-006 onboarding: see it

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, muted teal, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. A door far too tall standing alone in a calm sea, slightly ajar with warm light in the gap and its reflection in the water, a very small house beside it, a pale full moon.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/onboarding-picture.png`
- **Used for:** Second onboarding card: each dream gets its own picture. Without it the interim file at `assets/interim/onboarding-picture.png` is shown.

## DL-007 onboarding: notice it

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, violet, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. Seen from above like an old sea chart: six small paper-white islands in a violet sea, each holding one simple dark object (waves, a door, a key, a moon, stairs, a bird), ringed with faint contour lines and joined by dotted routes. A small compass star in one corner.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/onboarding-patterns.png`
- **Used for:** Third onboarding card: over months, see which symbols return. Without it the interim file at `assets/interim/onboarding-patterns.png` is shown.

## DL-008 empty state: timeline

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, warm grey-lilac, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. A single tall door, slightly ajar with warm light in the gap, standing on an empty plain under a large pale moon. Nothing else.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/empty-timeline.png`
- **Used for:** Shown on the timeline before there are any dreams. Without it the interim file at `assets/interim/empty-timeline.png` is shown.

## DL-009 empty state: patterns

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, warm grey-lilac, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. A low mountain range with a little snow on one peak under a sky with a handful of paper-white stars. Nothing else.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/empty-patterns.png`
- **Used for:** Shown on the patterns screen before there is anything to count. Without it the interim file at `assets/interim/empty-patterns.png` is shown.

## DL-010 empty state: search

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, warm grey-lilac, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. One enormous old key floating at an angle above an empty plain, casting a soft shadow, with a small paper-white cloud.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/empty-search.png`
- **Used for:** Shown when a search finds nothing. Without it the interim file at `assets/interim/empty-search.png` is shown.

## DL-011 empty state: atlas

- **Status:** requested (code-drawn interim file in use)
- **Prompt:** Soft watercolour on cold-pressed paper: wet-on-wet washes, visible pigment granulation, darker pooling at the edge of each wash, and a ragged unpainted paper border all round. Dreamlike scale distortion: one object far too large for the scene, another far too small. One dominant colour only, warm grey-lilac, with unpainted paper for anything light and a little warm amber for anything that glows. No text, no letters, no numbers, no people, no faces, no figures, no watermark. A small sailing boat with paper-white sails on a calm sea, its reflection broken by a few ripples, two or three distant birds.
- **Spec:** 1440x1080 px, 4:3, opaque, PNG.
- **Save to:** `assets/generated/empty-atlas.png`
- **Used for:** Shown on the atlas before any month has a dream in it. Without it the interim file at `assets/interim/empty-atlas.png` is shown.

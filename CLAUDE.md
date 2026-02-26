# CrowTalk – CLAUDE.md

## What this project is
CrowTalk is a self-contained, offline-first single-file HTML app for studying and communicating with corvids (starting with the Hooded Crow, *Corvus cornix*). It runs in Safari on iPhone with no server required.

## Key architecture
- **`build_crowtalk.py`** — Python generator. Reads audio files from `ljud/`, base64-encodes them, and injects everything into a single HTML file.
- **`index.html`** — Output: self-contained ~17MB app with all audio, CSS and JS embedded.
- **`ljud/`** — Local XC (xeno-canto) audio files. Files >6MB are skipped to keep the app loadable on iPhone.

## Build command
```bash
python3 build_crowtalk.py
```
Output: `index.html` (deploy this file via GitHub Pages or transfer to iPhone).

## App structure (5 tabs)
| Tab | Description |
|-----|-------------|
| Library | Browse + play all sounds (synth first, then XC recordings, then field recordings) |
| Record | Microphone recording with GPS, phonetics, interpretation, crow response logging |
| Journal | Field journal (date, place, weather, activity, notes) |
| Theory | Guide to crow communication science |
| Data | Stats + JSON export of all logged data |

## Data storage
- **IndexedDB** (v3): `recordings` store (field recordings as Blob + metadata), `dagbok` store (journal entries)
- **localStorage**: XC recording labels (category, name, phonetics, interpretation)

## Audio handling
- **Synthetic sounds**: Generated via Web Audio API (OscillatorNode + GainNode). No files needed.
- **XC recordings**: Base64-encoded and embedded at build time. Played via `URL.createObjectURL()` (Blob URL) for iOS Safari compatibility.
- **Field recordings**: MediaRecorder → Blob → IndexedDB.

## Metadata per recording
Each field recording stores: `blob, category, phonetic, tolkning (interpretation), response (crow reaction), place, notes, gps {lat, lon, acc}, recTime (ISO), ts, duration`

## Key JavaScript structures
- `RECORDINGS` — injected JSON array of XC audio data
- `CATEGORIES` — sound categories with internal IDs (kept stable, do not rename)
- `SYNTH_DEMOS` — synthetic sound definitions
- `COMM_GUIDE_DATA` — communication assistant rules per category
- `buildAllItems()` — merges synths + XC recordings into unified list

## Adding a new species
The app is designed to be extensible. To add a species:
1. Add audio files to `ljud/` with a species prefix
2. Add a species constant in the JS (like `SYNTH_DEMOS` but for the new species)
3. Add a species selector to the UI header

## Contributing recordings
- Field recordings are stored locally in IndexedDB
- Export via the Data tab (JSON export)
- XC recordings can be added by placing `.wav`/`.mp3` files in `ljud/` and rebuilding

## External links
- **Artportalen**: https://www.artportalen.se — Swedish species observation database
- **Merlin Bird ID**: https://merlin.allaboutbirds.org — Cornell Lab bird ID app
- **Xeno-canto**: https://xeno-canto.org — Source of XC recordings

## GitHub Pages deployment
The built `index.html` can be served directly via GitHub Pages. Users access it in Safari on iPhone, then add to home screen for an offline app experience.

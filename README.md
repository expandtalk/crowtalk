<p align="center">
  <img src="logo.png" alt="CrowTalk" width="160">
</p>

<h1 align="center">CrowTalk</h1>
<p align="center"><b>A field tool for studying and communicating with corvids — works offline on iPhone.</b></p>

CrowTalk is a single-file HTML app built for fieldwork. It combines a library of synthesized and real crow sounds, a microphone recorder with GPS tagging, a field journal, and a communication guide — all without requiring an internet connection or app store.

---

## Live app (GitHub Pages)

> 📱 Open in Safari on iPhone → tap **Share → Add to Home Screen** for a full offline app experience.

`https://expandtalk.github.io/crowtalk/`

---

## Features

- **Sound library** — Synthetic crow calls (generated via Web Audio) + real XC recordings, sorted: synthetic → field-verified → your own
- **Geo-sorted recordings** — Real recordings sorted by distance from your current location
- **Field recorder** — Records audio with automatic GPS coordinates, timestamp, phonetic notation, interpretation, and crow reaction log
- **Communication guide** — Context-aware suggestions for what to play next based on the crow's response
- **Field journal** — Date/place/weather/activity logging with IndexedDB persistence
- **Data export** — All metadata exportable as JSON for analysis or AI training
- **Offline-first** — No server, no account, no tracking
- **Multi-species ready** — Designed to extend beyond hooded crow (*Corvus cornix*)

---

## Getting started on iPhone

1. Visit the GitHub Pages URL above in **Safari**
2. Tap the share icon → **Add to Home Screen**
3. Open CrowTalk from your home screen — it works fully offline

---

## Building locally

Requirements: Python 3, audio files in `ljud/`

```bash
python3 build_crowtalk.py
```

Output: `index.html` (~17 MB, self-contained)

Transfer to iPhone via **AirDrop**, **iCloud Drive**, or **Google Drive**.

---

## Adding XC recordings

1. Download recordings from [xeno-canto.org](https://xeno-canto.org) (hooded crow: *Corvus cornix*)
2. Place `.wav` or `.mp3` files in the `ljud/` folder
3. Files larger than 6 MB are automatically skipped (iPhone memory limit)
4. Run `python3 build_crowtalk.py` to rebuild

---

## Contributing your recordings

Recordings you make in the app are stored locally in your browser (IndexedDB). To share them with the community:

1. Go to the **Data** tab → **Export JSON**
2. Open a GitHub Issue and attach your JSON export
3. We'll review and optionally include verified recordings in a future build

---

## Metadata format

Each field recording stores:

```json
{
  "category": "contact",
  "phonetic": "kraa… kraa",
  "interpretation": "Relaxed contact, approaching",
  "response": "approached",
  "place": "Södermalm, Stockholm",
  "gps": { "lat": "59.314520", "lon": "18.071948", "acc": 8 },
  "recTime": "2026-02-26T07:42:00.000Z",
  "duration": 4.2
}
```

This format is designed to be usable as a training dataset for bird call classification models.

---

## External resources

| Resource | Description |
|----------|-------------|
| [Artportalen](https://www.artportalen.se) | Swedish species observation reporting |
| [Merlin Bird ID](https://merlin.allaboutbirds.org) | Cornell Lab — AI bird identification |
| [Xeno-canto](https://xeno-canto.org) | Crowdsourced bird sound recordings |
| [eBird](https://ebird.org) | Cornell Lab — citizen science bird data |

---

## Roadmap

- [ ] Shared recording library via GitHub (pull request workflow)
- [ ] Artportalen observation logging integration
- [ ] More species: Jackdaw (*Corvus monedula*), Rook (*Corvus frugilegus*), Magpie (*Pica pica*)
- [ ] On-device call classification (TensorFlow.js)
- [ ] Regional dialect mapping

---

## License

MIT — recordings from xeno-canto.org are subject to their individual Creative Commons licenses.

---

*Built for field researchers, birders, and anyone curious about talking to crows.*

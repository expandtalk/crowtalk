#!/usr/bin/env python3
"""
Build index.html – self-contained offline app with real crow audio,
recording capability, field journal, alarm safety, and theory page.
"""
import base64, os, json, io, warnings
warnings.filterwarnings('ignore')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.signal import spectrogram as _sg

# Dark app-themed colormap: silence → teal → green → amber peak
_CROW_CMAP = LinearSegmentedColormap.from_list('crow', [
    '#07090a', '#0d2535', '#1a4a5a', '#2dd4bf', '#3ecf72', '#f0a832'])

def make_sono(path):
    """Generate a base64-encoded spectrogram PNG for an audio file."""
    try:
        import soundfile as sf
        raw, sr = sf.read(path, always_2d=True)
        data = raw.mean(axis=1).astype(np.float32)
    except Exception:
        try:
            from scipy.io import wavfile
            sr, raw = wavfile.read(path)
            if raw.ndim > 1:
                raw = raw.mean(axis=1)
            data = raw.astype(np.float32)
            if data.max() > 1.0:
                data = data / float(np.iinfo(raw.dtype).max)
        except Exception as e:
            print(f"    ⚠ sono skip ({e})")
            return None

    # Downsample to 22050 Hz max
    if sr > 22050:
        step = sr // 22050
        data = data[::step]
        sr = sr // step

    nperseg = min(512, len(data) // 8)
    f, t, Sxx = _sg(data, fs=sr, nperseg=nperseg, noverlap=nperseg*3//4, nfft=1024)
    mask = f <= 8000
    Sxx_db = 10 * np.log10(np.maximum(Sxx[mask], 1e-10))
    vmin, vmax = np.percentile(Sxx_db, [5, 99])

    fig = plt.figure(figsize=(5.5, 1.3))
    fig.patch.set_facecolor('#07090a')
    ax = fig.add_axes([0.07, 0.15, 0.92, 0.78])
    ax.pcolormesh(t, f[mask] / 1000, Sxx_db, vmin=vmin, vmax=vmax,
                  cmap=_CROW_CMAP, shading='gouraud')
    ax.set_facecolor('#07090a')
    ax.set_ylim(0, 8)
    ax.set_ylabel('kHz', color='#556070', fontsize=7, labelpad=2)
    ax.tick_params(colors='#556070', labelsize=6, length=2, width=0.5)
    for sp in ax.spines.values():
        sp.set_edgecolor('#2a3540')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=80, facecolor='#07090a', edgecolor='none')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

_HERE     = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(_HERE, "ljud")
OUTPUT    = os.path.join(_HERE, "index.html")
MAX_SIZE  = 6 * 1024 * 1024

# GitHub Pages base URL – used for og:image (social sharing preview)
GITHUB_PAGES_URL = "https://expandtalk.github.io/crowtalk"

def _b64_icon(filename):
    """Return data URI for an icon file if it exists, else empty string."""
    path = os.path.join(_HERE, filename)
    if not os.path.exists(path):
        return ''
    ext = filename.rsplit('.', 1)[-1].lower()
    mime = {'png': 'image/png', 'ico': 'image/x-icon', 'svg': 'image/svg+xml'}.get(ext, 'image/png')
    with open(path, 'rb') as f:
        return f'data:{mime};base64,{base64.b64encode(f.read()).decode()}'

ICON_180   = _b64_icon('icon-180.png')   # Apple Touch Icon
ICON_32    = _b64_icon('icon-32.png')    # Favicon
ICON_APPLE = ICON_180 or _b64_icon('icon-192.png')  # fallback to 192

print("🔊 Laddar ljudfiler...")

# Known GPS coordinates for XC recordings (lat, lon from xeno-canto.org metadata)
XC_COORDS = {
    'XC736923':  (59.33, 18.07),   # Stockholm, Sweden
    'XC1077561': (59.33, 18.07),   # Stockholm, Sweden
    'XC1077566': (59.33, 18.07),   # Stockholm, Sweden
    'XC1077567': (59.33, 18.07),   # Stockholm, Sweden
    'XC1078236': (57.70, 11.97),   # Gothenburg, Sweden
    'XC1079819': (55.60, 13.00),   # Malmö, Sweden
    'XC1079820': (55.60, 13.00),   # Malmö, Sweden
    'XC1080420': (59.85, 17.63),   # Uppsala, Sweden
}

recordings = []
for fname in sorted(os.listdir(AUDIO_DIR)):
    if not (fname.endswith('.wav') or fname.endswith('.mp3')):
        continue
    path = os.path.join(AUDIO_DIR, fname)
    size = os.path.getsize(path)
    if size > MAX_SIZE:
        print(f"  ↩ skip  {fname}  ({size//1024}KB)")
        continue
    xc_id = fname.split(' ')[0]
    base_no_ext = os.path.splitext(fname)[0]
    parts = base_no_ext.split(' - ', 1)
    fname_label = parts[1].strip() if len(parts) > 1 else base_no_ext
    mime  = 'audio/wav' if fname.endswith('.wav') else 'audio/mpeg'
    coords = XC_COORDS.get(xc_id)
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    sono = make_sono(path)
    recordings.append({'id': xc_id, 'fname_label': fname_label, 'mime': mime, 'size': size, 'audio': b64,
                        'lat': coords[0] if coords else None,
                        'lon': coords[1] if coords else None,
                        'sono': sono})
    sono_kb = f"  +{len(sono)//1024}KB sono" if sono else "  (no sono)"
    print(f"  ✓ {xc_id}  {size//1024}KB{sono_kb}")

print(f"\n  → {len(recordings)} inspelningar inbäddade\n")

REC_JSON = json.dumps([
    {'id': r['id'], 'fname_label': r['fname_label'], 'mime': r['mime'], 'size': r['size'], 'audio': r['audio'],
     'lat': r['lat'], 'lon': r['lon'], 'sono': r['sono']}
    for r in recordings
], ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="CrowTalk">
<meta name="description" content="Study and communicate with corvids — works fully offline on iPhone">
<meta property="og:title" content="CrowTalk">
<meta property="og:description" content="Field tool for studying hooded crows — sound library, recorder, journal. Offline-first on iPhone.">
<meta property="og:image" content="{GITHUB_PAGES_URL}/social.png">
<meta property="og:url" content="{GITHUB_PAGES_URL}/">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{GITHUB_PAGES_URL}/social.png">
{'<link rel="apple-touch-icon" href="' + ICON_APPLE + '">' if ICON_APPLE else ''}
{'<link rel="icon" type="image/png" href="' + ICON_32 + '">' if ICON_32 else ''}
<link rel="manifest" href="manifest.json">
<title>CrowTalk</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
:root{{
  --bg:#07090a; --s1:#0e1215; --s2:#161c20; --s3:#1e262b;
  --border:#2a3540; --t1:#e8edf0; --t2:#8fa0ac; --t3:#556070;
  --green:#3ecf72; --gdim:#1a5c34; --amber:#f0a832; --red:#e85555; --blue:#4fa8e8;
  --purple:#a78bfa; --teal:#2dd4bf;
  --safe-t:env(safe-area-inset-top); --safe-b:env(safe-area-inset-bottom);
}}
html,body{{height:100%;overflow:hidden;background:var(--bg);color:var(--t1)}}
body{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',system-ui,sans-serif;font-size:15px}}

/* Shell */
.shell{{display:flex;flex-direction:column;height:100vh;height:100dvh}}
.content{{flex:1;overflow-y:auto;overflow-x:hidden;-webkit-overflow-scrolling:touch}}

/* Top bar */
.topbar{{
  background:var(--s1);border-bottom:1px solid var(--border);flex-shrink:0;
  padding:10px 16px;padding-top:calc(var(--safe-t) + 10px);
  display:flex;align-items:center;gap:12px
}}
.topbar svg,.topbar img{{width:36px;height:36px;flex-shrink:0;border-radius:8px;object-fit:contain}}
.topbar h1{{font-size:17px;font-weight:600;letter-spacing:-0.2px}}
.topbar p{{font-size:11px;color:var(--t3);font-family:monospace}}
.offline-badge{{
  margin-left:auto;font-size:10px;font-weight:700;letter-spacing:0.5px;
  padding:3px 9px;border-radius:20px;background:var(--gdim);color:var(--green);
  border:1px solid var(--green);font-family:monospace;flex-shrink:0
}}

/* Bottom nav */
.nav{{display:flex;background:var(--s1);border-top:1px solid var(--border);flex-shrink:0;padding-bottom:var(--safe-b)}}
.nav-btn{{
  flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;
  padding:8px 2px;border:none;background:none;color:var(--t3);cursor:pointer;
  font-size:9px;font-weight:500;letter-spacing:0.2px;transition:color 0.15s
}}
.nav-btn.active{{color:var(--green)}}
.nav-btn svg{{width:20px;height:20px}}

/* Tabs */
.tab{{display:none}}.tab.active{{display:block}}

/* ── FILTER BAR ─────────────────────────────────────────────────── */
.filter-bar{{
  background:var(--s1);border-bottom:1px solid var(--border);
  padding:6px 12px 2px;flex-shrink:0
}}
.filter-row{{
  display:flex;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;padding-bottom:6px;align-items:center
}}
.filter-row::-webkit-scrollbar{{display:none}}
.filter-chip{{
  padding:6px 14px;border-radius:20px;border:1px solid var(--border);
  font-size:13px;color:var(--t2);background:var(--s2);white-space:nowrap;
  cursor:pointer;flex-shrink:0;transition:all 0.15s
}}
.filter-chip.on{{background:var(--green);color:#000;border-color:var(--green);font-weight:600}}
.filter-chip.type-real.on{{background:var(--blue);color:#000;border-color:var(--blue)}}
.filter-chip.type-synth.on{{background:var(--amber);color:#000;border-color:var(--amber)}}
.filter-chip.field-hq.on{{background:var(--green);color:#000;border-color:var(--green);font-weight:600}}
.filter-chip.field-new.on{{background:var(--purple);color:#fff;border-color:var(--purple);font-weight:600}}

/* ── SOUND LIST ─────────────────────────────────────────────────── */
.sound-list{{padding:8px 12px}}
.sound-row{{
  display:flex;align-items:center;gap:12px;
  padding:12px;background:var(--s1);border:1px solid var(--border);
  border-left-width:3px;
  border-radius:10px;margin-bottom:8px;cursor:pointer;transition:all 0.12s;
  -webkit-user-select:none;user-select:none
}}
.sound-row:active{{background:var(--s2)}}
.sound-row.playing{{border-color:var(--green);background:rgba(62,207,114,0.06)}}
.sound-row.danger{{border-color:var(--red);background:rgba(232,85,85,0.04)}}
.sound-row.type-real{{border-left-color:var(--blue)}}
.sound-row.type-synth{{border-left-color:var(--amber);background:rgba(240,168,50,0.04)}}
.mini-play{{
  width:42px;height:42px;border-radius:50%;flex-shrink:0;border:1.5px solid var(--border);
  background:var(--s2);display:flex;align-items:center;justify-content:center;transition:all 0.15s
}}
.mini-play svg{{width:16px;height:16px;color:var(--t2)}}
.sound-row.playing .mini-play{{background:var(--green);border-color:var(--green)}}
.sound-row.playing .mini-play svg{{color:#000}}
.sound-row.danger .mini-play{{border-color:var(--red)}}
.sound-info{{flex:1;min-width:0}}
.sound-name{{font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sound-meta{{font-size:12px;color:var(--t3);margin-top:2px}}
.sound-cat{{
  font-size:11px;padding:2px 8px;border-radius:10px;border:1px solid var(--border);
  color:var(--t2);flex-shrink:0;white-space:nowrap
}}
.sound-cat.labeled{{background:var(--gdim);border-color:var(--green);color:var(--green)}}
.sound-cat.danger-cat{{background:rgba(232,85,85,0.15);border-color:var(--red);color:var(--red)}}
.type-badge{{font-size:9px;font-weight:700;letter-spacing:0.5px;padding:2px 5px;border-radius:4px;flex-shrink:0;font-family:monospace}}
.type-badge.real{{background:rgba(79,168,232,0.15);color:var(--blue);border:1px solid rgba(79,168,232,0.35)}}
.type-badge.synth{{background:rgba(240,168,50,0.15);color:var(--amber);border:1px solid rgba(240,168,50,0.35)}}
.type-badge.danger{{background:rgba(232,85,85,0.15);color:var(--red);border:1px solid rgba(232,85,85,0.35)}}
.type-badge.field{{background:rgba(167,139,250,0.15);color:var(--purple);border:1px solid rgba(167,139,250,0.35)}}
.empty-state{{padding:40px 16px;text-align:center;color:var(--t3);font-size:13px}}
.drag-handle{{width:18px;height:42px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:var(--t3);cursor:grab;touch-action:none}}
.drag-handle:active{{cursor:grabbing;color:var(--t2)}}
.drag-handle svg{{pointer-events:none}}
.sound-row.drag-over{{border-top:2px solid var(--blue)}}
.sound-row.dragging{{opacity:0.3;pointer-events:none}}
.help-btn{{width:30px;height:30px;border-radius:50%;background:var(--s2);border:1px solid var(--border);color:var(--t2);font-size:14px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;line-height:1;padding:0}}
.help-btn:active{{background:var(--s3)}}
.help-overlay{{position:fixed;inset:0;z-index:300;background:rgba(0,0,0,0.72);display:flex;align-items:flex-end}}
.help-sheet{{background:var(--s1);border-radius:18px 18px 0 0;padding:22px 20px;padding-bottom:calc(env(safe-area-inset-bottom) + 28px);width:100%;max-height:75vh;overflow-y:auto}}
.help-sheet-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}}
.help-sheet h2{{font-size:17px;font-weight:700;color:var(--t1)}}
.help-close{{background:var(--s3);border:none;color:var(--t2);width:28px;height:28px;border-radius:50%;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}}
.help-body p{{font-size:14px;color:var(--t2);line-height:1.6;margin-bottom:10px}}
.help-body ul{{margin:0 0 10px 18px;font-size:14px;color:var(--t2);line-height:1.9}}
.help-body b{{color:var(--t1)}}
/* ── CONTEXT PANEL ──────────────────────────────────────────────── */
.ctx-panel{{padding:10px 12px 0;border-bottom:1px solid var(--border);background:var(--bg)}}
.ctx-row{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.ctx-mode-btn{{flex:1;padding:7px 6px;border-radius:8px;border:1.5px solid var(--border);background:var(--s2);color:var(--t3);font-size:12px;font-weight:600;cursor:pointer;text-align:center;transition:all 0.15s}}
.ctx-mode-btn.home.active{{border-color:var(--green);background:rgba(62,207,114,0.12);color:var(--green)}}
.ctx-mode-btn.new-t.active{{border-color:var(--purple);background:rgba(167,139,250,0.12);color:var(--purple)}}
.ctx-time-badge{{font-size:11px;padding:3px 8px;border-radius:8px;background:var(--s2);border:1px solid var(--border);color:var(--t3);white-space:nowrap;flex-shrink:0}}
.ctx-season{{font-size:11px;color:var(--t3);flex:1}}
.ctx-tip{{font-size:12px;color:var(--t2);background:var(--s2);border-radius:8px;padding:8px 10px;line-height:1.5;margin-bottom:10px;border-left:3px solid var(--border)}}
.ctx-tip.home{{border-left-color:var(--green)}}
.ctx-tip.new-t{{border-left-color:var(--purple)}}
.ctx-tip.caution{{border-left-color:var(--amber)}}

/* ── FIELD PLAYER OVERLAY ───────────────────────────────────────── */
.player-overlay{{
  position:fixed;inset:0;z-index:200;
  background:rgba(0,0,0,0.92);backdrop-filter:blur(8px);
  display:none;flex-direction:column;
  padding-top:calc(var(--safe-t) + 16px);
  padding-bottom:calc(var(--safe-b) + 16px);
  touch-action:pan-y
}}
.player-overlay.open{{display:flex}}
.player-header{{
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px 16px
}}
.player-close{{
  width:36px;height:36px;border-radius:50%;background:var(--s2);
  border:1px solid var(--border);color:var(--t1);font-size:20px;cursor:pointer;
  display:flex;align-items:center;justify-content:center
}}
.player-pos{{font-size:13px;color:var(--t3);font-family:monospace}}
.player-body{{
  flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:0 24px;gap:0
}}
.player-type-badge{{
  font-size:11px;font-weight:700;letter-spacing:0.8px;padding:4px 12px;border-radius:20px;
  margin-bottom:12px
}}
.player-type-badge.real{{background:rgba(79,168,232,0.15);color:var(--blue);border:1px solid var(--blue)}}
.player-type-badge.synth{{background:rgba(240,168,50,0.15);color:var(--amber);border:1px solid var(--amber)}}
.player-type-badge.danger{{background:rgba(232,85,85,0.15);color:var(--red);border:1px solid var(--red)}}
.player-type-badge.field{{background:rgba(167,139,250,0.15);color:var(--purple);border:1px solid var(--purple)}}
.player-title{{font-size:22px;font-weight:700;letter-spacing:-0.3px;text-align:center;margin-bottom:4px}}
.player-sub{{font-size:13px;color:var(--t3);text-align:center;font-family:monospace;margin-bottom:12px}}
.sono-wrap{{position:relative;margin:0 0 16px;border-radius:8px;overflow:hidden;border:1px solid var(--border)}}
.sono-wrap img{{width:100%;display:block}}
.sono-playhead{{position:absolute;top:0;bottom:0;width:2px;background:var(--green);opacity:0.85;pointer-events:none;transform:translateX(0)}}

/* Big play button */
.big-play{{
  width:96px;height:96px;border-radius:50%;border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  background:var(--green);transition:transform 0.12s,opacity 0.12s;margin-bottom:24px
}}
.big-play:active{{transform:scale(0.93)}}
.big-play.paused{{background:var(--s2);border:2px solid var(--border)}}
.big-play.danger-play{{background:var(--red);border:none}}
.big-play svg{{width:44px;height:44px;color:#000}}
.big-play.paused svg{{color:var(--t2)}}

/* Progress */
.player-progress{{width:100%;margin-bottom:8px}}
.prog-track{{
  width:100%;height:4px;background:var(--s3);border-radius:2px;
  overflow:hidden;cursor:pointer;margin-bottom:6px
}}
.prog-fill{{height:100%;background:var(--green);width:0%;transition:width 0.1s linear;border-radius:2px}}
.prog-times{{display:flex;justify-content:space-between;font-family:monospace;font-size:11px;color:var(--t3)}}

/* Controls row */
.controls-row{{display:flex;align-items:center;gap:20px;margin-bottom:24px}}
.ctrl-btn{{
  display:flex;flex-direction:column;align-items:center;gap:4px;
  background:none;border:none;cursor:pointer;color:var(--t2);padding:8px
}}
.ctrl-btn svg{{width:24px;height:24px}}
.ctrl-btn span{{font-size:10px;letter-spacing:0.3px}}
.ctrl-btn.on{{color:var(--green)}}
.ctrl-btn.on svg{{filter:drop-shadow(0 0 6px var(--green))}}

/* Volume */
.vol-row{{display:flex;align-items:center;gap:10px;width:100%;margin-bottom:20px}}
.vol-row svg{{width:18px;height:18px;color:var(--t3);flex-shrink:0}}
input[type=range]{{
  -webkit-appearance:none;flex:1;height:4px;border-radius:2px;
  background:var(--s3);outline:none;cursor:pointer
}}
input[type=range]::-webkit-slider-thumb{{
  -webkit-appearance:none;width:20px;height:20px;border-radius:50%;
  background:var(--t1);cursor:pointer;border:2px solid var(--s2)
}}

/* Swipe nav arrows */
.swipe-row{{display:flex;align-items:center;gap:16px}}
.swipe-btn{{
  width:48px;height:48px;border-radius:50%;background:var(--s2);
  border:1px solid var(--border);display:flex;align-items:center;
  justify-content:center;cursor:pointer;color:var(--t2)
}}
.swipe-btn:active{{background:var(--s3)}}
.swipe-btn svg{{width:22px;height:22px}}
.swipe-hint{{font-size:11px;color:var(--t3)}}

/* Label section inside player */
.player-label{{
  width:100%;padding:16px 24px;border-top:1px solid var(--border);
  background:var(--s1)
}}
.player-label-title{{font-size:11px;color:var(--t3);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px}}
.player-chips{{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}}
.player-chip{{
  padding:7px 14px;border-radius:20px;border:1px solid var(--border);
  font-size:13px;color:var(--t2);background:var(--s2);cursor:pointer;transition:all 0.12s
}}
.player-chip.selected{{background:var(--gdim);border-color:var(--green);color:var(--green);font-weight:500}}
.player-save-row{{display:flex;gap:8px}}
.player-notes{{
  flex:1;background:var(--s2);border:1px solid var(--border);color:var(--t1);
  padding:9px 12px;border-radius:8px;font-size:14px;font-family:inherit;resize:none
}}
.player-notes:focus{{outline:none;border-color:var(--blue)}}
.player-save{{
  padding:9px 18px;background:var(--green);border:none;border-radius:8px;
  color:#000;font-weight:600;font-size:13px;cursor:pointer;white-space:nowrap
}}
/* Record-in-field button */
.field-rec-btn{{
  width:48px;height:48px;border-radius:50%;background:var(--s2);
  border:1px solid var(--border);display:flex;align-items:center;
  justify-content:center;cursor:pointer;color:var(--t2);transition:all 0.2s
}}
.field-rec-btn.armed{{background:var(--red);border-color:var(--red);color:#fff;animation:rpulse 1s ease-in-out infinite}}
.field-rec-btn svg{{width:22px;height:22px}}
@keyframes rpulse{{0%,100%{{box-shadow:0 0 0 0 rgba(232,85,85,0.4)}}50%{{box-shadow:0 0 0 10px rgba(232,85,85,0)}}}}

/* ── ALARM SAFETY MODAL ─────────────────────────────────────────── */
.alarm-modal{{
  position:fixed;inset:0;z-index:400;
  background:rgba(0,0,0,0.95);backdrop-filter:blur(12px);
  display:none;flex-direction:column;align-items:center;justify-content:center;
  padding:32px 24px;text-align:center
}}
.alarm-modal.open{{display:flex}}
.alarm-icon{{font-size:52px;margin-bottom:16px;animation:pulse-warn 1.5s ease-in-out infinite}}
@keyframes pulse-warn{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.1)}}}}
.alarm-title{{font-size:22px;font-weight:700;color:var(--red);margin-bottom:12px}}
.alarm-body{{font-size:14px;color:var(--t2);line-height:1.7;margin-bottom:8px;max-width:320px}}
.alarm-science{{
  font-size:12px;color:var(--t3);background:var(--s2);border:1px solid var(--border);
  border-radius:10px;padding:12px 16px;margin-bottom:32px;max-width:320px;line-height:1.6
}}
.alarm-buttons{{display:flex;gap:12px;width:100%;max-width:320px}}
.alarm-cancel{{
  flex:1;padding:14px;border-radius:12px;border:1px solid var(--border);
  background:var(--s2);color:var(--t1);font-size:15px;font-weight:600;cursor:pointer
}}
.alarm-confirm{{
  flex:1;padding:14px;border-radius:12px;border:1px solid var(--red);
  background:rgba(232,85,85,0.15);color:var(--red);font-size:15px;font-weight:600;cursor:pointer
}}

/* ── RECORD TAB ─────────────────────────────────────────────────── */
.record-tip{{
  margin:12px 12px 0;padding:12px 14px;background:rgba(79,168,232,0.08);
  border:1px solid rgba(79,168,232,0.3);border-radius:10px;font-size:12px;color:var(--t2);line-height:1.6
}}
.record-tip strong{{color:var(--blue)}}
.record-center{{display:flex;flex-direction:column;align-items:center;padding:24px 16px 20px}}
.record-btn{{
  width:96px;height:96px;border-radius:50%;border:2px solid var(--border);
  background:var(--s2);display:flex;align-items:center;justify-content:center;
  cursor:pointer;position:relative;transition:all 0.2s
}}
.record-btn.armed{{background:var(--red);border-color:var(--red);animation:rpulse 1.2s ease-in-out infinite}}
.record-btn svg{{width:40px;height:40px;color:var(--t2);transition:color 0.2s}}
.record-btn.armed svg{{color:#fff}}
.rec-timer{{font-family:monospace;font-size:28px;font-weight:700;margin-top:18px;letter-spacing:2px}}
.rec-timer.armed{{color:var(--red)}}
.rec-hint{{font-size:13px;color:var(--t3);margin-top:6px}}
.pending-card{{background:var(--s1);border:1px solid var(--amber);border-radius:12px;padding:16px;margin:0 12px 16px}}
.pending-title{{font-size:12px;color:var(--amber);font-weight:600;margin-bottom:10px}}
.pending-play-row{{display:flex;align-items:center;gap:10px;margin-bottom:12px}}
.pending-play{{width:40px;height:40px;border-radius:50%;background:var(--amber);border:none;display:flex;align-items:center;justify-content:center;cursor:pointer}}
.pending-play svg{{width:16px;height:16px;color:#000}}
.pending-prog{{flex:1;height:4px;background:var(--s3);border-radius:2px;overflow:hidden}}
.pending-fill{{height:100%;background:var(--amber);width:0%}}
.pending-time{{font-family:monospace;font-size:11px;color:var(--t3)}}
.btn-row{{display:flex;gap:8px;margin-top:12px}}
.discard-btn{{flex:1;padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--s2);color:var(--t3);font-size:13px;cursor:pointer}}
.keep-btn{{flex:1;padding:10px;border-radius:8px;border:none;background:var(--amber);color:#000;font-size:13px;font-weight:600;cursor:pointer}}
.field-card{{background:var(--s1);border:1px solid var(--border);border-radius:10px;margin-bottom:8px}}
.field-head{{display:flex;align-items:center;gap:10px;padding:12px}}
.field-play{{width:38px;height:38px;border-radius:50%;background:var(--s2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}}
.field-play svg{{width:14px;height:14px;color:var(--t2)}}
.field-card.playing .field-play{{background:var(--green);border-color:var(--green)}}
.field-card.playing .field-play svg{{color:#000}}
.field-info{{flex:1;min-width:0}}
.field-id{{font-family:monospace;font-size:12px;color:var(--t2)}}
.field-label-txt{{font-size:13px;color:var(--t1);margin-top:2px}}
.field-label-txt.empty{{color:var(--t3);font-style:italic}}
.field-del{{padding:6px;background:none;border:none;color:var(--t3);cursor:pointer;font-size:20px}}
.field-prog{{padding:0 12px 10px;display:flex;align-items:center;gap:8px}}
.field-prog-track{{flex:1;height:3px;background:var(--s3);border-radius:2px;overflow:hidden}}
.field-prog-fill{{height:100%;background:var(--green);width:0%}}
.field-prog-time{{font-family:monospace;font-size:10px;color:var(--t3)}}

/* ── DAGBOK TAB ─────────────────────────────────────────────────── */
.dagbok-form{{
  background:var(--s1);border-bottom:1px solid var(--border);padding:14px 12px
}}
.dagbok-form-title{{
  font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;
  color:var(--t3);margin-bottom:12px
}}
.form-row{{display:flex;gap:8px;margin-bottom:10px}}
.form-input{{
  flex:1;background:var(--s2);border:1px solid var(--border);color:var(--t1);
  padding:10px 12px;border-radius:10px;font-size:14px;font-family:inherit
}}
.form-input:focus{{outline:none;border-color:var(--blue)}}
.form-input::placeholder{{color:var(--t3)}}
.weather-row{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}}
.weather-btn{{
  padding:8px 14px;border-radius:20px;border:1px solid var(--border);
  font-size:16px;background:var(--s2);cursor:pointer;transition:all 0.12s
}}
.weather-btn.on{{border-color:var(--amber);background:rgba(240,168,50,0.12)}}
.activity-row{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px}}
.activity-chip{{
  padding:6px 13px;border-radius:20px;border:1px solid var(--border);
  font-size:12px;color:var(--t2);background:var(--s2);cursor:pointer;transition:all 0.12s
}}
.activity-chip.on{{background:var(--gdim);border-color:var(--green);color:var(--green)}}
.dagbok-save-btn{{
  width:100%;padding:12px;border-radius:10px;border:none;
  background:var(--green);color:#000;font-size:14px;font-weight:600;cursor:pointer
}}
.terr-toggle{{display:flex;gap:4px;flex:1}}
.terr-btn{{flex:1;padding:7px 4px;border-radius:8px;border:1.5px solid var(--border);background:var(--s2);color:var(--t2);font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap}}
.terr-btn.home.active{{border-color:var(--green);background:rgba(62,207,114,0.12);color:var(--green)}}
.terr-btn.new-t.active{{border-color:var(--purple);background:rgba(167,139,250,0.12);color:var(--purple)}}
.hq-display{{display:flex;align-items:center;gap:8px;padding:4px 0 8px;min-height:32px}}
.hq-name-lbl{{font-size:14px;color:var(--t1);font-weight:500;flex:1}}
.hq-name-lbl.empty{{color:var(--t3);font-style:italic;font-size:12px}}
.hq-edit-btn{{padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:var(--s2);color:var(--t2);font-size:11px;cursor:pointer;white-space:nowrap}}
/* journal entry list */
.journal-entry{{
  background:var(--s1);border:1px solid var(--border);border-radius:12px;
  margin:0 12px 10px;overflow:hidden
}}
.journal-head{{
  display:flex;align-items:flex-start;justify-content:space-between;
  padding:12px 14px 8px
}}
.journal-date{{font-family:monospace;font-size:12px;color:var(--blue)}}
.journal-loc{{font-size:14px;font-weight:500;color:var(--t1);margin-top:2px}}
.journal-weather{{font-size:18px;margin-top:2px}}
.journal-del{{padding:4px;background:none;border:none;color:var(--t3);cursor:pointer;font-size:18px}}
.journal-activities{{
  display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 8px
}}
.journal-activity-tag{{
  font-size:11px;padding:3px 10px;border-radius:12px;
  background:rgba(62,207,114,0.1);border:1px solid var(--gdim);color:var(--green)
}}
.journal-notes{{
  padding:8px 14px 14px;font-size:13px;color:var(--t2);
  border-top:1px solid var(--border);line-height:1.6
}}
.journal-notes.empty{{color:var(--t3);font-style:italic}}
.journal-sec{{padding:12px 12px 4px;display:flex;align-items:center;justify-content:space-between}}
.journal-sec-title{{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--t3)}}

/* ── JOURNAL SUB-NAV ────────────────────────────────────────────── */
.journal-subnav{{display:flex;gap:6px;padding:10px 12px 0;background:var(--bg)}}
.jnav-btn{{flex:1;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--s1);color:var(--t2);font-size:12px;font-weight:600;cursor:pointer;transition:all .15s}}
.jnav-btn.active{{background:var(--gdim);border-color:var(--green);color:var(--green)}}
.journal-view{{display:none}}.journal-view.active{{display:block}}

/* ── MONTHLY CALENDAR ───────────────────────────────────────────── */
.month-list{{padding:10px 12px 24px}}
.month-card{{background:var(--s1);border:1px solid var(--border);border-radius:12px;margin-bottom:8px;overflow:hidden}}
.month-header{{display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;user-select:none}}
.month-icon{{font-size:22px;width:32px;text-align:center;flex-shrink:0}}
.month-title{{font-weight:700;font-size:14px;color:var(--t1);flex:1}}
.month-subtitle{{font-size:11px;color:var(--t3)}}
.month-chevron{{color:var(--t3);font-size:14px;transition:transform .2s;flex-shrink:0}}
.month-card.open .month-chevron{{transform:rotate(180deg)}}
.month-body{{display:none;padding:0 14px 14px;border-top:1px solid var(--border)}}
.month-card.open .month-body{{display:block}}
.month-body p{{font-size:13px;color:var(--t2);line-height:1.6;margin:10px 0 6px}}
.month-obs{{background:var(--s2);border-radius:8px;padding:10px 12px;margin-top:8px}}
.month-obs-title{{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--t3);margin-bottom:6px}}
.month-obs-item{{display:flex;gap:8px;font-size:12px;color:var(--t2);margin-bottom:4px;line-height:1.5}}
.month-obs-item:last-child{{margin-bottom:0}}
.month-obs-dot{{color:var(--green);flex-shrink:0;margin-top:2px}}

/* ── DATA TAB ───────────────────────────────────────────────────── */
.stat-card{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:10px}}
.stat-title{{font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:14px}}
.big-nums{{display:flex;gap:10px;margin-bottom:10px}}
.big-num{{flex:1;background:var(--s2);border-radius:10px;padding:12px;text-align:center}}
.big-num-val{{font-size:26px;font-weight:700;font-family:monospace;color:var(--green)}}
.big-num-label{{font-size:10px;color:var(--t3);margin-top:3px}}
.stat-row{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.stat-label{{font-size:13px;color:var(--t1);width:110px;flex-shrink:0}}
.stat-bar-wrap{{flex:1;height:8px;background:var(--s3);border-radius:4px;overflow:hidden}}
.stat-bar{{height:100%;background:var(--green);border-radius:4px;transition:width 0.4s ease}}
.stat-count{{font-family:monospace;font-size:12px;color:var(--t3);width:24px;text-align:right}}
.export-btn{{width:100%;padding:14px;background:var(--s2);border:1px solid var(--border);border-radius:12px;color:var(--t1);font-size:14px;font-weight:500;cursor:pointer;margin-top:4px;transition:all 0.15s}}
.export-btn:active{{background:var(--s3)}}

/* ── TEORI TAB ──────────────────────────────────────────────────── */
.teori-content{{padding:12px}}
.teori-section{{margin-bottom:20px}}
.teori-h1{{
  font-size:18px;font-weight:700;color:var(--t1);
  padding:16px 0 8px;border-bottom:1px solid var(--border);margin-bottom:12px
}}
.teori-h2{{
  font-size:14px;font-weight:600;color:var(--t2);
  text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px
}}
.call-card{{
  background:var(--s1);border:1px solid var(--border);border-left:3px solid var(--green);
  border-radius:10px;padding:12px 14px;margin-bottom:8px
}}
.call-card.danger-card{{border-left-color:var(--red)}}
.call-card.amber-card{{border-left-color:var(--amber)}}
.call-card.blue-card{{border-left-color:var(--blue)}}
.call-card.purple-card{{border-left-color:var(--purple)}}
.call-name{{font-size:14px;font-weight:600;color:var(--t1);margin-bottom:2px}}
.call-phonetic{{font-family:monospace;font-size:12px;color:var(--green);margin-bottom:4px}}
.call-desc{{font-size:13px;color:var(--t2);line-height:1.6}}
.call-badge{{
  display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;
  margin-bottom:6px
}}
.badge-alarm{{background:rgba(232,85,85,0.15);color:var(--red);border:1px solid var(--red)}}
.badge-social{{background:rgba(62,207,114,0.12);color:var(--green);border:1px solid var(--gdim)}}
.badge-food{{background:rgba(240,168,50,0.12);color:var(--amber);border:1px solid var(--amber)}}
.badge-juv{{background:rgba(79,168,232,0.12);color:var(--blue);border:1px solid var(--blue)}}
.behavior-card{{
  background:var(--s1);border:1px solid var(--border);
  border-radius:10px;padding:12px 14px;margin-bottom:8px;
  display:flex;align-items:flex-start;gap:10px
}}
.behavior-icon{{font-size:22px;flex-shrink:0}}
.behavior-text{{flex:1}}
.behavior-name{{font-size:13px;font-weight:600;color:var(--t1);margin-bottom:2px}}
.behavior-desc{{font-size:13px;color:var(--t2);line-height:1.5}}
.science-box{{
  background:rgba(79,168,232,0.06);border:1px solid rgba(79,168,232,0.25);
  border-radius:10px;padding:12px 14px;margin-bottom:8px
}}
.science-box p{{font-size:13px;color:var(--t2);line-height:1.7;margin-bottom:6px}}
.science-box p:last-child{{margin-bottom:0}}
.science-box strong{{color:var(--blue)}}
.tip-box{{
  background:rgba(62,207,114,0.06);border:1px solid rgba(62,207,114,0.25);
  border-radius:10px;padding:12px 14px;margin-bottom:8px
}}
.tip-box p{{font-size:13px;color:var(--t2);line-height:1.7;margin-bottom:6px}}
.tip-box p:last-child{{margin-bottom:0}}
.tip-box strong{{color:var(--green)}}
.warn-box{{
  background:rgba(232,85,85,0.06);border:1px solid rgba(232,85,85,0.25);
  border-radius:10px;padding:12px 14px;margin-bottom:8px
}}
.warn-box p{{font-size:13px;color:var(--t2);line-height:1.7;margin-bottom:6px}}
.warn-box p:last-child{{margin-bottom:0}}
.warn-box strong{{color:var(--red)}}
.count-table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px}}
.count-table th{{text-align:left;padding:8px 10px;color:var(--t3);font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)}}
.count-table td{{padding:9px 10px;border-bottom:1px solid var(--border);color:var(--t2);vertical-align:top;line-height:1.5}}
.count-table tr:last-child td{{border-bottom:none}}
.count-table td:first-child{{font-family:monospace;color:var(--green);font-weight:600;white-space:nowrap}}
.guide-step{{
  display:flex;gap:12px;align-items:flex-start;margin-bottom:12px
}}
.step-num{{
  width:28px;height:28px;border-radius:50%;background:var(--green);color:#000;
  font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0
}}
.step-body{{flex:1;padding-top:4px}}
.step-title{{font-size:14px;font-weight:600;color:var(--t1);margin-bottom:3px}}
.step-desc{{font-size:13px;color:var(--t2);line-height:1.6}}
.ref-item{{font-size:12px;color:var(--t3);line-height:1.8;padding:4px 0;border-bottom:1px solid var(--border)}}
.ref-item:last-child{{border-bottom:none}}
.ref-item em{{color:var(--blue)}}

.pad{{padding:12px}}
.sec-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding:12px 12px 0}}
.sec-title{{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--t3)}}
</style>
</head>
<body>
<div class="shell">

  <div class="topbar">
    {'<img src="' + ICON_APPLE + '" alt="CrowTalk">' if ICON_APPLE else ''}
    <div>
      <h1>CrowTalk</h1>
      <p id="topSub">Corvus cornix</p>
    </div>
    <span class="offline-badge">OFFLINE</span>
    <button class="help-btn" onclick="showHelp()">?</button>
  </div>

  <div id="ctxPanel" class="ctx-panel" style="display:none"></div>

  <div class="help-overlay" id="helpOverlay" style="display:none" onclick="closeHelp()">
    <div class="help-sheet" onclick="event.stopPropagation()">
      <div class="help-sheet-head">
        <h2 id="helpTitle"></h2>
        <button class="help-close" onclick="closeHelp()">×</button>
      </div>
      <div class="help-body" id="helpBody"></div>
    </div>
  </div>

  <div class="content">

    <!-- ══ TAB: BIBLIOTEK ══════════════════════════════════════════ -->
    <div class="tab active" id="tab-library">
      <div class="filter-bar" id="filterBar"></div>
      <div class="sound-list" id="soundList"><div class="empty-state" style="padding:24px;text-align:center;opacity:.5">Loading sounds…</div></div>
    </div>

    <!-- ══ TAB: SPELA IN ══════════════════════════════════════════ -->
    <div class="tab" id="tab-record">
      <div class="record-tip">
        <strong>🗺 Regional sounds:</strong> Crow dialect varies between populations.
        Always note the location when saving — your recording contributes to local dialect research.
      </div>
      <div class="record-center">
        <button class="record-btn" id="recordBtn">
          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>
        </button>
        <div class="rec-timer" id="recTimer">0:00</div>
        <div class="rec-hint" id="recHint">Tap to record</div>
      </div>
      <div id="pendingZone" style="display:none"></div>
      <div class="sec-head">
        <span class="sec-title">Field recordings</span>
        <span id="fieldCount" style="font-size:11px;color:var(--t3);font-family:monospace"></span>
      </div>
      <div class="pad" style="padding-top:0">
        <div id="fieldList">
          <div class="empty-state">No recordings yet</div>
        </div>
      </div>
    </div>

    <!-- ══ TAB: DAGBOK ═════════════════════════════════════════════ -->
    <div class="tab" id="tab-dagbok">
      <div class="journal-subnav">
        <button class="jnav-btn active" id="jnav-log" onclick="switchJournalView('log')">📝 Log Entry</button>
        <button class="jnav-btn" id="jnav-cal" onclick="switchJournalView('cal')">📅 Monthly Calendar</button>
      </div>

      <!-- VIEW: Log Entry -->
      <div class="journal-view active" id="jview-log">
        <div class="dagbok-form">
          <div class="dagbok-form-title">New journal entry</div>
          <div class="form-row">
            <input class="form-input" id="dbDate" type="date" style="flex:none;width:150px">
            <div class="terr-toggle">
              <button class="terr-btn home active" id="terrHome" onclick="setJournalMode('home')">🏠 Home Quarter</button>
              <button class="terr-btn new-t" id="terrNew" onclick="setJournalMode('new')">🌲 New Territory</button>
            </div>
          </div>
          <div class="hq-display" id="hqDisplay">
            <span id="hqNameLbl" class="hq-name-lbl empty">(No Home Quarter set)</span>
            <button class="hq-edit-btn" onclick="promptSetHQ()">✏️ Set HQ</button>
          </div>
          <input class="form-input" id="dbPlace" type="text" placeholder="Territory name / area..." style="display:none;margin-bottom:8px">
          <div style="font-size:11px;color:var(--t3);margin-bottom:6px">Weather</div>
          <div class="weather-row" id="weatherRow">
            <button class="weather-btn" data-w="☀️">☀️</button>
            <button class="weather-btn" data-w="🌤️">🌤️</button>
            <button class="weather-btn" data-w="⛅">⛅</button>
            <button class="weather-btn" data-w="🌧️">🌧️</button>
            <button class="weather-btn" data-w="🌩️">🌩️</button>
            <button class="weather-btn" data-w="❄️">❄️</button>
            <button class="weather-btn" data-w="🌫️">🌫️</button>
          </div>
          <div style="font-size:11px;color:var(--t3);margin-bottom:6px">What happened?</div>
          <div class="activity-row" id="activityRow">
            <button class="activity-chip" data-a="Offered food">Offered food</button>
            <button class="activity-chip" data-a="Got response">Got response</button>
            <button class="activity-chip" data-a="Got gift">Got gift 🎁</button>
            <button class="activity-chip" data-a="Contact established">Contact established</button>
            <button class="activity-chip" data-a="Played sound">Played sound</button>
            <button class="activity-chip" data-a="Mobbing incident">Mobbing incident</button>
            <button class="activity-chip" data-a="Responded to call">Responded to call</button>
            <button class="activity-chip" data-a="No response">No response</button>
          </div>
          <textarea class="form-input" id="dbNotes" placeholder="Observations, behaviours, number of crows, notable events..." rows="3" style="width:100%;margin-bottom:10px;resize:none"></textarea>
          <button class="dagbok-save-btn" onclick="saveDagbok()">Save entry</button>
        </div>
        <div class="journal-sec">
          <span class="journal-sec-title">Journal</span>
          <span id="dagbokCount" style="font-size:11px;color:var(--t3);font-family:monospace"></span>
        </div>
        <div id="dagbokList">
          <div class="empty-state" style="padding:32px 16px">No entries yet</div>
        </div>
      </div>

      <!-- VIEW: Monthly Calendar -->
      <div class="journal-view" id="jview-cal">
        <div class="month-list">
          <div class="teori-h1" style="padding:10px 2px 12px;font-size:13px;color:var(--t3)">What to observe month by month — Hooded Crow in suburban Stockholm</div>

          <!-- JANUARY -->
          <div class="month-card" id="mc-jan">
            <div class="month-header" onclick="toggleMonth('mc-jan')">
              <div class="month-icon">❄️</div>
              <div><div class="month-title">January</div><div class="month-subtitle">Winter flocking · food dependency</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Crows gather in larger groups for winter protection. Deep snow covers natural food, making them more dependent on supplementary feeding. A core family group of 12–13 individuals may adopt a regular feeder as part of their territory — numbers can swell to ~30 when neighbouring crows join.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Large mixed flocks (crows + jackdaws) in open areas</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Cooperative foraging — individuals signal food finds to the group</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Crows flying to greet you when you appear with food</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Pair bonds visible even within the flock</div>
              </div>
            </div>
          </div>

          <!-- FEBRUARY -->
          <div class="month-card" id="mc-feb">
            <div class="month-header" onclick="toggleMonth('mc-feb')">
              <div class="month-icon">🌨️</div>
              <div><div class="month-title">February</div><div class="month-subtitle">Pre-spring restlessness · hierarchy visible</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Large flocks of crows and jackdaws cross the sky — increased activity despite remaining snow and cold. A clear hierarchy becomes visible: older, larger crows act as "group leaders" deep in the forest, signalling which direction the flock should fly when food is found. Territory thinking begins to form.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Directed flock movements — follow a lead bird from a forest edge</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Pairs beginning to separate slightly from the main flock</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Increased vocalisation near potential nesting sites</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>First signs of courtship: bowing, preening each other</div>
              </div>
            </div>
          </div>

          <!-- MARCH -->
          <div class="month-card" id="mc-mar">
            <div class="month-header" onclick="toggleMonth('mc-mar')">
              <div class="month-icon">💨</div>
              <div><div class="month-title">March</div><div class="month-subtitle">Nest building · storm flying</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>First signs of spring. Storms become a playground — crows use strong winds for acrobatic flying, sometimes in pairs, sometimes in groups. Their flight over open fields looks like a dance. Flock sizes decrease as pairs establish territories. Food caching becomes more frequent as individuals compete.</p>
              <p>Late March: nest construction begins. Pairs select a tree, often at height, and start building. In Årsta, one pair nests at 6th-floor height, visible from an 8th-floor apartment.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Acrobatic flying in wind — barrel rolls, sudden dives</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Pairs carrying sticks and twigs to nest sites</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Food caching: crow buries excess food, smooths surface with bill</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Smaller groups — territorial pairs dispersing</div>
              </div>
            </div>
          </div>

          <!-- APRIL -->
          <div class="month-card" id="mc-apr">
            <div class="month-header" onclick="toggleMonth('mc-apr')">
              <div class="month-icon">🌸</div>
              <div><div class="month-title">April</div><div class="month-subtitle">Incubation begins · interspecies conflict</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Crows are seen in established pairs. Females sit tight on the nest, resting heavily before egg laying. Multiple nests visible in neighbourhood trees. Other species become aggressive: fieldfares (björktrastar) defend territory against crows and will dive-bomb them — sometimes in coordinated attacks. Ravens appear sporadically and displace local crows from their territory.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Female sitting low on nest, barely visible</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Male foraging alone and returning to the nest area</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Fieldfare attacks on crows — watch crows crouch and flee</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Crows escorting ravens out of territory</div>
              </div>
            </div>
          </div>

          <!-- MAY -->
          <div class="month-card" id="mc-may">
            <div class="month-header" onclick="toggleMonth('mc-may')">
              <div class="month-icon">🌿</div>
              <div><div class="month-title">May</div><div class="month-subtitle">Hatching · chick care</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Large winter flocks are gone. Pairs focus on their own family and territory. Early May: first chicks hatch. The female broods while the male forages. Eggs: up to 6, pale blue-green with liver-brown spots, ~45×30 mm. Warning calls (3 fast calls) sound when a fox, crow or raptor approaches the nest.</p>
              <p>Gulls and herring gulls become the primary aerial threat in the upper airspace during this period.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Male making multiple food trips per hour</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Female rarely leaving the nest</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>3-call alarm (rapid KRA-KRA-KRA) when predators appear</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Only one crow from the pair visible at a time near the nest</div>
              </div>
            </div>
          </div>

          <!-- JUNE -->
          <div class="month-card" id="mc-jun">
            <div class="month-header" onclick="toggleMonth('mc-jun')">
              <div class="month-icon">☀️</div>
              <div><div class="month-title">June</div><div class="month-subtitle">Fledglings · first flight</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Around June 1, the first fledglings leave the nest. They are already large but cannot fly — they jump on the ground and cling to bicycles and fences. Juveniles are recognisable: duller plumage, slightly lighter, softer bill, blue eyes and swollen gape corners. They beg loudly with raised wings when a parent approaches.</p>
              <p>By day 9, a chick may fly 10 metres up into a tree. The male grows bolder, following the observer further from the nest. Both parents feed young. Tragically, traffic and gull attacks take some fledglings.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Juvenile: blue eyes, pink gape, wobbly posture</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Begging call — high-pitched, loud, constant</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Parent caching food 20 m away for later retrieval</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Both parents calling (4 soft calls) after feeding — contentment</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Magpies and gulls hunting fieldfare chicks nearby</div>
              </div>
            </div>
          </div>

          <!-- JULY -->
          <div class="month-card" id="mc-jul">
            <div class="month-header" onclick="toggleMonth('mc-jul')">
              <div class="month-icon">🌞</div>
              <div><div class="month-title">July</div><div class="month-subtitle">Summer dispersal · teaching</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Crows seem to disappear during daytime. Activity shifts to early morning (from ~06:00). Juveniles are still with parents, being taught foraging and territory skills. The family may range more widely now that chicks can fly. Historically reported that some crow populations move toward Åland and the islands in summer — hard to verify.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Juveniles following parents — still begging but less insistently</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Family groups of 4–5 birds moving together</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Best observation window: early morning, same spot daily</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>One juvenile may be slower to develop than siblings</div>
              </div>
            </div>
          </div>

          <!-- AUGUST -->
          <div class="month-card" id="mc-aug">
            <div class="month-header" onclick="toggleMonth('mc-aug')">
              <div class="month-icon">🍒</div>
              <div><div class="month-title">August</div><div class="month-subtitle">Juvenile independence · pre-autumn</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Continued development of juveniles. Late berries, insects and small animals provide ideal training prey. Parents demonstrate tool use, food handling and caching. The juvenile grows gradually more independent — exploring alone but returning for support. Parents may begin reinforcing or scouting next year&#39;s nesting site.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Juvenile foraging independently for short periods</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Juveniles practising bill manipulation: opening packages, probing cracks</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Parents watching from distance while juvenile forages</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Increased interactions with neighbouring crow families</div>
              </div>
            </div>
          </div>

          <!-- SEPTEMBER -->
          <div class="month-card" id="mc-sep">
            <div class="month-header" onclick="toggleMonth('mc-sep')">
              <div class="month-icon">🍂</div>
              <div><div class="month-title">September</div><div class="month-subtitle">Thermals · aerial competition · mobbing</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Autumn felt clearly. Large flocks circle industrial areas, using thermals from heated asphalt and flat rooftops. Crows and gulls compete for the same airspace with different strategies: gulls dominate in calm weather with their long wings; crows dominate in gusty autumn wind with their compact, manoeuvrable wings.</p>
              <p>September 25 (Årsta): a long-eared owl was chased into a tree by crows and jackdaws, terrorised for hours by magpies that plucked its tail feathers. This "mobbing" behaviour drives predators from nesting areas and is one of the corvids' key collective defence tools.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Thermals: crows circling in tight spirals above industrial areas</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Mobbing events: multiple crows dive-bombing a raptor or owl</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Intense food caching before first frost</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Juvenile vocal development — calls becoming stronger and more varied</div>
              </div>
            </div>
          </div>

          <!-- OCTOBER -->
          <div class="month-card" id="mc-oct">
            <div class="month-header" onclick="toggleMonth('mc-oct')">
              <div class="month-icon">🌬️</div>
              <div><div class="month-title">October</div><div class="month-subtitle">Storm play · nut cracking · flocking</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Dramatic autumn weather. Crows "play" in storms — acrobatic flying high in the wind strengthens flight muscles ahead of winter. Flocking increases: restless groups of young crows move across the city in preparation for winter. In southern Sweden, crows have been observed placing walnuts on roads and waiting for cars to crack them open, then retrieving the kernels — a learned cultural behaviour spread through observation.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Storm flying: barrel rolls and tumbles in strong wind</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Road nut-cracking: crow drops hard food on traffic lanes</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Large restless flocks crossing the city</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Fallen fruit scavenging — apples, rowan berries</div>
              </div>
            </div>
          </div>

          <!-- NOVEMBER -->
          <div class="month-card" id="mc-nov">
            <div class="month-header" onclick="toggleMonth('mc-nov')">
              <div class="month-icon">🌧️</div>
              <div><div class="month-title">November</div><div class="month-subtitle">Winter movement · urban foraging</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Crows from further north (including possibly Åland) may arrive on the Swedish mainland as conditions worsen. Those staying intensify urban foraging — raking through fallen leaves and checking bins. Social dynamics grow more complex: competition for limited resources increases aggression between individuals. Migration, if it occurs, typically happens flockwise from October onwards, preferring calm or light tailwind conditions.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Unfamiliar individuals appearing in established territories</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Displacement fights at reliable food sources</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Leaf-raking behaviour to expose insects and seeds</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Large communal roosts forming at dusk in tall trees</div>
              </div>
            </div>
          </div>

          <!-- DECEMBER -->
          <div class="month-card" id="mc-dec">
            <div class="month-header" onclick="toggleMonth('mc-dec')">
              <div class="month-icon">🌃</div>
              <div><div class="month-title">December</div><div class="month-subtitle">Winter roosts · Christmas surplus</div></div>
              <div class="month-chevron">▼</div>
            </div>
            <div class="month-body">
              <p>Urban crows in Stockholm adapt well to the city&#39;s warmth. Foraging around restaurants and bins intensifies — the Christmas season&#39;s increased food waste is a key resource. Large winter roosts form in trees near heat sources (ventilation shafts, heated buildings). Territorial disputes increase as natural food sources shrink and competition with other wintering species grows.</p>
              <div class="month-obs">
                <div class="month-obs-title">What to watch for</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Winter roosts: dozens of crows gathering at dusk in the same tree</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Active bin and skip foraging, especially near restaurants</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Crows near ventilation exhausts and other urban heat sources</div>
                <div class="month-obs-item"><span class="month-obs-dot">●</span>Established pairs staying close — pair bond maintained through winter</div>
              </div>
            </div>
          </div>

        </div>
      </div><!-- end jview-cal -->
    </div>

    <!-- ══ TAB: THEORY ══════════════════════════════════════════════ -->
    <div class="tab" id="tab-teori">
      <div class="teori-content">

        <div class="teori-section">
          <div class="teori-h1">🎵 Vocalisations</div>
          <div class="call-card">
            <span class="call-badge badge-social">Social</span>
            <div class="call-name">Contact call</div>
            <div class="call-phonetic">kraa… kraa (1–2 calls)</div>
            <div class="call-desc">Soft, calm call to maintain contact with flock or partner. The most common call in everyday situations. Longer pauses between calls signal relaxation.</div>
          </div>
          <div class="call-card amber-card">
            <span class="call-badge badge-food">Food</span>
            <div class="call-name">Food call</div>
            <div class="call-phonetic">kra-kra-kra (2–3 short)</div>
            <div class="call-desc">Shorter, faster calls when food is found. Research shows crows deliberately keep food calls shorter to avoid attracting too many competitors (Pendergraft &amp; Marzluff, 2019).</div>
          </div>
          <div class="call-card danger-card">
            <span class="call-badge badge-alarm">Alarm</span>
            <div class="call-name">Alarm call</div>
            <div class="call-phonetic">KRA! KRA! KRA! (3 fast)</div>
            <div class="call-desc">Three fast, loud calls when a raptor or other threat is detected. Universally understood by other crows. <strong style="color:var(--red)">WARNING: May cause a permanent negative association if used against crows that don't know you.</strong></div>
          </div>
          <div class="call-card danger-card">
            <span class="call-badge badge-alarm">Alarm</span>
            <div class="call-name">Mobbing</div>
            <div class="call-phonetic">KRA-KRA-KRA-KRA-KRA (5+ calls)</div>
            <div class="call-desc">Intense, repeated calls to rally the flock against a threat. Five or more calls mobilise the entire flock. Crows remember faces and can spread "warning" to others (Cornell Lab, 2012).</div>
          </div>
          <div class="call-card blue-card">
            <span class="call-badge badge-juv">Regional</span>
            <div class="call-name">Territorial</div>
            <div class="call-phonetic">KRAAAA (2 long, powerful)</div>
            <div class="call-desc">Powerful, extended call to defend territory. Used mostly during breeding season. Shows clear variation between regional populations — an important sound for dialect research.</div>
          </div>
          <div class="call-card purple-card">
            <span class="call-badge badge-social">Social</span>
            <div class="call-name">Rattle / Click</div>
            <div class="call-phonetic">klk-klk-klk (low frequency)</div>
            <div class="call-desc">Low-frequency clicking or rattling sound. Used in close social contact, often between pairs. A sign of relaxed trust — a good sign if a crow rattles near you.</div>
          </div>
          <div class="call-card">
            <span class="call-badge badge-juv">Juvenile</span>
            <div class="call-name">Juvenile call</div>
            <div class="call-phonetic">high-pitched, uncertain</div>
            <div class="call-desc">Young crows have a thinner, higher-pitched voice. Adult crows are usually tolerant of begging juveniles. Juvenile calls are regionally inconsistent — dialect develops during the first year of life.</div>
          </div>
          <div class="call-card amber-card">
            <span class="call-badge badge-food">Comfort</span>
            <div class="call-name">Content / Comfort call</div>
            <div class="call-phonetic">kraa-kraa-kraa-kraa (4 soft)</div>
            <div class="call-desc">Four soft, calm calls used in safe situations — resting, near a partner, or after successful feeding. Similar to contact call but with longer duration per call.</div>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🔢 Call count</div>
          <table class="count-table">
            <thead>
              <tr><th>Count</th><th>Meaning</th><th>Situation</th></tr>
            </thead>
            <tbody>
              <tr><td>1</td><td>Acknowledgement / attention</td><td>Reply to contact, "I see you"</td></tr>
              <tr><td>2</td><td>Contact / greeting</td><td>Calm presence, near partner</td></tr>
              <tr><td>3</td><td>Alarm — threat</td><td>Raptor, unknown human</td></tr>
              <tr><td>4</td><td>Content / well-being</td><td>Safe situation, bonding</td></tr>
              <tr><td>5+</td><td>Mobbing — rally flock</td><td>Intense threat, chasing raptor</td></tr>
              <tr><td>2–3 short</td><td>Food</td><td>Food find, but kept sparse</td></tr>
              <tr><td>2 long</td><td>Territorial</td><td>Territory defence, breeding season</td></tr>
            </tbody>
          </table>
          <div class="science-box">
            <p><strong>Counting:</strong> A 2024 study in Science showed that crows mentally plan 1–4 calls before vocalising — one of the few documented forms of numerical planning in birds.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🐦 Body language</div>
          <div class="behavior-card">
            <div class="behavior-icon">⬆️</div>
            <div class="behavior-text">
              <div class="behavior-name">Upright posture, feathers sleek</div>
              <div class="behavior-desc">Alert or alarm behaviour. The crow is focused on a potential threat. Often combined with alarm calls.</div>
            </div>
          </div>
          <div class="behavior-card">
            <div class="behavior-icon">⬇️</div>
            <div class="behavior-text">
              <div class="behavior-name">Hunched, ruffled feathers</div>
              <div class="behavior-desc">Relaxed and calm state. Ruffled feathers = thermoregulation or relaxation. A good sign if the crow hunches near you.</div>
            </div>
          </div>
          <div class="behavior-card">
            <div class="behavior-icon">🙇</div>
            <div class="behavior-text">
              <div class="behavior-name">Head-lowering (allopreening)</div>
              <div class="behavior-desc">The crow lowers its head towards a partner for preening. A sign of deep trust and social bonding. Rare towards humans, but documented.</div>
            </div>
          </div>
          <div class="behavior-card">
            <div class="behavior-icon">🍗</div>
            <div class="behavior-text">
              <div class="behavior-name">Flying towards you + wing flapping</div>
              <div class="behavior-desc">Begging behaviour, common in juveniles towards parents. Towards humans = established relationship and expectation of food.</div>
            </div>
          </div>
          <div class="behavior-card">
            <div class="behavior-icon">🎁</div>
            <div class="behavior-text">
              <div class="behavior-name">Leaving objects</div>
              <div class="behavior-desc">Documented behaviour in crows that have formed close bonds with humans. Considered reciprocal gift-giving — the crow returns the favour for food received.</div>
            </div>
          </div>
          <div class="behavior-card">
            <div class="behavior-icon">👁️</div>
            <div class="behavior-text">
              <div class="behavior-name">Direct eye contact + sideways posture</div>
              <div class="behavior-desc">Crow eyes are on the sides of the head. Tilting to look directly with one eye = focus and curiosity. Avoiding eye contact = discomfort.</div>
            </div>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">💬 Communicating with crows</div>
          <div class="tip-box">
            <p><strong>Core principle:</strong> Crows are highly social and curious, but also cautious. Build trust gradually. A crow that trusts you will actively seek you out.</p>
          </div>
          <div class="guide-step">
            <div class="step-num">1</div>
            <div class="step-body">
              <div class="step-title">Establish a safe place</div>
              <div class="step-desc">Visit the same spot at the same time each day. Leave food (walnuts, unsalted peanuts, soft food) without trying to interact. Let the crows observe you undisturbed for 1–2 weeks.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">2</div>
            <div class="step-body">
              <div class="step-title">Start with contact calls</div>
              <div class="step-desc">Once the crows are used to you: play a soft contact call (1–2 calls) via the app. Wait 30–60 seconds. If they respond or move closer — repeat. Never play alarm or mobbing at this stage.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">3</div>
            <div class="step-body">
              <div class="step-title">Record responses</div>
              <div class="step-desc">Record the crow's response directly in the app (Record tab). Note call count, character and behaviour in the journal. Patterns over time reveal whether you are classified as friend, neutral or threat.</div>
            </div>
          </div>
          <div class="warn-box">
            <p><strong>⚠️ Never use alarm or mobbing against unfamiliar crows.</strong> A crow that classifies you as a "threat" shares that information with its flock. This negative association can persist for months to years and is very difficult to reverse.</p>
            <p><strong>Exception:</strong> Alarm can be useful if you want to study reaction patterns — but only with crows that already know you well and can see that it is you playing.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🗺️ Regional dialects</div>
          <div class="science-box">
            <p>Hooded crow (<em>Corvus cornix</em>) vocalisations show measurable acoustic differences between populations. Studies across Scandinavia, Central Europe and the Mediterranean have documented systematic variations in fundamental frequency, call duration and modulation patterns.</p>
            <p><strong>Why this matters to you:</strong> A crow in your region may not respond appropriately to a recording made in another country. The app includes recordings from xeno-canto — note the recording's country of origin for each XC sound.</p>
            <p><strong>Your role:</strong> Every recording you make and tag with a location contributes to mapping regional dialects. Share data via the JSON export.</p>
          </div>
          <div class="tip-box">
            <p><strong>Tip:</strong> Always record the crow's response immediately after playing a sound. Comparing the sound you played with the crow's reply is the core of dialect research.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">👤 Facial recognition</div>
          <div class="science-box">
            <p>Research at the University of Washington (Marzluff et al., 2010) showed that crows (<em>Corvus brachyrhynchos</em>, likely applicable to <em>C. cornix</em> as well) are capable of individual facial recognition in humans.</p>
            <p><strong>The experiment:</strong> Crows were trapped by researchers wearing a specific mask. Afterwards, crows reacted aggressively specifically towards that mask — not others. The reaction also spread to crows that were not present during the trapping.</p>
            <p><strong>Memory:</strong> Negative associations were still observed <strong>5 years later</strong>. Positive associations appear to build more slowly but are equally lasting.</p>
          </div>
          <div class="tip-box">
            <p><strong>Practical conclusion:</strong> Crows in your area recognise your face. Always wear similar clothing during contact sessions to reduce confusion. Hats and glasses can interfere with recognition.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🏠 Territory &amp; trust — why your mode matters for the crow</div>
          <div class="science-box">
            <p>Hooded crows divide the world into known individuals and strangers. When a crow classifies you as "safe", that assessment is stored permanently — and shared with their mate and nearby flock members. The reverse is equally true. The mode you choose in this app affects which sounds and behaviours are appropriate, not just for your own safety but for the crow's social world.</p>
          </div>
          <div class="teori-h2">Home Quarter</div>
          <div class="tip-box">
            <p>You and the local crows have reached an implicit agreement: <em>you bring food, you are not a threat, you behave predictably.</em> From the crow's perspective this is a genuine social relationship. They can read your body language. They notice if you're anxious, distracted, or aggressive. Mirror their communication — contact calls answered with contact calls, silence answered with silence — and the relationship deepens over time.</p>
            <p><strong>Key insight:</strong> The crows in your home quarter are not simply tolerating you. They are actively managing a relationship with a predictable resource partner. You have become part of their cognitive map — a named, remembered individual in their social network.</p>
          </div>
          <div class="teori-h2">New Territory</div>
          <div class="tip-box">
            <p>Entering a new territory means the resident crows must classify you from scratch. <em>Threat or neutral?</em> This assessment takes seconds. First impressions compound — a single alarm response means all crows present form a threat memory of your face and voice that can persist for years and will spread through the flock via social learning.</p>
            <p><strong>Key insight:</strong> Never play alarm or mobbing calls in a new territory. Even if the crows don't react visibly, the negative association is being formed in their memory. Start with passive presence only, then — if they approach neutrally — a single soft contact call. Give the crows time to classify you correctly: as a harmless observer.</p>
            <p><strong>From the crow's perspective:</strong> A strange human who makes crow alarm sounds near a nest site is the precise behavioural signature of a predator. That threat profile will be shared across the local flock rapidly.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🕐 Time of day — daily cycle &amp; the evening roost</div>
          <div class="teori-h2">Daily rhythm</div>
          <div class="science-box">
            <table style="width:100%;border-collapse:collapse;font-size:13px;line-height:1.7">
              <tr style="color:var(--t3)"><td style="padding:3px 0;font-weight:600;white-space:nowrap">Time</td><td style="padding:3px 8px;font-weight:600">Phase</td><td style="padding:3px 0;font-weight:600">Behaviour &amp; recommendation</td></tr>
              <tr><td style="color:var(--t3);white-space:nowrap">05–08</td><td style="padding:2px 8px">🌅 Dawn</td><td>Peak vocality, territorial. Best time for contact calls — crows are alert and responsive.</td></tr>
              <tr><td style="color:var(--t3)">08–12</td><td style="padding:2px 8px">☀️ Morning</td><td>Active foraging and social interaction. Good window for building contact in home quarter.</td></tr>
              <tr><td style="color:var(--t3)">12–15</td><td style="padding:2px 8px">🌤 Midday</td><td>Lower activity, resting and preening. Minimal response to calls. Passive observation only.</td></tr>
              <tr><td style="color:var(--t3)">15–18</td><td style="padding:2px 8px">🌇 Afternoon</td><td>Pre-roost foraging intensifies. Food calls effective. Crows are motivated and focused.</td></tr>
              <tr><td style="color:var(--t3)">18–21</td><td style="padding:2px 8px">🌆 Evening</td><td>Communal roost flight. Observe only — see below.</td></tr>
              <tr><td style="color:var(--t3)">21–05</td><td style="padding:2px 8px">🌙 Night</td><td>Roosting. Crows are silent unless disturbed. No field activity recommended.</td></tr>
            </table>
          </div>
          <div class="teori-h2">Evening roost movement</div>
          <div class="science-box">
            <p>In autumn and winter, Hooded Crows from a large area converge each evening on communal roost sites — sometimes thousands of birds. This movement is not random: it follows established flight corridors and is organised by experienced individuals who know the safe routes and roost locations.</p>
            <p>Younger birds (juveniles and first-year crows) are <strong>escorted</strong> by older, experienced birds. You can observe this as a mixture of confident, direct fliers (adults — larger body, more purposeful wingbeats) and smaller, less certain birds following the stream. The escort relationship is how younger generations learn the roost locations, safe flight corridors, and social rules of the broader population. This is active cultural transmission — knowledge passed between individuals, not hardwired instinct.</p>
            <p>During roost movement, crows are collectively vigilant. Any disturbance — including unusual human sounds — can panic the entire stream. If a location causes repeated disturbances, crows will begin to route around it.</p>
          </div>
          <div class="tip-box">
            <p><strong>Observer tip:</strong> Stand still, be silent, and watch the stream overhead. You can identify experienced adults by their larger body size, more deliberate wingbeats, and their position at the front or flanks of the stream — they are guiding. Juveniles tend to fly in the centre or rear, following the leaders. The constant calling during roost flight ("recruiting calls") is how the flock stays coherent across a wide area. It is one of the most impressive things you can witness in urban bird life.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">📏 Estimating crow age — size matters</div>
          <div class="science-box">
            <p>Hooded Crows approach adult size by their first autumn, but body mass and structural robustness continue to develop over 2–3 years. In the field, <strong>larger individuals are almost always older</strong> — and older means more experienced, higher social status, and more likely to be a territory holder.</p>
          </div>
          <div class="teori-h2">Field markers</div>
          <div class="guide-step">
            <div class="step-num">1</div>
            <div class="step-body">
              <div class="step-title">Body size &amp; bill thickness</div>
              <div class="step-desc">A noticeably large, heavy-chested crow with a thick bill is almost certainly an adult (2+ years) and likely a territory holder. These individuals move with deliberate confidence — they have earned their status and know it.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">2</div>
            <div class="step-body">
              <div class="step-title">Plumage contrast</div>
              <div class="step-desc">Adult crows (after their first full moult at ~14 months) have clean, iridescent black feathers with crisp contrast against the grey body. Juveniles often have duller, slightly brownish-tinged feathers, especially on the crown and wings.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">3</div>
            <div class="step-body">
              <div class="step-title">Eye colour</div>
              <div class="step-desc">Juvenile Hooded Crows have a pale, bluish-grey iris. Adults develop a dark brown to near-black iris. Visible at close range and a reliable age marker when combined with other features.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">4</div>
            <div class="step-body">
              <div class="step-title">Behavioural confidence</div>
              <div class="step-desc">Older crows hold their ground longer, approach more directly, and leave more slowly. Juveniles are more erratic and easily startled, and defer to older individuals at food sources. If a crow stays calm as you approach, it is likely older.</div>
            </div>
          </div>
          <div class="tip-box">
            <p><strong>Social significance:</strong> When a large, confident crow approaches you in a new territory, it is almost certainly the dominant individual or one of the resident pair. How it reacts to you — and how you respond — sets the template for every crow in the area. This bird is also likely actively teaching younger birds how to assess you. Its response will propagate through the local social network within hours. Be calm, make no sudden movements. If you play a sound at all, make it a single, soft contact call.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🔗 External resources</div>
          <div class="stat-card" style="padding:12px 14px">
            <div class="ref-item" style="margin-bottom:10px">
              <a href="https://www.artportalen.se" target="_blank" style="color:var(--green);text-decoration:none;font-weight:600">🌿 Artportalen</a>
              <span style="color:var(--t3)"> — Swedish species observation database. Report your crow observations here.</span>
            </div>
            <div class="ref-item" style="margin-bottom:10px">
              <a href="https://merlin.allaboutbirds.org" target="_blank" style="color:var(--green);text-decoration:none;font-weight:600">🐦 Merlin Bird ID</a>
              <span style="color:var(--t3)"> — Cornell Lab AI bird identification. Great for verifying species in the field.</span>
            </div>
            <div class="ref-item" style="margin-bottom:10px">
              <a href="https://xeno-canto.org/explore?query=Corvus+cornix" target="_blank" style="color:var(--green);text-decoration:none;font-weight:600">🎵 Xeno-canto</a>
              <span style="color:var(--t3)"> — Crowdsourced bird sound library. Source of XC recordings in this app.</span>
            </div>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🧠 Intelligence &amp; cognition</div>
          <div class="science-box">
            <p>Corvids (crows, jackdaws, ravens, rooks) belong to the family Corvidae and rank among the most cognitively advanced animals on Earth. They learn new sounds throughout life, cooperate, use tools, and may be capable of empathy.</p>
            <p><strong>Neural density:</strong> The raven&#39;s pallium contains up to 14× more neurons per gram than the human cerebral cortex. A 2020 study in <em>Science</em> showed that bird brains are structurally more similar to mammal brains than previously thought — with long-range associative circuits comparable to the neocortex.</p>
            <p><strong>Raven development:</strong> A 2020 study in <em>Scientific Reports</em> found that hand-raised ravens tested at 4 months perform comparably to adult great apes on cognitive tasks — suggesting rapid and near-complete cognitive maturation very early in life.</p>
          </div>
          <div class="science-box">
            <p><strong>Mourning the dead:</strong> Research by Dr Kaeli Swift (University of Washington) documented corvids gathering in large groups around dead flock members, leaving objects (sticks, feathers) at the body, and following the corpse for days. Brain scans showed activation of threat-memory regions — suggesting these gatherings serve a functional purpose: learning about danger from the manner of death.</p>
          </div>
          <div class="tip-box">
            <p><strong>Old field observation (Shetland Islands, 1888):</strong> About 50 crows were seen gathered on a field in what looked like a "court". One crow stood apart as if on trial. After a period of intense calling it crouched, appearing to beg for mercy — and was then executed by the flock, which scattered immediately. Such reports of apparent collective social judgment have been noted across multiple historical sources.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">✂️ Crow training</div>
          <div class="science-box">
            <p>Because crows learn quickly and retain information long-term, positive reinforcement training is effective. The key is <strong>consistency, patience, and a reliable reward</strong> delivered immediately after the desired behaviour.</p>
            <p>Behavioural researcher Christian Gunther-Hanssen developed a pilot project in Södertälje where crows were trained to collect cigarette butts in exchange for food from a vending machine — a project that became international news. The principle can be applied to any retrievable object.</p>
          </div>
          <div class="guide-step">
            <div class="step-num">1</div>
            <div class="step-body">
              <div class="step-title">Establish a food relationship first</div>
              <div class="step-desc">Before any training, build a reliable feeding routine (same time, same place, same signal). The crow must associate you with reward before it will engage with training tasks. This phase takes 1–4 weeks.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">2</div>
            <div class="step-body">
              <div class="step-title">Introduce the target object</div>
              <div class="step-desc">Place the target item (e.g. a cigarette butt, a coin, a marked stone) near the feeding spot. Reward the crow any time it approaches or touches the object — even if it just investigates it. Use a short, repeatable reward sound (whistle or click) immediately at the moment of correct behaviour.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">3</div>
            <div class="step-body">
              <div class="step-title">Shape pick-up behaviour</div>
              <div class="step-desc">Reward only when the crow picks up the object. Do not reward approach alone. Place multiple objects on the ground; reward each pick-up. Crows are fast learners — expect to see deliberate pick-ups within days once the association is formed.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">4</div>
            <div class="step-body">
              <div class="step-title">Add a deposit location</div>
              <div class="step-desc">Place a small container (bowl, box) near the feeding point. Reward the crow only when it drops the object into the container. Start with the container directly below where the crow normally lands; gradually move it to a fixed permanent location.</div>
            </div>
          </div>
          <div class="guide-step">
            <div class="step-num">5</div>
            <div class="step-body">
              <div class="step-title">Increase difficulty gradually</div>
              <div class="step-desc">Scatter objects at different distances and heights. Introduce similar-looking non-target items; only reward the correct object. The crow will learn to discriminate. Once reliable in one environment, test in different weather and lighting conditions.</div>
            </div>
          </div>
          <div class="warn-box">
            <p><strong>Never use punishment.</strong> Crows have a long, precise memory for negative experiences. A single bad encounter can undo weeks of trust-building. If a session goes poorly, simply end it — do not withhold food as punishment.</p>
          </div>
          <div class="tip-box">
            <p><strong>Whistle cue:</strong> Establish a consistent whistle or sound before presenting food. Over time the whistle alone will bring crows from considerable distance — useful for calling them to a training session.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">🐾 Enemies &amp; mobbing</div>
          <div class="science-box">
            <p>Natural enemies include eagle owls and hawks. However, crows in groups can overwhelm and kill a hawk that attacks a nest — and have been documented burying the carcass under branches afterwards. Mobbing behaviour (coordinated harassment of a larger predator) is one of the corvid family&#39;s most sophisticated collective defence strategies. Crows on Stockholm&#39;s bridges have been seen circling eagles passing through their territory.</p>
            <p>Other species also mob crows: fieldfares (björktrastar) are particularly aggressive during their own breeding season and will dive-bomb crows repeatedly, sometimes even depositing droppings on them in flight.</p>
          </div>
        </div>

        <div class="teori-section">
          <div class="teori-h1">📚 References</div>
          <div class="stat-card" style="padding:12px 14px">
            <div class="ref-item">Marzluff, J.M. et al. (2010). <em>Lasting recognition of threatening people by wild American crows.</em> Animal Behaviour, 79(3), 699–707.</div>
            <div class="ref-item">Pendergraft, L.T. &amp; Marzluff, J.M. (2019). <em>Crow vocalizations: complexity and context.</em> Behavioural Processes, 163, 78–89.</div>
            <div class="ref-item">Nieder, A. et al. (2024). <em>Crows count before they vocalize.</em> Science, 383, 1058–1061.</div>
            <div class="ref-item">Clayton, N.S. &amp; Dickinson, A. (1998). <em>Episodic-like memory during cache recovery by scrub jays.</em> Nature, 395, 272–274.</div>
            <div class="ref-item">Emery, N.J. &amp; Clayton, N.S. (2004). <em>The mentality of crows.</em> Science, 306, 1903–1907.</div>
            <div class="ref-item">Cornell Lab of Ornithology (2012). <em>Crow behavior and vocal communication.</em> Birds of North America Online.</div>
            <div class="ref-item">xeno-canto Foundation (2024). <em>Corvus cornix recordings.</em> xeno-canto.org. CC BY-NC-SA 4.0.</div>
            <div class="ref-item">Olkowicz, S. et al. (2016). <em>Birds have primate-like numbers of neurons in the forebrain.</em> PNAS, 113(26), 7255–7260.</div>
            <div class="ref-item">Kabadayi, C. &amp; Osvath, M. (2017). <em>Ravens parallel great apes in flexible planning for tool-use and bartering.</em> Science, 357(6347), 202–204.</div>
            <div class="ref-item">Swift, K.N. &amp; Marzluff, J.M. (2015). <em>Wild American crows gather around their dead to learn about danger.</em> Animal Behaviour, 109, 187–197.</div>
            <div class="ref-item">Güntürkün, O. &amp; Bugnyar, T. (2016). <em>Cognition without cortex.</em> Trends in Cognitive Sciences, 20(4), 291–303.</div>
          </div>
        </div>

      </div>
    </div>

    <!-- ══ TAB: DATA ═══════════════════════════════════════════════ -->
    <div class="tab" id="tab-data">
      <div class="pad" style="padding-top:16px">
        <div id="dataContent"></div>
      </div>
    </div>

  </div>

  <nav class="nav">
    <button class="nav-btn active" data-tab="library" onclick="switchTab('library')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
      </svg>
      <span>Library</span>
    </button>
    <button class="nav-btn" data-tab="record" onclick="switchTab('record')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"/>
      </svg>
      <span>Record</span>
    </button>
    <button class="nav-btn" data-tab="dagbok" onclick="switchTab('dagbok')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
      </svg>
      <span>Journal</span>
    </button>
    <button class="nav-btn" data-tab="teori" onclick="switchTab('teori')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"/>
      </svg>
      <span>Theory</span>
    </button>
    <button class="nav-btn" data-tab="data" onclick="switchTab('data')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>
      </svg>
      <span>Data</span>
    </button>
  </nav>
</div>

<!-- Field player overlay -->
<div class="player-overlay" id="playerOverlay">
  <div class="player-header">
    <span class="player-pos" id="playerPos"></span>
    <button class="player-close" id="playerClose">✕</button>
  </div>
  <div class="player-body">
    <span class="player-type-badge" id="playerBadge"></span>
    <div class="player-title" id="playerTitle"></div>
    <div class="player-sub" id="playerSub"></div>

    <div class="sono-wrap" id="sonoWrap" style="display:none">
      <img id="sonoImg" alt="Spectrogram">
      <div class="sono-playhead" id="sonoPlayhead"></div>
    </div>

    <button class="big-play paused" id="bigPlay">
      <svg id="bigPlayIcon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
    </button>

    <div class="player-progress" id="playerProgress">
      <div class="prog-track" id="progTrack">
        <div class="prog-fill" id="progFill"></div>
      </div>
      <div class="prog-times">
        <span id="progCur">0:00</span>
        <span id="progDur">0:00</span>
      </div>
    </div>

    <div class="vol-row">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
      <input type="range" id="volSlider" min="0" max="1" step="0.05" value="1">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77 0-4.28-2.99-7.86-7-8.77z"/></svg>
    </div>

    <div class="controls-row">
      <button class="ctrl-btn" id="loopBtn" onclick="toggleLoop()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3"/>
        </svg>
        <span>Loop</span>
      </button>
      <button class="ctrl-btn" id="fieldRecToggle" onclick="toggleFieldRecFromPlayer()">
        <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>
        <span>Record</span>
      </button>
      <button class="swipe-btn" onclick="prevSound()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
      </button>
      <button class="swipe-btn" onclick="nextSound()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
      </button>
    </div>
  </div>

  <!-- Kommunikationsassistent -->
  <div id="commGuide" style="margin:0 16px 12px;background:var(--s2);border:1px solid var(--border);border-radius:12px;overflow:hidden;display:none">
    <button onclick="toggleCommGuide()" style="width:100%;background:none;border:none;color:var(--t1);padding:12px 16px;text-align:left;font-size:13px;display:flex;justify-content:space-between;align-items:center;cursor:pointer">
      <span>🤝 Communication guide</span>
      <svg id="commArrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;transition:transform 0.2s"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
    </button>
    <div id="commGuideBody" style="padding:0 16px 14px;display:none;font-size:13px;color:var(--t2);line-height:1.6">
      <div id="commText"></div>
      <div id="commSuggest" style="margin-top:10px"></div>
    </div>
  </div>

  <div class="player-label" id="playerLabelSection">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;flex-shrink:0">✏️ Name</span>
      <input class="player-notes" id="playerNameInput" type="text" placeholder="Give the recording a name..." style="flex:1;padding:8px 12px;border-radius:8px;font-size:14px;height:auto">
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;flex-shrink:0">🔤 Phonetic</span>
      <input class="player-notes" id="playerPhonetic" type="text" placeholder="e.g. kra-kra-kra…" style="flex:1;padding:8px 12px;border-radius:8px;font-size:14px;height:auto;font-family:monospace">
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
      <span style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;flex-shrink:0">💡 Meaning</span>
      <input class="player-notes" id="playerTolkning" type="text" placeholder="e.g. Warning – raptor nearby…" style="flex:1;padding:8px 12px;border-radius:8px;font-size:14px;height:auto">
    </div>
    <div class="player-label-title">Categorise</div>
    <div class="player-chips" id="playerChips"></div>
    <div class="player-save-row">
      <textarea class="player-notes" id="playerNotes" placeholder="Notes, context, weather, location…" rows="2"></textarea>
      <button class="player-save" onclick="savePlayerLabel()">Save</button>
    </div>
  </div>
</div>

<!-- Alarm Safety Modal -->
<div class="alarm-modal" id="alarmModal">
  <div class="alarm-icon">⚠️</div>
  <div class="alarm-title" id="alarmModalTitle"></div>
  <div class="alarm-body" id="alarmModalBody"></div>
  <div class="alarm-science" id="alarmModalScience"></div>
  <div class="alarm-buttons">
    <button class="alarm-cancel" id="alarmCancel">Cancel</button>
    <button class="alarm-confirm" id="alarmConfirm">Play anyway</button>
  </div>
</div>

<audio id="mainAudio"></audio>
<audio id="fieldAudio"></audio>

<script>
// ═══════════════════════════════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════════════════════════════
const RECORDINGS = {REC_JSON};

const CATEGORIES = [
  {{id:'kontaktrop',  label:'Contact call', note:'1–2 calls, soft'}},
  {{id:'alarm',       label:'Alarm',        note:'3 fast, loud'}},
  {{id:'mobbing',     label:'Mobbing',      note:'5+ calls, intense'}},
  {{id:'matrop',      label:'Food call',    note:'Short, near food'}},
  {{id:'territorial', label:'Territorial',  note:'Powerful'}},
  {{id:'rassel',      label:'Rattle',       note:'Clicking'}},
  {{id:'juvenil',     label:'Juvenile',     note:'High-pitched'}},
  {{id:'ovrigt',      label:'Other',        note:''}},
];

// Danger categories that need confirmation before playing
const DANGER_SYNTHS = new Set(['alarm','mob']);

const SYNTH_DEMOS = [
  {{id:'syn_contact', name:'Contact (2 calls)',  ph:'kraa… kraa',          cat:'kontaktrop', note:'Longer = friendly',      danger:false}},
  {{id:'syn_food',    name:'Food (3 short)',     ph:'kra-kra-kra',          cat:'matrop',    note:'Shorter near food',      danger:false}},
  {{id:'syn_alarm',   name:'Alarm (3 fast)',     ph:'KRA! KRA! KRA!',      cat:'alarm',     note:'3 = warning',            danger:true}},
  {{id:'syn_mob',     name:'Mobbing (5+)',       ph:'KRA-KRA-KRA-KRA-KRA', cat:'mobbing',   note:'5+ = rally the flock',   danger:true}},
  {{id:'syn_content', name:'Content (4 calls)',  ph:'kraa-kraa-kraa-kraa',  cat:'ovrigt',   note:'Relaxed / observed',     danger:false}},
  {{id:'syn_click',   name:'Rattle',             ph:'klk-klk-klk',          cat:'rassel',   note:'Social close contact',   danger:false}},
];

// Haversine distance in km between two lat/lon points
function haversine(lat1, lon1, lat2, lon2) {{
  const R = 6371, dLat = (lat2-lat1)*Math.PI/180, dLon = (lon2-lon1)*Math.PI/180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}}

// Current user position (updated when available)
let userLat = null, userLon = null;
if (navigator.geolocation) {{
  navigator.geolocation.getCurrentPosition(p => {{
    userLat = p.coords.latitude; userLon = p.coords.longitude;
    renderSoundList(); // re-sort once we have position
  }}, ()=>{{}}, {{enableHighAccuracy:false, timeout:8000, maximumAge:60000}});
}}

// Order: 1) Synths  2) XC recordings (geo-sorted if location known)  3) Field recordings (badge: own)
let fieldItems = [];
async function loadFieldItems() {{
  if (!db) {{ fieldItems = []; return; }}
  const recs = await dbGetAll('recordings');
  const hqRaw = getHQName().trim().toLowerCase();
  fieldItems = recs.map(r => {{
    const placeRaw = (r.place||'').trim().toLowerCase();
    const territory = (hqRaw && placeRaw === hqRaw) ? 'hq' : 'new';
    const dateStr = r.recTime
      ? new Date(r.recTime).toLocaleDateString('sv-SE',{{month:'short',day:'numeric'}})
      : '';
    return {{
      id: 'field_' + r.id,
      type: 'field',
      territory,
      name: r.phonetic || r.category || 'Field recording',
      sub: [r.place, dateStr].filter(Boolean).join(' · '),
      cat: r.category || '',
      notes: r.tolkning || '',
      audio: null, synth: null, danger: false, fieldRec: r
    }};
  }});
}}

function buildAllItems() {{
  const lbl = getLabels();

  // 1. Synthetic sounds first
  const synths = SYNTH_DEMOS.map(d => ({{
    id: d.id, type:'synth', name: d.name,
    sub: d.ph, cat: d.cat, notes:'', audio:null, synth:d, danger: d.danger, badge:'synth'
  }}));

  // 2. XC library recordings – geo-sorted if user position is known
  let reals = RECORDINGS.map(r => {{
    const dist = (userLat && r.lat && r.lon) ? haversine(userLat, userLon, r.lat, r.lon) : null;
    const phonetic = lbl[r.id]?.phonetic || '';
    const sizeMeta = (r.size/1024).toFixed(0) + ' KB · ' + (r.mime==='audio/wav'?'WAV':'MP3') + (dist!==null?' · '+Math.round(dist)+'km':'');
    return {{
      id: r.id, type:'real', badge:'xc',
      name: lbl[r.id]?.name || r.fname_label || r.id,
      sub: phonetic || sizeMeta,
      cat: lbl[r.id]?.category || '',
      notes: lbl[r.id]?.notes || '',
      audio: r, synth: null, danger: false, dist,
    }};
  }});
  if (userLat) reals.sort((a,b) => (a.dist??9999) - (b.dist??9999));

  return [...applyCustomOrder([...synths, ...reals]), ...fieldItems];
}}

// ── Labels (localStorage) ───────────────────────────────────────────
function getLabels() {{ return JSON.parse(localStorage.getItem('ct_labels')||'{{}}'); }}
function saveLabels(obj) {{ localStorage.setItem('ct_labels', JSON.stringify(obj)); }}

// ── IndexedDB ───────────────────────────────────────────────────────
let db;
function openDB() {{
  return new Promise((res,rej) => {{
    const req = indexedDB.open('crowtalk',3);
    req.onupgradeneeded = e => {{
      const d = e.target.result;
      if (!d.objectStoreNames.contains('recordings'))
        d.createObjectStore('recordings',{{keyPath:'id',autoIncrement:true}});
      if (!d.objectStoreNames.contains('dagbok'))
        d.createObjectStore('dagbok',{{keyPath:'id',autoIncrement:true}});
    }};
    req.onsuccess = e => {{ db=e.target.result; res(db); }};
    req.onerror  = () => rej(req.error);
  }});
}}
function dbAdd(store,r)    {{ return dbOp(store,'readwrite', s=>s.add(r)); }}
function dbGetAll(store)   {{ return dbOp(store,'readonly',  s=>s.getAll()); }}
function dbDelete(store,id){{ return dbOp(store,'readwrite', s=>s.delete(id)); }}
function dbOp(store,mode,fn) {{
  return new Promise((res,rej) => {{
    const tx=db.transaction(store,mode), req=fn(tx.objectStore(store));
    req.onsuccess=()=>res(req.result); req.onerror=()=>rej(req.error);
  }});
}}

// ═══════════════════════════════════════════════════════════════════
// JOURNAL SUB-NAV
// ═══════════════════════════════════════════════════════════════════
function switchJournalView(view) {{
  document.querySelectorAll('.journal-view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.jnav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('jview-'+view).classList.add('active');
  document.getElementById('jnav-'+view).classList.add('active');
}}

function toggleMonth(id) {{
  const card = document.getElementById(id);
  if (card) card.classList.toggle('open');
}}

// ═══════════════════════════════════════════════════════════════════
// NAV
// ═══════════════════════════════════════════════════════════════════
function switchTab(name) {{
  activeTab = name;
  renderContextPanel();
  stopMain();
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.querySelector(`.nav-btn[data-tab="${{name}}"]`).classList.add('active');
  if (name==='record') renderField();
  if (name==='data')   renderData();
  if (name==='dagbok') renderDagbok();
}}

// ═══════════════════════════════════════════════════════════════════
// FILTER
// ═══════════════════════════════════════════════════════════════════
let activeFilters = new Set(['all']);

function renderFilterBar() {{
  const bar = document.getElementById('filterBar');
  const typeFilters = [
    {{id:'all',   label:'All',          cls:''}},
    {{id:'real',  label:'🔵 Real',      cls:'type-real'}},
    {{id:'synth', label:'🟡 Synthetic', cls:'type-synth'}},
    ...CATEGORIES.map(c=>( {{id:'cat_'+c.id, label:c.label, cls:''}} )),
  ];
  bar.innerHTML = `
    <div class="filter-row">
      <button class="filter-chip field-hq ${{activeFilters.has('field_hq')?'on':''}}" data-fid="field_hq">🏠 Home Quarter</button>
      <button class="filter-chip field-new ${{activeFilters.has('field_new')?'on':''}}" data-fid="field_new">🌲 New Territory</button>
    </div>
    <div class="filter-row">
      ${{typeFilters.map(f=>`<button class="filter-chip ${{f.cls}} ${{activeFilters.has(f.id)?'on':''}}" data-fid="${{f.id}}">${{f.label}}</button>`).join('')}}
    </div>`;
  bar.querySelectorAll('.filter-chip').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const fid = btn.dataset.fid;
      if (fid === 'all') {{
        activeFilters = new Set(['all']);
      }} else {{
        activeFilters.delete('all');
        if (activeFilters.has(fid)) activeFilters.delete(fid);
        else activeFilters.add(fid);
        if (!activeFilters.size) activeFilters.add('all');
      }}
      renderFilterBar();
      renderSoundList();
    }});
  }});
}}

function getFilteredItems() {{
  const items = buildAllItems();
  if (activeFilters.has('all')) return items;
  const hasFieldHQ  = activeFilters.has('field_hq');
  const hasFieldNew = activeFilters.has('field_new');
  const hasFieldFilter = hasFieldHQ || hasFieldNew;
  const catFilters  = [...activeFilters].filter(f=>f.startsWith('cat_'));
  const hasTypeFilter = activeFilters.has('real') || activeFilters.has('synth');
  const hasCatFilter  = catFilters.length > 0;
  return items.filter(item => {{
    if (item.type === 'field') {{
      if (!hasFieldFilter) return false;
      return (hasFieldHQ && item.territory==='hq') || (hasFieldNew && item.territory==='new');
    }}
    // real / synth items
    if (!hasTypeFilter && !hasCatFilter) return false;
    const typeMatch = (activeFilters.has('real') && item.type==='real') ||
                      (activeFilters.has('synth') && item.type==='synth');
    const catMatch  = catFilters.some(f => f.replace('cat_','') === item.cat);
    if (hasTypeFilter && hasCatFilter) return typeMatch && catMatch;
    if (hasTypeFilter) return typeMatch;
    if (hasCatFilter)  return catMatch;
    return false;
  }});
}}

// ═══════════════════════════════════════════════════════════════════
// CUSTOM ROW ORDER (drag-to-reorder)
// ═══════════════════════════════════════════════════════════════════
let activeTab = 'library';
function getCustomOrder(){{try{{return JSON.parse(localStorage.getItem('rowOrder')||'[]')}}catch{{return[]}}}}
function saveCustomOrder(ids){{localStorage.setItem('rowOrder',JSON.stringify(ids))}}
function applyCustomOrder(items){{
  const order=getCustomOrder();
  if(!order.length) return items;
  const pos={{}};order.forEach((id,i)=>pos[id]=i);
  return [...items].sort((a,b)=>((pos[a.id]??9999)-(pos[b.id]??9999)));
}}

// ── HTML5 drag (desktop) ─────────────────────────────────────────────
let dragSrcIdx=-1;
function dragStart(e,idx){{
  dragSrcIdx=idx;
  e.dataTransfer.effectAllowed='move';
  setTimeout(()=>document.querySelector(`[data-idx="${{idx}}"]`)?.classList.add('dragging'),0);
}}
function dragOver(e,idx){{
  e.preventDefault();
  document.querySelectorAll('.sound-row.drag-over').forEach(r=>r.classList.remove('drag-over'));
  if(idx!==dragSrcIdx) document.querySelector(`[data-idx="${{idx}}"]`)?.classList.add('drag-over');
}}
function dragEnd(){{
  document.querySelectorAll('.sound-row').forEach(r=>r.classList.remove('dragging','drag-over'));
  dragSrcIdx=-1;
}}
function dragDrop(e,toIdx){{
  e.preventDefault();
  if(dragSrcIdx>=0&&dragSrcIdx!==toIdx) performDrop(dragSrcIdx,toIdx);
  dragEnd();
}}

// ── Touch drag (mobile/iPhone) ────────────────────────────────────────
let tdActive=false,tdFrom=-1,tdTo=-1,tdClone=null,tdRow=null;
function tdStart(e,idx,handle){{
  e.preventDefault();e.stopPropagation();
  tdActive=true;tdFrom=idx;tdTo=idx;
  tdRow=handle.closest('.sound-row');
  tdRow.classList.add('dragging');
  const r=tdRow.getBoundingClientRect();
  tdClone=tdRow.cloneNode(true);
  tdClone.style.cssText=`position:fixed;pointer-events:none;opacity:0.8;z-index:9999;width:${{r.width}}px;left:${{r.left}}px;top:${{r.top}}px;border-radius:10px;`;
  document.body.appendChild(tdClone);
}}
document.addEventListener('touchmove',e=>{{
  if(!tdActive)return;
  e.preventDefault();
  const t=e.touches[0];
  if(tdClone)tdClone.style.top=(t.clientY-tdClone.offsetHeight/2)+'px';
  tdClone.style.display='none';
  const el=document.elementFromPoint(t.clientX,t.clientY);
  tdClone.style.display='';
  const targetRow=el?.closest('.sound-row[data-idx]');
  document.querySelectorAll('.sound-row.drag-over').forEach(r=>r.classList.remove('drag-over'));
  if(targetRow&&targetRow!==tdRow){{
    tdTo=parseInt(targetRow.dataset.idx);
    targetRow.classList.add('drag-over');
  }}
}},{{passive:false}});
document.addEventListener('touchend',()=>{{
  if(!tdActive)return;
  tdActive=false;
  if(tdClone){{tdClone.remove();tdClone=null;}}
  document.querySelectorAll('.sound-row').forEach(r=>r.classList.remove('dragging','drag-over'));
  if(tdFrom>=0&&tdTo>=0&&tdFrom!==tdTo) performDrop(tdFrom,tdTo);
  tdFrom=-1;tdTo=-1;tdRow=null;
}});

// ── Shared drop logic ─────────────────────────────────────────────────
function performDrop(fromIdx,toIdx){{
  const all=buildAllItems();
  const fromId=filteredItems[fromIdx].id;
  const toId=filteredItems[toIdx].id;
  const fromAllIdx=all.findIndex(x=>x.id===fromId);
  const[moved]=all.splice(fromAllIdx,1);
  const toAllIdx=all.findIndex(x=>x.id===toId);
  all.splice(toAllIdx,0,moved);
  saveCustomOrder(all.map(x=>x.id));
  renderSoundList();
}}

// ── Context panel (Territory × Time × Season) ──────────────────────────
function getTerritoryMode(){{return localStorage.getItem('territory')||'home';}}
function setTerritoryMode(m){{localStorage.setItem('territory',m);renderContextPanel();}}

function getTimeOfDay(){{
  const h=new Date().getHours();
  if(h>=5&&h<8)   return{{id:'dawn',     label:'🌅 Dawn',          note:'High activity — territorial'}};
  if(h>=8&&h<12)  return{{id:'morning',  label:'☀️ Morning',       note:'Foraging & social contact'}};
  if(h>=12&&h<15) return{{id:'midday',   label:'🌤 Midday',        note:'Rest period — quieter'}};
  if(h>=15&&h<18) return{{id:'afternoon',label:'🌇 Afternoon',     note:'Pre-roost foraging'}};
  if(h>=18&&h<21) return{{id:'evening',  label:'🌆 Evening roost', note:'Mass flight to communal roost'}};
  return                 {{id:'night',   label:'🌙 Night',         note:'Roosting'}};
}}
function getSeason(){{
  const m=new Date().getMonth();
  if(m<=1||m===11)return{{label:'❄️ Winter',note:'Cooperative flocking, resource scarcity'}};
  if(m<=3)        return{{label:'🌱 Spring',note:'Territory establishment & pair bonding'}};
  if(m<=7)        return{{label:'🌿 Summer',note:'Breeding & juvenile training'}};
  return                {{label:'🍂 Autumn',note:'Juvenile social learning'}};
}}

const CTX_TIPS={{
  home:{{
    dawn:     {{tip:"Your regulars are active. Contact calls work well — you're a known face. Match their morning energy.",cls:'home'}},
    morning:  {{tip:"Established trust allows closer interaction. Mirror their contact calls to reinforce the bond.",cls:'home'}},
    midday:   {{tip:"Lower activity. Good time to offer food quietly — no sounds needed.",cls:'home'}},
    afternoon:{{tip:"Pre-roost foraging. Food calls are effective. Your crows know the reward signal.",cls:'home'}},
    evening:  {{tip:"⚠ Your home crows join the evening roost flight. Stay passive and watch — don't disrupt the movement.",cls:'caution'}},
    night:    {{tip:"Crows are roosting. Field work not recommended until dawn.",cls:''}},
  }},
  new:{{
    dawn:     {{tip:"Unknown territory. Stay completely passive. Let the crows notice you first — no sounds yet.",cls:'new-t'}},
    morning:  {{tip:"Assess the local birds before playing anything. If they approach neutrally, try one soft contact call.",cls:'new-t'}},
    midday:   {{tip:"Quiet period — ideal for passive observation. Watch the social hierarchy and dominant individuals.",cls:'new-t'}},
    afternoon:{{tip:"If no alarm response so far, try one gentle contact call. Watch body posture carefully.",cls:'new-t'}},
    evening:  {{tip:"⚠ Strangers near a communal roost can panic the entire flock. Observe only — absolutely no sounds.",cls:'caution'}},
    night:    {{tip:"Crows are roosting. Come back at dawn.",cls:''}},
  }},
}};

function renderContextPanel(){{
  const el=document.getElementById('ctxPanel');
  if(!el) return;
  const show=(activeTab==='record');
  el.style.display=show?'block':'none';
  if(!show) return;
  const mode=getTerritoryMode();
  const time=getTimeOfDay();
  const season=getSeason();
  const tipData=(CTX_TIPS[mode]||{{}})[time.id]||{{tip:'',cls:''}};
  el.innerHTML=`
    <div class="ctx-row">
      <button class="ctx-mode-btn home ${{mode==='home'?'active':''}}" onclick="setTerritoryMode('home')">🏠 Home Quarter</button>
      <button class="ctx-mode-btn new-t ${{mode==='new'?'active':''}}" onclick="setTerritoryMode('new')">🌲 New Territory</button>
      <span class="ctx-time-badge" title="${{time.note}}">${{time.label}}</span>
    </div>
    <div class="ctx-row" style="margin-top:-4px;margin-bottom:${{tipData.tip?'4px':'10px'}}">
      <span class="ctx-season">${{season.label}} · ${{season.note}}</span>
    </div>
    ${{tipData.tip?`<div class="ctx-tip ${{tipData.cls}}">${{tipData.tip}}</div>`:''}}
  `;
}}

// ── Help system ────────────────────────────────────────────────────────
const HELP={{
  library:{{title:'Library',body:`<p>Browse and play all crow sounds.</p><ul>
<li><b>SYN</b> (amber) — Synthesized via Web Audio — no audio file needed</li>
<li><b>XC</b> (blue) — Real field recordings from xeno-canto.org</li>
<li><b>⚠</b> (red) — Alarm / danger calls — use with care near crows</li></ul>
<p>Tap a row to open the player. Drag the <b>⠿</b> handle on the left to reorder rows — your order is saved automatically. Use the filter buttons above to show only one type.</p>
<hr style="border-color:var(--border);margin:14px 0">
<p><b>📱 Install on iPhone</b></p>
<ol style="padding-left:18px;margin:8px 0">
<li>Open this page in <b>Safari</b></li>
<li>Tap the <b>Share</b> button <span style="font-family:monospace;background:var(--s2);padding:1px 5px;border-radius:4px">⎙</span> at the bottom of the screen</li>
<li>Scroll down and tap <b>"Add to Home Screen"</b></li>
<li>Name it <b>CrowTalk</b> → tap <b>Add</b></li>
</ol>
<p style="color:var(--t3);font-size:13px;margin-top:6px">The app works fully offline once installed — no internet required.</p>`}},
  record:{{title:'Record',body:`<p>Record crow sounds in the field with automatic GPS tagging.</p><ul>
<li>Tap the red button to start / stop a recording</li>
<li>After recording, set category, phonetics, and the crow's reaction</li>
<li>GPS coordinates are attached automatically if location access is granted</li>
<li>All recordings are stored locally on your device (IndexedDB)</li></ul>`}},
  dagbok:{{title:'Field Journal',body:`<p>Log your crow observation sessions.</p><ul>
<li>Add entries with date, place, weather, and crow activity notes</li>
<li>Use the monthly view to see your session history</li>
<li>Entries are stored locally — export them from the <b>Data</b> tab</li></ul>`}},
  teori:{{title:'Theory',body:`<p>A guide to crow communication science.</p><ul>
<li>Learn the main call categories: contact, alarm, food, play, and more</li>
<li>Understand crow body language and social signals</li>
<li>Use as a reference when classifying your own recordings</li></ul>`}},
  data:{{title:'Data',body:`<p>Statistics and data export for your field sessions.</p><ul>
<li>View counts of recordings and journal entries</li>
<li>Export all data as JSON for analysis or sharing</li>
<li>JSON format is compatible with bird call classification models</li></ul>`}},
}};
function showHelp(){{
  const h=HELP[activeTab]||{{title:'Help',body:'<p>No help available.</p>'}};
  document.getElementById('helpTitle').textContent=h.title;
  document.getElementById('helpBody').innerHTML=h.body;
  document.getElementById('helpOverlay').style.display='flex';
}}
function closeHelp(){{document.getElementById('helpOverlay').style.display='none';}}

// ═══════════════════════════════════════════════════════════════════
// SOUND LIST
// ═══════════════════════════════════════════════════════════════════
let filteredItems = [];

function renderSoundList() {{
  filteredItems = getFilteredItems();
  const list = document.getElementById('soundList');
  if (!filteredItems.length) {{
    list.innerHTML = '<div class="empty-state">No sounds match the filter</div>';
    return;
  }}
  const lbl = getLabels();
  list.innerHTML = filteredItems.map((item,i) => {{
    const catLabel = CATEGORIES.find(c=>c.id===item.cat)?.label || '';
    const hasCat   = !!item.cat;
    const isDanger = item.danger;
    return `<div class="sound-row type-${{item.type}} ${{isDanger?'danger':''}}" id="row-${{item.id}}" data-idx="${{i}}"
      draggable="true"
      ondragstart="dragStart(event,${{i}})" ondragover="dragOver(event,${{i}})" ondrop="dragDrop(event,${{i}})" ondragend="dragEnd()"
      onclick="openPlayer(${{i}})">
      <div class="drag-handle" ontouchstart="tdStart(event,${{i}},this)">
        <svg viewBox="0 0 10 16" fill="currentColor" width="10" height="16">
          <circle cx="2" cy="2" r="1.5"/><circle cx="8" cy="2" r="1.5"/>
          <circle cx="2" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/>
          <circle cx="2" cy="14" r="1.5"/><circle cx="8" cy="14" r="1.5"/>
        </svg>
      </div>
      <div class="mini-play" id="mp-${{item.id}}">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
      </div>
      <div class="type-badge ${{isDanger?'danger':item.type}}">${{isDanger?'⚠':item.type==='real'?'XC':item.type==='field'?'🎙':'SYN'}}</div>
      <div class="sound-info">
        <div class="sound-name">${{item.name}}${{isDanger?' ⚠️':''}}</div>
        <div class="sound-meta">${{item.sub}}</div>
      </div>
      ${{isDanger
        ? `<span class="sound-cat danger-cat">Warning</span>`
        : hasCat ? `<span class="sound-cat labeled">${{catLabel}}</span>` : `<span class="sound-cat"></span>`
      }}
    </div>`;
  }}).join('');
}}

// ═══════════════════════════════════════════════════════════════════
// ALARM SAFETY MODAL
// ═══════════════════════════════════════════════════════════════════
let alarmModalCallback = null;

function showAlarmModal(synthName, callback) {{
  const modal = document.getElementById('alarmModal');
  const isAlarm = synthName === 'alarm';
  document.getElementById('alarmModalTitle').textContent =
    isAlarm ? '⚠️ Alarm call – read this!' : '⚠️ Mobbing call – read this!';
  document.getElementById('alarmModalBody').textContent = isAlarm
    ? 'Three fast alarm calls signal "dangerous enemy". Crows that hear this directed at you may classify you as a threat and remember it for years.'
    : 'Five or more mobbing calls rally the flock against a threat. If crows associate this sound with you, it can disrupt all future contact.';
  document.getElementById('alarmModalScience').innerHTML = isAlarm
    ? '🔬 Research shows crows identify and remember "dangerous faces" for up to 5 years (Marzluff et al., 2010). Negative associations spread to the entire flock.'
    : '🔬 Mobbing behaviour activates the crow&#39;s "threat memory". The reaction is stronger and longer-lasting than alarm and can affect your relationship with the entire local population.';
  alarmModalCallback = callback;
  modal.classList.add('open');
}}

document.getElementById('alarmCancel').onclick = () => {{
  document.getElementById('alarmModal').classList.remove('open');
  alarmModalCallback = null;
}};
document.getElementById('alarmConfirm').onclick = () => {{
  document.getElementById('alarmModal').classList.remove('open');
  if (alarmModalCallback) alarmModalCallback();
  alarmModalCallback = null;
}};

// ═══════════════════════════════════════════════════════════════════
// FIELD PLAYER
// ═══════════════════════════════════════════════════════════════════
const mainAudio = document.getElementById('mainAudio');
let playerIdx   = 0;
let loopOn      = false;
let progInt     = null;
let playerRecArmed = false;
let playerRecChunks = [];
let playerMediaRec  = null;

function openPlayer(idx) {{
  playerIdx = idx;
  loadPlayerItem();
  document.getElementById('playerOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function loadPlayerItem() {{
  const item = filteredItems[playerIdx];
  if (!item) return;
  stopMain();

  // Header
  document.getElementById('playerPos').textContent = `${{playerIdx+1}} / ${{filteredItems.length}}`;
  const badge = document.getElementById('playerBadge');
  if (item.danger) {{
    badge.textContent = '⚠️ Dangerous sound';
    badge.className   = 'player-type-badge danger';
  }} else if (item.type === 'real') {{
    badge.textContent = '🔵 Real recording';
    badge.className   = 'player-type-badge real';
  }} else if (item.type === 'field') {{
    badge.textContent = '🎙 My recording';
    badge.className   = 'player-type-badge field';
  }} else {{
    badge.textContent = '🟡 Synthetic';
    badge.className   = 'player-type-badge synth';
  }}
  document.getElementById('playerTitle').textContent = item.name;
  document.getElementById('playerSub').textContent   = item.sub;

  // Spectrogram
  const sonoWrap = document.getElementById('sonoWrap');
  const sonoImg  = document.getElementById('sonoImg');
  const sonoSrc  = item.type === 'real' ? item.audio?.sono : null;
  if (sonoSrc) {{
    sonoImg.src = 'data:image/png;base64,' + sonoSrc;
    sonoWrap.style.display = 'block';
    document.getElementById('sonoPlayhead').style.left = '0px';
  }} else {{
    sonoWrap.style.display = 'none';
  }}

  // Big play button styling for danger sounds
  const bigPlay = document.getElementById('bigPlay');
  bigPlay.classList.toggle('danger-play', item.danger && !item.danger); // reset initially

  // Progress bar: only for real audio
  document.getElementById('playerProgress').style.display = item.type==='real' ? 'block' : 'none';

  // Label chips (only for real recordings)
  const lbl = getLabels();
  const savedCat      = item.type==='real' ? (lbl[item.id]?.category||'') : item.cat;
  const savedNotes    = item.type==='real' ? (lbl[item.id]?.notes||'') : '';
  const savedName     = item.type==='real' ? (lbl[item.id]?.name || item.id) : '';
  const savedPhonetic = item.type==='real' ? (lbl[item.id]?.phonetic||'') : '';
  const savedTolkning = item.type==='real' ? (lbl[item.id]?.tolkning||'') : '';
  document.getElementById('playerLabelSection').style.display = item.type==='real' ? 'block' : 'none';
  if (item.type==='real') {{
    document.getElementById('playerNameInput').value = savedName !== item.id ? savedName : '';
    document.getElementById('playerNameInput').placeholder = item.id + ' — custom name...';
    document.getElementById('playerPhonetic').value = savedPhonetic;
    document.getElementById('playerTolkning').value = savedTolkning;
    document.getElementById('playerChips').innerHTML = CATEGORIES.map(c => `
      <button class="player-chip ${{c.id===savedCat?'selected':''}}" data-cat="${{c.id}}"
        onclick="selectPlayerChip(this)">${{c.label}}</button>`).join('');
    document.getElementById('playerNotes').value = savedNotes;
  }}

  // Big play button reset
  setBigPlay(false);
  document.getElementById('progFill').style.width  = '0%';
  document.getElementById('progCur').textContent   = '0:00';
  document.getElementById('progDur').textContent   = '0:00';

  // Kommunikationsguide
  updateCommGuide(item);
}}

function selectPlayerChip(btn) {{
  document.querySelectorAll('#playerChips .player-chip').forEach(c=>c.classList.remove('selected'));
  btn.classList.add('selected');
}}

function savePlayerLabel() {{
  const item = filteredItems[playerIdx];
  if (!item || item.type!=='real') return;
  const cat      = document.querySelector('#playerChips .player-chip.selected')?.dataset.cat || '';
  const notes    = document.getElementById('playerNotes').value.trim();
  const nameRaw  = document.getElementById('playerNameInput').value.trim();
  const phonetic = document.getElementById('playerPhonetic').value.trim();
  const tolkning = document.getElementById('playerTolkning').value.trim();
  const lbl      = getLabels();
  const name     = nameRaw || lbl[item.id]?.name || '';
  lbl[item.id]   = {{category:cat, notes, name, phonetic, tolkning, ts:Date.now()}};
  saveLabels(lbl);
  if (name) document.getElementById('playerTitle').textContent = name;
  if (phonetic) document.getElementById('playerSub').textContent = phonetic;
  renderSoundList();
  renderFilterBar();
  updateCommGuide(filteredItems[playerIdx]);
}}

// ── Kommunikationsguide ──────────────────────────────────────────────
const COMM_GUIDE_DATA = {{
  kontaktrop: {{
    text: 'The contact call signals presence and willingness to communicate — the crow is relaxed and social. It is the safest call to start with.',
    suggest: [
      {{label:'Reply with contact call', sound:'syn_contact', tip:'Match the rhythm. Wait 3–5 sec after each call.'}},
      {{label:'Play content call if crow approached', sound:'syn_content', tip:'A softer tone signals you are harmless.'}},
    ]
  }},
  matrop: {{
    text: 'The food call triggers curiosity and recruitment — crows share food sources within the flock. Best played near a visible food attraction.',
    suggest: [
      {{label:'Reply with contact call', sound:'syn_contact', tip:'Make contact with the crow without escalating.'}},
      {{label:'Play food call again', sound:'syn_food', tip:'Repeat if the crow looks interested but hesitates.'}},
    ]
  }},
  alarm: {{
    text: '⚠️ The alarm call means the crow perceives a threat. Playing it without context risks frightening the crow and the entire flock permanently.',
    suggest: [
      {{label:'Wait — play nothing', sound:null, tip:'Let the crow calm down. Wait at least 5 minutes.'}},
      {{label:'Contact call once crow has calmed', sound:'syn_contact', tip:'Re-establish trust with a calm contact call.'}},
    ]
  }},
  mobbing: {{
    text: '⚠️ The mobbing call rallies the flock against a shared threat. Only use if you want to study flock response — it can disturb crows for hours.',
    suggest: [
      {{label:'Wait and observe', sound:null, tip:'Document how many gather and from which direction.'}},
    ]
  }},
  rassel: {{
    text: 'The rattle is intimate — used at close range between crows that know each other. Effective if you have built trust over time.',
    suggest: [
      {{label:'Reply with contact call', sound:'syn_contact', tip:'Match the intimacy level, do not escalate to alarm.'}},
      {{label:'Play content call', sound:'syn_content', tip:'Signals you are calm and friendly.'}},
    ]
  }},
  ovrigt: {{
    text: 'Unclassified sound. Compare rhythm and pitch against known call categories. Juveniles and individuals with regional dialects often deviate.',
    suggest: [
      {{label:'Start with contact call', sound:'syn_contact', tip:'The safest choice in an unknown context.'}},
    ]
  }},
  '': {{
    text: 'Categorise the recording to receive communication suggestions.',
    suggest: []
  }}
}};

function updateCommGuide(item) {{
  const guide = document.getElementById('commGuide');
  if (!item || item.type === 'synth') {{ guide.style.display='none'; return; }}
  guide.style.display='block';
  const lbl = getLabels();
  const cat = lbl[item.id]?.category || '';
  const data = COMM_GUIDE_DATA[cat] || COMM_GUIDE_DATA[''];
  document.getElementById('commText').textContent = data.text;
  const sug = document.getElementById('commSuggest');
  if (data.suggest.length === 0) {{ sug.innerHTML=''; return; }}
  sug.innerHTML = '<div style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Try next</div>' +
    data.suggest.map(s => `
      <div style="background:var(--s3);border-radius:8px;padding:10px 12px;margin-bottom:8px">
        ${{s.sound ? `<button onclick="closePlayer();setTimeout(()=>jumpToSound('${{s.sound}}'),200)"
          style="background:var(--green);color:#000;border:none;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;margin-bottom:6px;cursor:pointer">
          ▶ ${{s.label}}</button>` :
          `<span style="color:var(--amber);font-size:12px;font-weight:600">⏸ ${{s.label}}</span>`}}
        <div style="font-size:11px;color:var(--t3);margin-top:4px">${{s.tip}}</div>
      </div>`).join('');
}}

function jumpToSound(synthId) {{
  // Hitta och öppna ett specifikt synth-ljud i spelaren
  const idx = filteredItems.findIndex(it => it.id === synthId);
  if (idx >= 0) {{ playerIdx = idx; loadPlayerItem(); openPlayer(); }}
  else {{
    // Kliv ur filter och sök globalt
    activeFilter=''; renderFilterBar(); renderSoundList();
    setTimeout(()=>{{
      const idx2 = filteredItems.findIndex(it => it.id === synthId);
      if (idx2 >= 0) {{ playerIdx=idx2; loadPlayerItem(); openPlayer(); }}
    }}, 100);
  }}
}}

function toggleCommGuide() {{
  const body = document.getElementById('commGuideBody');
  const arrow = document.getElementById('commArrow');
  const open = body.style.display === 'block';
  body.style.display = open ? 'none' : 'block';
  arrow.style.transform = open ? '' : 'rotate(180deg)';
}}

function closePlayer() {{
  stopMain();
  stopPlayerRec();
  document.getElementById('playerOverlay').classList.remove('open');
  document.body.style.overflow = '';
  renderSoundList();
}}
document.getElementById('playerClose').onclick = closePlayer;

function setBigPlay(playing) {{
  const btn  = document.getElementById('bigPlay');
  const icon = document.getElementById('bigPlayIcon');
  if (playing) {{
    btn.classList.remove('paused');
    icon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  }} else {{
    btn.classList.add('paused');
    icon.innerHTML = '<path d="M8 5v14l11-7z"/>';
  }}
}}

document.getElementById('bigPlay').onclick = handleBigPlayClick;

// Cache blob URLs so we don't re-convert base64 every tap
const blobUrlCache = {{}};
function getBlobUrl(item) {{
  if (blobUrlCache[item.id]) return blobUrlCache[item.id];
  // atob → Uint8Array → Blob → Object URL (works reliably on iOS Safari)
  const b64    = item.audio.audio;
  const mime   = item.audio.mime;
  const raw    = atob(b64);
  const bytes  = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const blob   = new Blob([bytes], {{type: mime}});
  const url    = URL.createObjectURL(blob);
  blobUrlCache[item.id] = url;
  return url;
}}

function handleBigPlayClick() {{
  const item = filteredItems[playerIdx];
  if (!item) return;
  if (item.type === 'synth') {{
    const synthKey = item.synth.id.replace('syn_','');
    if (DANGER_SYNTHS.has(synthKey)) {{
      showAlarmModal(synthKey, () => playSynth(synthKey));
    }} else {{
      playSynth(synthKey);
    }}
    return;
  }}
  // Real audio – use Blob URL for iOS Safari compatibility
  if (mainAudio.paused) {{
    const blobUrl = getBlobUrl(item);
    if (mainAudio.src !== blobUrl) {{
      mainAudio.src = blobUrl;
      mainAudio.load();
    }}
    mainAudio.play().catch(e => console.warn('play failed:', e));
    setBigPlay(true);
    startProgTimer();
  }} else {{
    mainAudio.pause();
    setBigPlay(false);
    clearInterval(progInt);
  }}
}}

function stopMain() {{
  clearInterval(progInt); progInt=null;
  mainAudio.pause();
  mainAudio.src = '';
  setBigPlay(false);
}}

function startProgTimer() {{
  clearInterval(progInt);
  progInt = setInterval(() => {{
    if (!mainAudio.duration) return;
    const pct = (mainAudio.currentTime/mainAudio.duration)*100;
    document.getElementById('progFill').style.width = pct + '%';
    document.getElementById('progCur').textContent  = fmt(mainAudio.currentTime);
    document.getElementById('progDur').textContent  = fmt(mainAudio.duration);
    // Animate spectrogram playhead
    const sw = document.getElementById('sonoWrap');
    if (sw && sw.style.display !== 'none') {{
      document.getElementById('sonoPlayhead').style.left = pct + '%';
    }}
  }}, 100);
}}

mainAudio.onended = () => {{
  if (loopOn) {{ mainAudio.currentTime=0; mainAudio.play(); }}
  else {{ setBigPlay(false); clearInterval(progInt); }}
}};

document.getElementById('progTrack').onclick = e => {{
  if (!mainAudio.duration) return;
  const r = e.currentTarget.getBoundingClientRect();
  mainAudio.currentTime = ((e.clientX-r.left)/r.width)*mainAudio.duration;
}};

document.getElementById('volSlider').oninput = e => {{ mainAudio.volume = e.target.value; }};

function toggleLoop() {{
  loopOn = !loopOn;
  document.getElementById('loopBtn').classList.toggle('on', loopOn);
}}

function prevSound() {{
  if (playerIdx > 0) {{ playerIdx--; loadPlayerItem(); }}
}}
function nextSound() {{
  if (playerIdx < filteredItems.length-1) {{ playerIdx++; loadPlayerItem(); }}
}}

// Swipe gestures on overlay
(function() {{
  const el = document.getElementById('playerOverlay');
  let sx=0, sy=0;
  el.addEventListener('touchstart', e=>{{ sx=e.touches[0].clientX; sy=e.touches[0].clientY; }}, {{passive:true}});
  el.addEventListener('touchend',   e=>{{
    const dx = e.changedTouches[0].clientX - sx;
    const dy = Math.abs(e.changedTouches[0].clientY - sy);
    if (Math.abs(dx) > 60 && dy < 80) {{
      if (dx < 0) nextSound(); else prevSound();
    }}
  }}, {{passive:true}});
}})();

// Record-in-player (quick field rec while player is open)
async function toggleFieldRecFromPlayer() {{
  const btn = document.getElementById('fieldRecToggle');
  if (!playerRecArmed) {{
    try {{
      const stream = await navigator.mediaDevices.getUserMedia({{audio:true}});
      const mimeType = ['audio/webm;codecs=opus','audio/webm','audio/ogg','audio/mp4']
        .find(m=>MediaRecorder.isTypeSupported(m)) || '';
      playerMediaRec  = new MediaRecorder(stream, mimeType?{{mimeType}}:{{}});
      playerRecChunks = [];
      playerMediaRec.ondataavailable = e=>{{ if(e.data.size>0) playerRecChunks.push(e.data); }};
      playerMediaRec.onstop = async () => {{
        const blob = new Blob(playerRecChunks, {{type:playerRecChunks[0]?.type||'audio/webm'}});
        const currentItem = filteredItems[playerIdx];
        const context = currentItem ? currentItem.name : '';
        await dbAdd('recordings', {{blob, category:'', notes:'Response to: '+context, ts:Date.now(), duration:0}});
        stream.getTracks().forEach(t=>t.stop());
        switchTab('record');
        closePlayer();
        renderField();
      }};
      playerMediaRec.start(100);
      playerRecArmed = true;
      btn.classList.add('on');
    }} catch(err) {{ alert('Microphone access denied'); }}
  }} else {{
    stopPlayerRec();
  }}
}}
function stopPlayerRec() {{
  if (playerMediaRec && playerMediaRec.state==='recording') playerMediaRec.stop();
  playerRecArmed = false;
  document.getElementById('fieldRecToggle')?.classList.remove('on');
}}

// ═══════════════════════════════════════════════════════════════════
// SYNTHETIC SOUNDS
// ═══════════════════════════════════════════════════════════════════
let audioCtx = null;
function initACtx() {{
  if (!audioCtx) audioCtx = new (window.AudioContext||window.webkitAudioContext)();
  if (audioCtx.state==='suspended') audioCtx.resume();
  return audioCtx;
}}
function caw(freq=450, dur=0.2) {{
  const c=initACtx(), now=c.currentTime;
  const osc=c.createOscillator(); osc.type='sawtooth';
  osc.frequency.setValueAtTime(freq,now);
  osc.frequency.linearRampToValueAtTime(freq*1.2,now+dur*0.2);
  osc.frequency.linearRampToValueAtTime(freq*0.9,now+dur);
  const gain=c.createGain();
  gain.gain.setValueAtTime(0,now);
  gain.gain.linearRampToValueAtTime(0.18,now+0.01);
  gain.gain.exponentialRampToValueAtTime(0.001,now+dur);
  osc.connect(gain); gain.connect(c.destination);
  osc.start(now); osc.stop(now+dur);
}}
function rattle() {{
  const c=initACtx(), now=c.currentTime;
  const osc=c.createOscillator(); osc.type='square'; osc.frequency.value=150;
  const gain=c.createGain();
  gain.gain.setValueAtTime(0.12,now);
  gain.gain.exponentialRampToValueAtTime(0.001,now+0.03);
  osc.connect(gain); gain.connect(c.destination);
  osc.start(now); osc.stop(now+0.03);
}}
let synthBusy=false;
function playSynth(id) {{
  if(synthBusy) return; synthBusy=true;
  const patterns={{
    contact:()=>{{ caw(380,0.35); setTimeout(()=>caw(400,0.3),520); return 950; }},
    food:   ()=>{{ for(let i=0;i<3;i++) setTimeout(()=>caw(500,0.12),i*180); return 620; }},
    alarm:  ()=>{{ for(let i=0;i<3;i++) setTimeout(()=>caw(600,0.15),i*160); return 580; }},
    mob:    ()=>{{ for(let i=0;i<5;i++) setTimeout(()=>caw(650+i*15,0.11),i*130); return 780; }},
    content:()=>{{ for(let i=0;i<4;i++) setTimeout(()=>caw(420-i*10,0.2),i*350); return 1500; }},
    click:  ()=>{{ for(let i=0;i<5;i++) setTimeout(()=>rattle(),i*80); return 480; }},
  }};
  const dur=patterns[id]?.() || 500;
  setBigPlay(true);
  setTimeout(()=>{{ synthBusy=false; setBigPlay(false); }}, dur+150);
}}

// ═══════════════════════════════════════════════════════════════════
// RECORD TAB
// ═══════════════════════════════════════════════════════════════════
let mediaRec=null, recChunks=[], recStart=0, recTimerInt=null, pendingBlob=null, pendingAudio=null;
let pendingGPS=null, pendingRecStart=null;

// GPS helper – hämtar koordinater och visar dem
function fetchGPS(callback) {{
  if (!navigator.geolocation) {{ callback(null, 'GPS not available'); return; }}
  navigator.geolocation.getCurrentPosition(
    pos => callback({{lat: pos.coords.latitude.toFixed(6), lon: pos.coords.longitude.toFixed(6), acc: Math.round(pos.coords.accuracy)}}, null),
    err => callback(null, 'GPS denied or timed out'),
    {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
  );
}}
const fieldAudio = document.getElementById('fieldAudio');
let fieldPlaying=null, fieldTimerInt=null, fieldURL=null;

document.getElementById('recordBtn').addEventListener('click',()=>{{
  if(mediaRec&&mediaRec.state==='recording') stopTabRecording();
  else startTabRecording();
}});

async function startTabRecording() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{audio:true}});
    const mimeType=['audio/webm;codecs=opus','audio/webm','audio/ogg','audio/mp4'].find(m=>MediaRecorder.isTypeSupported(m))||'';
    mediaRec=new MediaRecorder(stream,mimeType?{{mimeType}}:{{}});
    recChunks=[];
    pendingGPS=null;
    pendingRecStart = new Date();
    // Försök hämta GPS i bakgrunden medan användaren spelar in
    fetchGPS((gps, err) => {{ pendingGPS = gps; }});
    mediaRec.ondataavailable=e=>{{if(e.data.size>0)recChunks.push(e.data);}};
    mediaRec.onstop=finishTabRecording;
    mediaRec.start(100); recStart=Date.now();
    document.getElementById('recordBtn').classList.add('armed');
    document.getElementById('recHint').textContent='Tap to stop · fetching GPS…';
    document.getElementById('recTimer').classList.add('armed');
    recTimerInt=setInterval(()=>{{document.getElementById('recTimer').textContent=fmt((Date.now()-recStart)/1000);}},200);
  }} catch(err) {{ alert('Microphone access denied: '+err.message); }}
}}
function stopTabRecording() {{
  if(mediaRec) {{mediaRec.stop(); mediaRec.stream.getTracks().forEach(t=>t.stop());}}
  clearInterval(recTimerInt);
  document.getElementById('recordBtn').classList.remove('armed');
  document.getElementById('recTimer').textContent='0:00';
  document.getElementById('recTimer').classList.remove('armed');
  document.getElementById('recHint').textContent='Tap to record';
}}
function finishTabRecording() {{
  const blob=new Blob(recChunks,{{type:recChunks[0]?.type||'audio/webm'}});
  pendingBlob=blob;
  pendingAudio=new Audio(URL.createObjectURL(blob));
  showPending();
}}
const CROW_RESPONSES = [
  {{id:'approached', label:'🐦 Approached'}},
  {{id:'answered',   label:'🔊 Responded'}},
  {{id:'ignored',    label:'😐 Ignored'}},
  {{id:'fled',       label:'✈️ Flew away'}},
  {{id:'landed',     label:'🌿 Landed'}},
  {{id:'group',      label:'👥 Flock gathered'}},
];

function showPending() {{
  const zone=document.getElementById('pendingZone');
  zone.style.display='block';
  const chips=CATEGORIES.map(c=>`<button class="player-chip" data-cat="${{c.id}}" onclick="selectPendingChip(this)">${{c.label}}</button>`).join('');
  const respChips=CROW_RESPONSES.map(r=>`<button class="player-chip" data-resp="${{r.id}}" onclick="selectRespChip(this)">${{r.label}}</button>`).join('');
  const ts = pendingRecStart ? pendingRecStart.toLocaleString('sv-SE',{{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}}) : '';
  const gpsStr = pendingGPS ? `${{pendingGPS.lat}}, ${{pendingGPS.lon}} (±${{pendingGPS.acc}}m)` : '';
  zone.innerHTML=`<div class="pending-card">
    <div class="pending-title">🎙 New recording – review and label</div>
    ${{ts?`<div style="font-size:11px;color:var(--t3);margin-bottom:4px">🕐 ${{ts}}</div>`:''}}
    ${{gpsStr?`<div style="font-size:11px;color:var(--green);margin-bottom:8px">📍 ${{gpsStr}}</div>`:`<div style="font-size:11px;color:var(--t3);margin-bottom:8px">📍 GPS not available</div>`}}
    <div class="pending-play-row">
      <button class="pending-play" onclick="togglePending()">
        <svg id="ppIcon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
      </button>
      <div class="pending-prog"><div class="pending-fill" id="ppFill"></div></div>
      <div class="pending-time" id="ppTime">0:00</div>
    </div>
    <div style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Sound category</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px" id="pendingChips">${{chips}}</div>
    <input class="form-input" id="pendingPhonetic" type="text" placeholder="🔤 Phonetic: e.g. kra-kra-kraa…" style="width:100%;margin-bottom:8px;font-family:monospace">
    <input class="form-input" id="pendingTolkning" type="text" placeholder="💡 Meaning: e.g. Contact, slightly anxious…" style="width:100%;margin-bottom:8px">
    <input class="form-input" id="pendingPlace" type="text" placeholder="📍 Location (e.g. Södermalm, Stockholm)…" style="width:100%;margin-bottom:12px">
    <div style="font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Crow's reaction</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:10px" id="respChips">${{respChips}}</div>
    <textarea class="player-notes" id="pendingNotes" placeholder="Other notes, weather, context…" rows="2"></textarea>
    <div class="btn-row">
      <button class="discard-btn" onclick="discardPending()">Discard</button>
      <button class="keep-btn" onclick="savePending()">Save</button>
    </div>
  </div>`;
  if(pendingAudio) {{
    pendingAudio.ontimeupdate=()=>{{
      const pct=(pendingAudio.currentTime/(pendingAudio.duration||1))*100;
      const fill=document.getElementById('ppFill'), time=document.getElementById('ppTime');
      if(fill)fill.style.width=pct+'%'; if(time)time.textContent=fmt(pendingAudio.currentTime);
    }};
    pendingAudio.onended=()=>{{const i=document.getElementById('ppIcon');if(i)i.innerHTML='<path d="M8 5v14l11-7z"/>';}};
  }}
}}
function selectPendingChip(btn) {{
  document.querySelectorAll('#pendingChips .player-chip').forEach(c=>c.classList.remove('selected'));
  btn.classList.add('selected');
}}
function selectRespChip(btn) {{
  document.querySelectorAll('#respChips .player-chip').forEach(c=>c.classList.remove('selected'));
  btn.classList.add('selected');
}}
function togglePending() {{
  if(!pendingAudio)return;
  if(pendingAudio.paused){{pendingAudio.play();document.getElementById('ppIcon').innerHTML='<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';}}
  else{{pendingAudio.pause();document.getElementById('ppIcon').innerHTML='<path d="M8 5v14l11-7z"/>';}}
}}
function discardPending() {{
  if(pendingAudio){{pendingAudio.pause();pendingAudio=null;}} pendingBlob=null;
  document.getElementById('pendingZone').style.display='none';
  document.getElementById('pendingZone').innerHTML='';
}}
async function savePending() {{
  const cat      = document.querySelector('#pendingChips .player-chip.selected')?.dataset.cat||'';
  const response = document.querySelector('#respChips .player-chip.selected')?.dataset.resp||'';
  const place    = document.getElementById('pendingPlace')?.value.trim()||'';
  const phonetic = document.getElementById('pendingPhonetic')?.value.trim()||'';
  const tolkning = document.getElementById('pendingTolkning')?.value.trim()||'';
  const notes    = document.getElementById('pendingNotes')?.value.trim()||'';
  await dbAdd('recordings',{{
    blob: pendingBlob,
    category: cat,
    phonetic,
    tolkning,
    response,
    place,
    notes,
    gps: pendingGPS,
    recTime: pendingRecStart?.toISOString()||null,
    ts: Date.now(),
    duration: pendingAudio?.duration||0
  }});
  discardPending(); renderField(); loadFieldItems();
}}

async function renderField() {{
  if (!db) {{
    document.getElementById('fieldList').innerHTML =
      '<div class="empty-state">Storage not available in this browser context</div>';
    return;
  }}
  const recs=await dbGetAll('recordings');
  const list=document.getElementById('fieldList');
  document.getElementById('fieldCount').textContent=recs.length?recs.length+' saved':'';
  if(!recs.length){{list.innerHTML='<div class="empty-state">No recordings yet</div>';return;}}
  list.innerHTML=[...recs].reverse().map(r=>{{
    const cat      = CATEGORIES.find(c=>c.id===r.category)?.label||'';
    const resp     = CROW_RESPONSES.find(x=>x.id===r.response)?.label||'';
    const date     = new Date(r.ts).toLocaleDateString('sv-SE',{{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}});
    const gpsStr   = r.gps ? `${{r.gps.lat}}, ${{r.gps.lon}}` : '';
    const placeStr = r.place || '';
    return `<div class="field-card" id="fc-${{r.id}}">
      <div class="field-head">
        <button class="field-play" onclick="toggleField('${{r.id}}')">
          <svg id="fpi-${{r.id}}" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        </button>
        <div class="field-info">
          <div class="field-id">🕐 ${{date}}${{placeStr?' · 📍'+placeStr:''}}</div>
          <div class="field-label-txt ${{cat?'':'empty'}}">${{cat||'Unlabelled'}}${{resp?' · '+resp:''}}</div>
          ${{r.phonetic?`<div style="font-size:12px;color:var(--green);font-family:monospace;margin-top:2px">${{r.phonetic}}</div>`:''}}
          ${{r.tolkning?`<div style="font-size:11px;color:var(--blue);margin-top:1px">💡 ${{r.tolkning}}</div>`:''}}
          ${{gpsStr?`<div style="font-size:10px;color:var(--t3);margin-top:1px">📍 ${{gpsStr}} (±${{r.gps.acc}}m)</div>`:''}}
          ${{r.notes?`<div style="font-size:11px;color:var(--t3);margin-top:1px">${{r.notes}}</div>`:''}}
        </div>
        <button class="field-del" onclick="deleteField(${{r.id}})">×</button>
      </div>
      <div class="field-prog">
        <div class="field-prog-track"><div class="field-prog-fill" id="fpf-${{r.id}}"></div></div>
        <div class="field-prog-time" id="fpt-${{r.id}}">${{fmt(r.duration||0)}}</div>
      </div>
    </div>`;
  }}).join('');
}}
async function toggleField(id) {{
  if(fieldPlaying===id){{stopField();return;}}
  stopField();
  const all=await dbGetAll('recordings'); const rec=all.find(r=>r.id===id);
  if(!rec?.blob)return;
  if(fieldURL)URL.revokeObjectURL(fieldURL);
  fieldURL=URL.createObjectURL(rec.blob);
  fieldAudio.src=fieldURL; fieldAudio.load(); fieldAudio.play().catch(()=>{{}});
  fieldPlaying=id;
  document.getElementById('fc-'+id)?.classList.add('playing');
  document.getElementById('fpi-'+id).innerHTML='<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  fieldTimerInt=setInterval(()=>{{
    if(!fieldAudio.duration)return;
    const pct=(fieldAudio.currentTime/fieldAudio.duration)*100;
    const fill=document.getElementById('fpf-'+id), time=document.getElementById('fpt-'+id);
    if(fill)fill.style.width=pct+'%'; if(time)time.textContent=fmt(fieldAudio.currentTime);
  }},100);
}}
function stopField() {{
  clearInterval(fieldTimerInt); fieldTimerInt=null;
  if(fieldPlaying){{
    document.getElementById('fc-'+fieldPlaying)?.classList.remove('playing');
    const icon=document.getElementById('fpi-'+fieldPlaying);
    if(icon)icon.innerHTML='<path d="M8 5v14l11-7z"/>';
  }}
  fieldAudio.pause(); fieldPlaying=null;
}}
fieldAudio.onended=stopField;
async function deleteField(id){{stopField();await dbDelete('recordings',id);renderField();}}

// ═══════════════════════════════════════════════════════════════════
// DAGBOK TAB
// ═══════════════════════════════════════════════════════════════════
let selectedWeather = '';
let selectedActivities = new Set();

// Home Quarter helpers
function getHQName(){{return localStorage.getItem('hq_name')||'';}}
function getJournalMode(){{return localStorage.getItem('journalMode')||'home';}}
function setJournalMode(m){{
  localStorage.setItem('journalMode',m);
  const isHome=m==='home';
  document.getElementById('hqDisplay').style.display=isHome?'flex':'none';
  document.getElementById('dbPlace').style.display=isHome?'none':'block';
  document.getElementById('terrHome').classList.toggle('active',isHome);
  document.getElementById('terrNew').classList.toggle('active',!isHome);
  const hq=getHQName();
  const lbl=document.getElementById('hqNameLbl');
  if(isHome){{
    lbl.textContent=hq||'(No Home Quarter set — tap ✏️ to set)';
    lbl.className=hq?'hq-name-lbl':'hq-name-lbl empty';
  }}
}}
function promptSetHQ(){{
  const cur=getHQName();
  const val=prompt('Enter your Home Quarter name / location:',cur);
  if(val!==null){{
    localStorage.setItem('hq_name',val.trim());
    setJournalMode('home');
  }}
}}

// Init date to today
function initDagbokForm() {{
  const d = document.getElementById('dbDate');
  if (d) d.value = new Date().toISOString().split('T')[0];

  // Weather buttons
  document.getElementById('weatherRow').querySelectorAll('.weather-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.weather-btn').forEach(b=>b.classList.remove('on'));
      selectedWeather = btn.dataset.w;
      btn.classList.add('on');
    }});
  }});

  // Activity chips
  document.getElementById('activityRow').querySelectorAll('.activity-chip').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const a = btn.dataset.a;
      if (selectedActivities.has(a)) {{
        selectedActivities.delete(a);
        btn.classList.remove('on');
      }} else {{
        selectedActivities.add(a);
        btn.classList.add('on');
      }}
    }});
  }});

  // Territory mode
  setJournalMode(getJournalMode());
}}

async function saveDagbok() {{
  const date   = document.getElementById('dbDate').value;
  const jMode  = getJournalMode();
  const place  = jMode==='home' ? getHQName() : document.getElementById('dbPlace').value.trim();
  const notes  = document.getElementById('dbNotes').value.trim();
  if (!place && !notes && !selectedActivities.size) {{
    alert('Please enter at least a location, activity, or note.');
    return;
  }}
  await dbAdd('dagbok', {{
    date, place, weather: selectedWeather,
    activities: [...selectedActivities],
    notes, ts: Date.now()
  }});
  // Reset form
  document.getElementById('dbPlace').value = '';
  document.getElementById('dbNotes').value = '';
  setJournalMode('home');
  document.querySelectorAll('.weather-btn').forEach(b=>b.classList.remove('on'));
  document.querySelectorAll('.activity-chip').forEach(b=>b.classList.remove('on'));
  selectedWeather = ''; selectedActivities.clear();
  renderDagbok();
}}

async function renderDagbok() {{
  if (!db) {{
    document.getElementById('dagbokList').innerHTML =
      '<div class="empty-state">Storage not available in this browser context</div>';
    return;
  }}
  const entries = await dbGetAll('dagbok');
  const list = document.getElementById('dagbokList');
  document.getElementById('dagbokCount').textContent = entries.length ? entries.length + ' entries' : '';
  if (!entries.length) {{
    list.innerHTML = '<div class="empty-state" style="padding:32px 16px">No entries yet</div>';
    return;
  }}
  list.innerHTML = [...entries].reverse().map(e => {{
    const dateStr = e.date
      ? new Date(e.date + 'T12:00:00').toLocaleDateString('sv-SE', {{weekday:'short',month:'short',day:'numeric'}})
      : new Date(e.ts).toLocaleDateString('sv-SE', {{month:'short',day:'numeric'}});
    const acts = (e.activities||[]).map(a =>
      `<span class="journal-activity-tag">${{a}}</span>`
    ).join('');
    return `<div class="journal-entry" id="je-${{e.id}}">
      <div class="journal-head">
        <div>
          <div class="journal-date">${{dateStr}}</div>
          <div class="journal-loc">${{e.place || '<em style="color:var(--t3)">No location given</em>'}}</div>
          <div class="journal-weather">${{e.weather||''}}</div>
        </div>
        <button class="journal-del" onclick="deleteDagbok(${{e.id}})">×</button>
      </div>
      ${{acts ? `<div class="journal-activities">${{acts}}</div>` : ''}}
      ${{e.notes ? `<div class="journal-notes">${{e.notes}}</div>` : ''}}
    </div>`;
  }}).join('');
}}

async function deleteDagbok(id) {{
  await dbDelete('dagbok', id);
  renderDagbok();
}}

// ═══════════════════════════════════════════════════════════════════
// DATA TAB
// ═══════════════════════════════════════════════════════════════════
async function renderData() {{
  const fieldRecs  = db ? await dbGetAll('recordings') : [];
  const dagbokRecs = db ? await dbGetAll('dagbok') : [];
  const lbl = getLabels();
  const libLabeled = Object.values(lbl).filter(l=>l.category).length;
  const tally={{}};
  CATEGORIES.forEach(c=>tally[c.id]=0);
  Object.values(lbl).forEach(l=>{{if(l.category&&tally[l.category]!==undefined)tally[l.category]++;}});
  fieldRecs.forEach(r=>{{if(r.category&&tally[r.category]!==undefined)tally[r.category]++;}});
  const maxC=Math.max(1,...Object.values(tally));
  const bars=CATEGORIES.map(c=>`<div class="stat-row">
    <div class="stat-label">${{c.label}}</div>
    <div class="stat-bar-wrap"><div class="stat-bar" style="width:${{(tally[c.id]/maxC*100).toFixed(0)}}%"></div></div>
    <div class="stat-count">${{tally[c.id]}}</div>
  </div>`).join('');
  document.getElementById('dataContent').innerHTML=`
    <div class="big-nums">
      <div class="big-num"><div class="big-num-val">${{libLabeled}}</div><div class="big-num-label">Labelled XC sounds</div></div>
      <div class="big-num"><div class="big-num-val">${{fieldRecs.length}}</div><div class="big-num-label">Field recordings</div></div>
      <div class="big-num"><div class="big-num-val">${{dagbokRecs.length}}</div><div class="big-num-label">Journal entries</div></div>
    </div>
    <div class="stat-card"><div class="stat-title">Distribution by category</div>${{bars}}</div>
    <div class="stat-card">
      <div class="stat-title">Science background</div>
      <div style="font-size:13px;color:var(--t2);line-height:1.8">
        <p><strong style="color:var(--green)">3 calls = alarm</strong> — fast, loud warning calls at a raptor</p>
        <p><strong style="color:var(--green)">5+ calls = mobbing</strong> — mobilises the flock <em style="color:var(--t3)">(Corvid Research)</em></p>
        <p><strong style="color:var(--amber)">Shorter calls near food</strong> — avoids attracting competitors <em style="color:var(--t3)">(Pendergraft & Marzluff, 2019)</em></p>
        <p><strong style="color:var(--amber)">Counting</strong> — plans 1–4 calls before vocalising <em style="color:var(--t3)">(Science, 2024)</em></p>
        <p><strong style="color:var(--blue)">Regional dialects</strong> — measurable acoustic differences between populations</p>
      </div>
    </div>
    <button class="export-btn" onclick="exportData()">⬇ Export all data as JSON</button>`;
}}
async function exportData() {{
  const fieldRecs  = await dbGetAll('recordings');
  const dagbokRecs = await dbGetAll('dagbok');
  const blob=new Blob([JSON.stringify({{
    exportedAt: new Date().toISOString(),
    libraryLabels: getLabels(),
    fieldRecordings: fieldRecs.map(r=>( {{id:r.id,category:r.category,notes:r.notes,ts:r.ts,duration:r.duration}} )),
    dagbok: dagbokRecs.map(e=>( {{id:e.id,date:e.date,place:e.place,weather:e.weather,activities:e.activities,notes:e.notes,ts:e.ts}} )),
  }},null,2)],{{type:'application/json'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='crowtalk_data.json'; a.click();
}}

// ═══════════════════════════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════════════════════════
function fmt(s) {{
  if(!s||!isFinite(s))return'0:00';
  return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
}}

// ═══════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════
async function init() {{
  // IndexedDB is optional – Library/Theory work without it.
  // Wrap separately so a DB failure never blocks the sound list.
  try {{
    await openDB();
    await loadFieldItems();
  }} catch(e) {{
    console.warn('IndexedDB unavailable (private mode or blocked):', e);
    // db remains undefined; field recording / journal tabs will be disabled
  }}
  try {{
    renderContextPanel();
    renderFilterBar();
    renderSoundList();
    initDagbokForm();
    document.getElementById('topSub').textContent =
      `Corvus cornix · ${{RECORDINGS.length}} XC · ${{SYNTH_DEMOS.length}} synthetic`;
  }} catch(e) {{
    console.error('Render failed:', e);
    const list = document.getElementById('soundList');
    if (list) list.innerHTML =
      `<div class="empty-state" style="color:#f87171;padding:24px">⚠ Load error: ${{e.message}}</div>`;
  }}
}}
init().catch(e => console.error('init rejected:', e));
</script>
</body>
</html>"""

with open(OUTPUT,'w',encoding='utf-8') as f:
    f.write(html)
sz = os.path.getsize(OUTPUT)/1024/1024
print(f"✅ Klar! → {OUTPUT}  ({sz:.1f} MB)")

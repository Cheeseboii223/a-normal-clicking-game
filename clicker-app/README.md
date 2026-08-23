# a normal clicker game — Capacitor / Android build

This replaces the Kivy + buildozer + Colab pipeline entirely. The game is now
plain HTML/CSS/JS (`www/`), wrapped by **Capacitor** so it builds into a real
APK using nothing but Node + the Android SDK, straight from the VS Code
terminal. No more `python-for-android`, no more autoreconf/libffi/libtool
errors, no more Colab.

## 0. One-time setup on your machine

You need, installed locally (not in a notebook):
1. **Node.js** (LTS) — https://nodejs.org
2. **Android Studio** — https://developer.android.com/studio (this gives you
   the Android SDK + build tools + a JDK, even if you never open the Studio
   GUI again after installing it). During setup, let it install the default
   SDK platform + build tools.
3. Make sure `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) is set to your SDK path,
   e.g. on Windows `C:\Users\<you>\AppData\Local\Android\Sdk`, on
   mac/Linux `~/Android/Sdk`. Android Studio's "SDK Manager" screen shows you
   the exact path if you're not sure.

That's it — this is a one-time setup, not something you redo per build.

## 1. Drop in your real assets

Open the `www/assets/` folder and add the files from your old `game2`
folder:

| File to add                         | What it's for                              |
|--------------------------------------|---------------------------------------------|
| `icon.png` (replace the placeholder) | App icon shown in-game & used for launcher icon generation |
| `music1.ogg`                         | First background music track (loops into music2) |
| `music2.ogg`                         | Second background music track |
| `COMIC.TTF`                          | The game's font (optional — falls back to a similar font if missing) |

If your original files were `.jpg`/`.mp3` instead, either convert them or
just rename the extensions in `www/index.html` (icon) / `www/js/app.js`
(`MUSIC_TRACKS` array) / `www/css/style.css` (`@font-face`) to match.

## 2. Install dependencies

In VS Code's terminal, `cd` into this project folder, then:

```bash
npm install
```

## 3. Add the Android platform (only needed once)

```bash
npx cap add android
```

This generates an `android/` folder — a real Android Studio/Gradle project.

## 4. Sync your web code into the Android project

Run this **every time you change files in `www/`**:

```bash
npx cap sync android
```

## 5. Build the APK — straight from the terminal

```bash
npm run build:apk
```

(On Windows, use `npm run build:apk:win` instead.)

The debug APK will land at:

```
android/app/build/outputs/apk/debug/app-debug.apk
```

Copy that onto a phone (or drag it into an Android emulator window) to
install and play it. No Colab, no buildozer, no waiting 20 minutes for a
`libffi` recipe to explode.

### Want a "real" release build (signed, for the Play Store)?

Run `npx cap open android` to open the project in Android Studio once, then
use **Build > Generate Signed Bundle / APK** — Android Studio walks you
through creating a keystore. After that, you can also script signed builds
from the terminal with `./gradlew assembleRelease`, but that requires wiring
up signing config in `android/app/build.gradle` first, which is easiest to
do once through the Android Studio wizard.

## Polish pass (this update)

- **Upgrades no longer step on each other.** In the previous build several
  upgrades quietly added into the *same* shared counter (e.g. Auto Click,
  PSU Boost, and Network all pushed into one `auto_click_rate` number), so
  buying one could make another upgrade's effect look like it "vanished."
  Every upgrade now owns exactly one effect, shown live under its name in
  the shop. The single exception is **Core Overclock**, which is openly a
  global +1%/level multiplier on top of everything else — that's by design
  and is labelled as such, not a bug.
- **Upgrades shop stays open while you buy.** It used to close after every
  purchase; now it updates in place with a flash animation on success (or a
  shake if you can't afford it yet), plus a small live summary of your
  current Click Power / Auto Clicker / Global Boost at the top.
- **Hacked events are now scheduled, not a dice roll on every tap/tick.**
  The old version rolled a 2% chance on *every single click* and every
  1-second tick while a server was online, which meant frantic tapping (or
  just idling) could trigger a burst of attacks or none for ages. It's now
  a real timer: while a compatible server is online and the app is in the
  foreground, the next hacked event is queued at a randomised delay that
  averages out to **about 3 events per 10 minutes of active play**,
  independent of how fast you're tapping.
- **Smoother everywhere.** Modals, toasts, the hacked-event overlay, the
  hack-battle banner, milestone bars, rank-ups, and every button now use a
  consistent set of GPU-friendly transform/opacity transitions instead of
  hard cuts, tuned to feel snappy at 60fps rather than heavy.
- **Fewer localStorage writes.** Saves from ordinary taps/ticks are now
  batched (~1.2s) instead of writing to disk on every single tap, which
  keeps rapid tapping smooth on lower-end Android WebViews. Important
  events (purchases, milestones, settings, backgrounding the app) still
  save immediately so nothing is ever lost.
- **A couple of dead stats got wired up properly:** Network Defense now
  actually reduces clicks stolen during a hack battle (it was defined but
  always returned 0 before), and PSU Boost now contributes to your visible
  server power score instead of only nudging auto-click.

## What changed from the Kivy version

- All game logic was ported 1:1 from `main.py`'s economy: clicks-per-tap,
  auto-clicking, 12 upgrades, the milestone list + messages, the 30-tier
  rank system, offline-time bonus, the hacked-event glitch-text intro, and
  the hack-battle mini-game, and the full server builder (CPU / Motherboard
  / RAM / GPU / PSU / Case with the same compatibility rules and power-score
  math).
- Save data now lives in the WebView's `localStorage` instead of a JSON file
  in `user_data_dir` — same idea, different storage API, still survives
  app restarts and updates.
- Sound effects are now generated with the Web Audio API instead of
  `winsound` — this is actually an upgrade, since the original's
  `winsound` calls only ever worked on Windows desktop and were silently
  disabled on Android.
- **Not ported, because they were dead code in your original file**: the
  stock market (`buy_stock`/`sell_stock`), roulette, daily chest, and the
  Firewall/Overdrive/Auto-Repair/Rare-Drop upgrades. Those functions existed
  in `main.py` but were never bound to any button, so they were unreachable
  in the shipped game — I left them out rather than silently inventing UI
  for a system you never actually shipped. Say the word if you want any of
  them wired up (the underlying math is simple to add back).

## Project layout

```
clicker-app/
├── capacitor.config.json
├── package.json
├── www/                  <- this is your actual game (edit this)
│   ├── index.html
│   ├── css/style.css
│   ├── js/data.js         (server parts / milestones / ranks data)
│   ├── js/app.js          (all game logic)
│   └── assets/            (icon, music, font go here)
└── android/               <- generated by `npx cap add android`, don't hand-edit
```

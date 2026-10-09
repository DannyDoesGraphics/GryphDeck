# GryphDeck

Gryphon Esports/Gryphon Gaming stream overlay software with a Flask JSON API
and a Next.js frontend.

## Development

Start the Flask API from the project root:

```powershell
.\Scripts\python.exe run.py
```

In a second terminal, start Next.js:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The available frontend routes are `/idle`,
`/pregame`, `/ingame`, and `/UI`. The API runs at `http://localhost:5000/api`.

## Flask control page

Open `http://localhost:5000` (or `/UI`) after starting Flask. This control page
does not require Next.js. It loads Valorant by default and lists game JSON files
from `app/json` in the game selector.

- Choose a game and click **Load game** to reset its component toggles, map picks,
  and hero bans while retaining team names, scores, and rosters.
- Click a component in **Idle**, **Pregame**, or **Ingame** to enable
  or disable it. The same button displays its state. Components at the same
  position replace each other; toggles are independent between scenes.
- Team names and scores save automatically. Add or remove
  players individually. **Swap sides** calls `MatchInfo.swap_sides()` to swap
  the saved team names, scores, and rosters.

The page modifies one `StateManager` per Flask app instance, shared by clients.
State is held in memory and resets when the server restarts; use one server
process for this local control workspace. Refresh another open control page to
see the latest state. `/api/state` returns the full state, `/api/control` accepts
JSON actions, and the scene endpoints include the current match and components.

Run the control API and class tests together:

```powershell
.\Scripts\python.exe -m unittest app.test_routes app.classes.test_classes -v
```

## Scene JSON

`StateManager.create_post_request()` returns a JSON string with `game` and
`scenes`. The `scenes` object always contains `idle`, `pregame`, and `ingame`
arrays, containing only the components whose toggles are enabled. Each entry
has `name`, `location` (from the game JSON's `Position`), and `data`.

Every component's `data` includes `game` and `scene`. Dynamic components also
include their current values:

- Team Roster: `teams`, with `name` and `players` for each team.
- Score Pregame / Score Ingame: `teams`, with `name` and `score` for each team.
- Map Picks: `map_picks`, in selection order.
- Character Bans Pregame / Ingame: `hero_bans`, in selection order.
- Hero Draft / Deadlock Top Bar: `label`, `first_pick` (0 = none, 1 = left, 2 = right), and
  `teams` with `name`, `score`, `players`, `picks`, and `bans`. Pick and
  ban arrays have one entry per slot, `null` while open; pick slot N belongs to
  roster player N. `sides_known` is false until the in-game sides are known (teams show grey).

Team arrays are ordered left then right. Static components such as Starting
Soon and Sponsorships Badge receive only game and scene context, since no
editable content or sponsor assets are currently configured for them.

After every successful `/api/control` update, the route generates and prints
this document to the Flask terminal and POSTs it to the Next.js receiver at
`http://127.0.0.1:3000/api/overlay`. The method itself only returns the JSON;
`routes.py` handles delivery. The control API retains its existing response.

## OBS overlay sources

With Flask and Next.js running, add these URLs as OBS **Browser Sources**:

- `http://localhost:3000/idle`
- `http://localhost:3000/pregame`
- `http://localhost:3000/ingame`

Set the browser-source width and height to the broadcast resolution (for
example, 1920 × 1080). The page canvas is transparent with no full-page
background, loading message, or error screen. Only enabled component boxes
are drawn; their dark translucent fills help placeholder text remain readable.
Positions are anchored to the source edges or center using the JSON `location`.
Score, roster, map-pick, and hero-ban placeholders show the attached data.
Static components show their name and game; the sponsor badge uses a placeholder.

Pages poll the local Next.js receiver every 400 ms. It retains the latest POST
and reconciles with Flask's `GET /api/overlay` every two seconds to recover missed
updates or server restarts. A disconnected page keeps its last valid frame;
a page without a document stays transparent until it connects. The receiver
validates documents and rejects malformed data without replacing its last frame.
Run one local Next.js process and one Flask process for this setup.

For different ports or hosts, set `OVERLAY_POST_URL` in the Flask process and
`FLASK_API_URL` in `frontend/.env.local` (see `.env.example`), then restart the
servers. For example:

```powershell
$env:OVERLAY_POST_URL = "http://127.0.0.1:3005/api/overlay"
.\Scripts\python.exe run.py
```

The Flask delivery timeout is one second. A failed delivery is logged but does
not undo saved controls; the receiver recovers through the snapshot endpoint.
For OBS use, `npm run build` followed by `npm start` avoids development tooling.
The frontend `/UI` route opens the Flask control page.

Frontend checks: run `npm test`, `npm run lint`, and `npm run build` in `frontend`.

## Hero draft (Deadlock)

Games whose JSON has a `draft` section (`{"picks": 6, "bans": 2}`) get per-team
pick and ban slots. Deadlock uses this with the **Hero Draft** pregame component:
a full-screen picks-and-bans board built for broadcasts without player cameras.
On the control page, the **Hero draft** panel sets the match label, the first
pick, and each slot's hero. A hero can fill only one slot across both teams,
**Swap sides** moves each team's draft with it, and loading a game clears it.

The **Deadlock Top Bar** ingame component is a full-width match band (Gryphon Gaming
branding, both teams and their players, series score, and the match label) in the Hidden King
and Archmother team colours. It is laid out for Deadlock's spectator HUD pushed down
64px (at 1080p) by the GryphDeck spectator mod (below), and places each roster's player names above the
game's hero portraits, so enter players in their in-game slot order. Positions come
from the game's `citadel_hud_top_bar` layout (88-wide player columns in two 528-wide
teams, centred), in 1920-wide units that scale with any 16:9 output.

Hero portraits come from the local Deadlock install rather than the web. After
a game update (for example, when newly released heroes get their full card art),
re-export them:

```powershell
.\Scripts\python.exe tools\export_deadlock_heroes.py
```

It reads `pak01_dir.vpk` from the default Steam path (pass `--pak` for another
library) and writes `frontend/public/static/Deadlock/Chars/<Hero>.png` for every
hero in `app/json/Deadlock.json`. It also writes the team icons the Deadlock Top Bar uses
(`Deadlock/Teams/hidden_king.svg` and `archmother.svg`) from the game's own SVGs. New heroes need a line in the script's
`CODENAMES` table; the script lists card art it cannot match yet.

## Deadlock spectator mod

Start Deadlock for a broadcast with:

```powershell
.\start_deadlock.bat
```

It builds and installs the GryphDeck spectator mod, launches Deadlock, and reports the
match to GryphDeck until the game closes. Your other addons are set aside and restored
afterwards (`--keep-mods` keeps them).

The mod (`tools/deadlock/build_mod.py`) bundles the latest Top Bar Plus from GameBanana
(listed in `tools/deadlock/mods.json`), pushes the spectator HUD down 64px for the Deadlock
Top Bar, hides spectator-only clutter (camera controls, player navigation, and the Map View
label), and adds a script that reports each side's players and
heroes.

The Hero Draft and Deadlock Top Bar stay grey until the sides are known. GryphDeck matches
roster names and draft picks against the game's players and heroes, swaps the teams if
needed, and colours them. If it can't tell, the **Team sides** panel shows why; set the
sides there by hand.

## Class tests

Run the `GameInfo`, `MatchInfo`, and `StateManager` tests from the project root:

```powershell
.\Scripts\python.exe app/classes/test_classes.py
```

Add `--demo` to also print example game configuration, team updates, side swaps,
and component changes after the tests pass. Each class supports `print(instance)`
and `instance.print_info()` for inspecting its current state.

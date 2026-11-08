# Facade (React)

React version of the desktop app in `app/renderer`: Dashboard, API page and Settings drawer.
It looks and behaves the same as the HTML version.

```bash
cd web
npm install
npm run dev
```

## What came over unchanged

| React file | From |
| --- | --- |
| `src/styles.css` | `app/renderer/styles.css` (copied as is) |
| `src/lib/agentKinds.js` | the six tile animations in `app/renderer/dashboard.js` |
| `src/lib/mockApi.js` | `app/renderer/mockapi.js` |
| `src/lib/settings.js` | `app/renderer/settings.js` |
| `src/lib/mockRun.js` | `app/renderer/mock.js` |

## Layout

```
src/
  App.jsx                  pages, run form, status line, clock
  components/
    Titlebar.jsx           brand + Dashboard / API tabs
    Intake.jsx             link box, Run agents, safety chip, Settings button
    Board.jsx              the six agent tiles (canvas per tile)
    ApiView.jsx            generated API list, try-it panels, JSON viewer
    SettingsDrawer.jsx     safety, speed and stop limits
  lib/
    dashboard.js           tile controller: dashboard.set / reset / summary (same API as before)
    agentKinds.js          tile animations
    mockRun.js             fake agent progress (demo only)
    mockApi.js             fake endpoints and data
    settings.js            settings store (localStorage)
    hooks.js               useSettings, useTile
```

## Explorer tab (replay of a real run)

The Explorer tab replays a run of the Explorer agent line by line: the site map, the agent log,
the record counter, the data model and a data browser for the records.

Put the agent's output in `public/run/`:

```
public/run/run_log.jsonl
public/run/site_map.json
public/run/data_model.json
public/run/records/Post.jsonl
```

You can also drop a run folder onto the Explorer tab, or use **Load run files**.

Everything about loading lives in `src/run/data/source.js`. To switch to SpacetimeDB, write
`createSpacetimeSource` there (a sketch is at the bottom of the file) and pass it to `setSource`
in `src/run/ExplorerView.jsx`. The panels in `src/run/components/` don't change.

## Hooking up the back end

Same calls as the HTML app. `window.dashboard` and `window.facadeSettings` are still set:

```js
dashboard.set('explorer', { status: 'working', progress: 0.4, stat: 'Pages mapped 12 / 30' });
```

Replace `mock.start(...)` in `App.jsx` with the real run.

## Electron

`npm run build` writes `dist/` with relative paths. To load it in the desktop app later,
point `app/main.js` at `web/dist/index.html`.

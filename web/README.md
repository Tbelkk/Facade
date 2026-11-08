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

## Hooking up the back end

Same calls as the HTML app. `window.dashboard` and `window.facadeSettings` are still set:

```js
dashboard.set('explorer', { status: 'working', progress: 0.4, stat: 'Pages mapped 12 / 30' });
```

Replace `mock.start(...)` in `App.jsx` with the real run.

## Opening it from the home page

The home page (`index.html` in the repo root) has an **Open dashboard** button that links to `dashboard/`.
Build the dashboard into that folder:

```bash
cd web
npm run build      # writes ../dashboard
```

Then serve the repo root and open the home page:

```bash
cd ..
python3 -m http.server 8000   # http://localhost:8000/
```

Rebuild after changing anything in `web/`. Commit `dashboard/` too if the site is hosted as static files
(for example GitHub Pages). 
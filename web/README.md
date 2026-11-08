# RESTore (web)

The RESTore website's dashboard: Dashboard and API page, built with React and Vite.

```bash
cd web
npm install
npm run dev
```

## Layout

```
src/
  App.jsx                  pages, run form, status line, clock
  components/
    Titlebar.jsx           brand + Dashboard / API tabs
    Intake.jsx             link box, URL check, Start exploring
    Board.jsx              the six agent tiles (canvas per tile)
    ApiView.jsx            generated API list, try-it panels, JSON viewer
  lib/
    dashboard.js           tile controller: dashboard.set / reset / summary (same API as before)
    agentKinds.js          tile animations
    mockRun.js             fake agent progress (demo only)
    mockApi.js             fake endpoints and data
    hooks.js               useTile
```

## Hooking up the back end

`window.dashboard` is still set:

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
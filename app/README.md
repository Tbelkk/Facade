# Facade desktop app (front end)

The dashboard where you watch the agents work. The agents themselves are built by the back-end team.

- **Link box**: paste the old website's address and press **Run agents**.
- **Settings** button (top right of the link box): not wired up yet.
- **Dashboard**: one tile per agent, each animated with white dots:

| # | Agent | Shows |
|---|---|---|
| 01 | Explorer | the site map being drawn page by page |
| 02 | Analyst | scattered facts sorting into entities (Patient, Appointment, Invoice) and rules |
| 03 | Extractor | records streaming from the old site into the database |
| 04 | Builder | API endpoints and MCP tools being wired to the database |
| 05 | Worker | a request coming in, the old site's form being filled, the result going back |
| 06 | Verifier | a scan line checking every record, retrying anything that doesn't match |

## Settings → Safety

The **Settings** button (top right of the link box) opens the Safety panel: what agents may do on the old site.
A chip next to the button always shows the current mode (READ-ONLY / CAN ACT · ASKS FIRST).

| Setting | Default | Meaning |
|---|---|---|
| Read-only mode | on | Explore and copy only, never submit forms. While on, “Ask before acting” is locked and the Worker stays idle. |
| Ask before acting | Always | `always` / `destructive` / `never`: when changes need approval |
| Pages per minute | 20 | Explorer speed limit (1–60) |
| Pause between clicks | 1.0 s | 0–5 s |
| Max pages to explore | 200 | stop limit (10–5000) |
| Max run time | 30 min | stop limit (1–240) |

Settings autosave on this computer. The back end reads them with `facadeSettings.get()` and
`facadeSettings.onChange(fn)` (see `renderer/settings.js`).

## API page

The **API** tab (top right) shows the API the agents generate, Swagger-style: endpoints grouped by
section, each with a method badge, path, and lock icon. Click one to open it: its parameters are pre-filled
and editable, and it immediately returns **mock data** (status, timing, JSON, copy-as-curl).

The endpoints and the fake data live in `renderer/mockapi.js` (`SPEC`). When the back end generates a real
API, replace `SPEC` with the generated endpoints (or an OpenAPI file) and swap each `run` for a real request.

## Hooking up the back end

Right now `renderer/mock.js` fakes the progress so the dashboard can be demoed. To use real data,
remove `mock.js` and call this from the real agent events:

```js
dashboard.set('explorer', { status: 'working', progress: 0.4, stat: 'Pages mapped 12 / 30' });
// ids:     explorer, analyst, extractor, builder, worker, verifier
// status:  'idle' | 'working' | 'done' | 'live'
// progress: 0..1    stat: optional footer text
dashboard.reset();
```

## Run / build

```
cd app
npm install
npm start            # run the app
npm run dist:win     # build dist/Facade-Setup.exe
```

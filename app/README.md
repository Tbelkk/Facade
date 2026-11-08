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

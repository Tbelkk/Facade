# Facade desktop app

Electron app with the same blue and white look as the website.

## Run it

```
cd app
npm install
npm start
```

It connects to the Facade core at `ws://127.0.0.1:8765` (see FACADE-TEAM-PLAN §6.5).
If the core isn't running, it shows **Demo mode** with sample data, and the agent runs a simulated plan.

## Build the Windows installer

```
npm run dist:win
```

Creates `dist/Facade-Setup.exe`. Upload it to a GitHub Release (named exactly `Facade-Setup.exe`)
so the website's download button works:
https://github.com/Tbelkk/Facade/releases/latest/download/Facade-Setup.exe

// Facade desktop app: main process
const { app, BrowserWindow, shell } = require('electron');
const path = require('path');

function createWindow() {
  const isWin = process.platform === 'win32';

  const win = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 960,
    minHeight: 640,
    title: 'Facade',
    backgroundColor: '#f5f8fe',
    show: false,
    // Custom title bar that matches the app; Windows keeps native min/max/close buttons.
    titleBarStyle: 'hidden',
    titleBarOverlay: isWin ? { color: '#ffffff', symbolColor: '#0b1b3a', height: 44 } : false,
    trafficLightPosition: { x: 16, y: 15 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.once('ready-to-show', () => win.show());
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // Open external links in the user's browser, never inside the app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (e) => e.preventDefault());
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

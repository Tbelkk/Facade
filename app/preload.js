// Exposes a tiny, read-only bit of info to the UI. No Node access in the renderer.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('facade', {
  platform: process.platform,
});

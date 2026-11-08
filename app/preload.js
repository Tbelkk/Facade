// Small bridge to the UI. The back-end team can add their IPC calls here.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('facade', {
  platform: process.platform,
});

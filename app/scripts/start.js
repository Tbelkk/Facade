// Launch Electron with a clean environment. Some editors (e.g. VS Code extensions)
// set ELECTRON_RUN_AS_NODE=1, which makes Electron act like plain Node and no window opens.
const { spawn } = require('child_process');
const electron = require('electron');

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

const child = spawn(electron, ['.'], { stdio: 'inherit', env, cwd: __dirname + '/..' });
child.on('close', (code) => process.exit(code ?? 0));

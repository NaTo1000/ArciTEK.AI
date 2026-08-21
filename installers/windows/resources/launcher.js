/**
 * ArciTEK.AI Windows Launcher
 * 
 * Electron-based desktop application launcher for ArciTEK.AI.
 * Provides native Windows integration with system tray, notifications,
 * and automatic server management.
 * 
 * "Every build is a work of art" - infinite♾2025
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, shell, dialog, Notification } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

// Configuration
const APP_NAME = 'ArciTEK.AI';
const APP_VERSION = '1.0.0';
const SERVER_PORT = 8000;
const INSTALL_DIR = path.dirname(process.execPath);
const CONFIG_DIR = path.join(INSTALL_DIR, 'config');
const PYTHON_PATH = path.join(INSTALL_DIR, 'runtime', 'python', 'python.exe');
const ICON_PATH = path.join(INSTALL_DIR, 'arcitek_icon.ico');

let mainWindow = null;
let tray = null;
let serverProcess = null;
let isQuitting = false;

// ===== Server Management =====

function startServer() {
    const serverScript = path.join(INSTALL_DIR, 'arcitek_core', 'main.py');
    
    if (!fs.existsSync(PYTHON_PATH)) {
        dialog.showErrorBox('ArciTEK.AI', 
            'Python runtime not found. Please reinstall ArciTEK.AI.');
        return false;
    }
    
    serverProcess = spawn(PYTHON_PATH, [serverScript], {
        cwd: INSTALL_DIR,
        env: {
            ...process.env,
            ARCITEK_HOME: INSTALL_DIR,
            ARCITEK_PORT: SERVER_PORT.toString(),
            PYTHONPATH: INSTALL_DIR
        },
        stdio: ['pipe', 'pipe', 'pipe']
    });
    
    serverProcess.stdout.on('data', (data) => {
        console.log(`[Server] ${data}`);
    });
    
    serverProcess.stderr.on('data', (data) => {
        console.error(`[Server Error] ${data}`);
    });
    
    serverProcess.on('close', (code) => {
        console.log(`Server process exited with code ${code}`);
        if (!isQuitting && code !== 0) {
            showNotification('Server Stopped', 
                'ArciTEK.AI server has stopped unexpectedly. Restarting...');
            setTimeout(startServer, 3000);
        }
    });
    
    return true;
}

function stopServer() {
    if (serverProcess) {
        serverProcess.kill('SIGTERM');
        serverProcess = null;
    }
}

// ===== Window Management =====

function createMainWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 768,
        title: `${APP_NAME} v${APP_VERSION}`,
        icon: ICON_PATH,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: true
        },
        backgroundColor: '#1a1a2e',
        show: false,
        autoHideMenuBar: false
    });
    
    // Load the web interface
    mainWindow.loadURL(`http://localhost:${SERVER_PORT}`);
    
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        showNotification('ArciTEK.AI Started', 
            'Quantum-Enhanced AI Development Platform is ready.');
    });
    
    mainWindow.on('close', (event) => {
        if (!isQuitting) {
            event.preventDefault();
            mainWindow.hide();
            showNotification('ArciTEK.AI', 
                'ArciTEK.AI is still running in the system tray.');
        }
    });
    
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
    
    // Create application menu
    createAppMenu();
}

function createAppMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                { label: 'New Project', accelerator: 'CmdOrCtrl+N', click: () => newProject() },
                { label: 'Open Project', accelerator: 'CmdOrCtrl+O', click: () => openProject() },
                { type: 'separator' },
                { label: 'Configuration Wizard', click: () => openConfigWizard() },
                { type: 'separator' },
                { label: 'Exit', accelerator: 'Alt+F4', click: () => quitApp() }
            ]
        },
        {
            label: 'View',
            submenu: [
                { label: 'Dashboard', click: () => navigateTo('/dashboard') },
                { label: 'Quantum Lab', click: () => navigateTo('/quantum') },
                { label: 'AI Models', click: () => navigateTo('/ai-models') },
                { type: 'separator' },
                { label: 'Developer Tools', accelerator: 'F12', role: 'toggleDevTools' },
                { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' }
            ]
        },
        {
            label: 'Tools',
            submenu: [
                { label: 'Validate API Keys', click: () => validateKeys() },
                { label: 'Check for Updates', click: () => checkUpdates() },
                { label: 'Run Tests', click: () => runTests() },
                { type: 'separator' },
                { label: 'Open Terminal', click: () => openTerminal() }
            ]
        },
        {
            label: 'Help',
            submenu: [
                { label: 'Documentation', click: () => shell.openExternal('https://github.com/NaTo1000/ArciTEK.AI') },
                { label: 'Quick Start Guide', click: () => openFile('QUICKSTART.md') },
                { type: 'separator' },
                { label: `About ${APP_NAME}`, click: () => showAbout() }
            ]
        }
    ];
    
    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

// ===== System Tray =====

function createTray() {
    const icon = nativeImage.createFromPath(ICON_PATH);
    tray = new Tray(icon);
    
    const contextMenu = Menu.buildFromTemplate([
        { label: `${APP_NAME} v${APP_VERSION}`, enabled: false },
        { type: 'separator' },
        { label: 'Open ArciTEK.AI', click: () => showMainWindow() },
        { label: 'Open Dashboard', click: () => shell.openExternal(`http://localhost:${SERVER_PORT}/dashboard`) },
        { type: 'separator' },
        { label: 'Start Server', click: () => startServer() },
        { label: 'Stop Server', click: () => stopServer() },
        { label: 'Restart Server', click: () => { stopServer(); setTimeout(startServer, 1000); } },
        { type: 'separator' },
        { label: 'Configuration', click: () => openConfigWizard() },
        { label: 'Check for Updates', click: () => checkUpdates() },
        { type: 'separator' },
        { label: 'Quit', click: () => quitApp() }
    ]);
    
    tray.setToolTip(`${APP_NAME} - Quantum-Enhanced AI Development Platform`);
    tray.setContextMenu(contextMenu);
    
    tray.on('double-click', () => showMainWindow());
}

// ===== Helper Functions =====

function showMainWindow() {
    if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
    } else {
        createMainWindow();
    }
}

function showNotification(title, body) {
    if (Notification.isSupported()) {
        new Notification({ title, body, icon: ICON_PATH }).show();
    }
}

function navigateTo(path) {
    if (mainWindow) {
        mainWindow.loadURL(`http://localhost:${SERVER_PORT}${path}`);
    }
}

function openConfigWizard() {
    exec(`"${PYTHON_PATH}" "${path.join(INSTALL_DIR, 'scripts', 'config_wizard.py')}"`, {
        cwd: INSTALL_DIR
    });
}

function validateKeys() {
    exec(`"${PYTHON_PATH}" "${path.join(INSTALL_DIR, 'scripts', 'validate_keys.py')}"`, {
        cwd: INSTALL_DIR
    }, (error, stdout) => {
        dialog.showMessageBox(mainWindow, {
            type: error ? 'error' : 'info',
            title: 'API Key Validation',
            message: error ? 'Validation failed' : 'Validation complete',
            detail: stdout || error.message
        });
    });
}

function checkUpdates() {
    exec(`"${PYTHON_PATH}" "${path.join(INSTALL_DIR, 'scripts', 'upgrade.py')}" check`, {
        cwd: INSTALL_DIR
    }, (error, stdout) => {
        dialog.showMessageBox(mainWindow, {
            type: 'info',
            title: 'Update Check',
            message: stdout || 'You are up to date!'
        });
    });
}

function runTests() {
    exec(`"${PYTHON_PATH}" -m pytest "${path.join(INSTALL_DIR, 'tests')}" -v`, {
        cwd: INSTALL_DIR
    }, (error, stdout) => {
        dialog.showMessageBox(mainWindow, {
            type: error ? 'warning' : 'info',
            title: 'Test Results',
            message: error ? 'Some tests failed' : 'All tests passed!',
            detail: stdout
        });
    });
}

function openTerminal() {
    exec('start cmd.exe', { cwd: INSTALL_DIR });
}

function openFile(filename) {
    shell.openPath(path.join(INSTALL_DIR, filename));
}

function newProject() {
    navigateTo('/new-project');
}

function openProject() {
    dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: 'ArciTEK Projects', extensions: ['arcitek'] },
            { name: 'All Files', extensions: ['*'] }
        ]
    }).then(result => {
        if (!result.canceled && result.filePaths.length > 0) {
            navigateTo(`/project?path=${encodeURIComponent(result.filePaths[0])}`);
        }
    });
}

function showAbout() {
    dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: `About ${APP_NAME}`,
        message: `${APP_NAME} v${APP_VERSION}`,
        detail: `Quantum-Enhanced AI Development Platform\n\n` +
                `"Every build is a work of art"\n\n` +
                `• 5 Quantum Computing Platforms\n` +
                `• 325B AI Parameters\n` +
                `• 99.97% Precision Builds\n` +
                `• +26.7% Quantum Boost\n\n` +
                `© 2025 infinite♾2025\n` +
                `https://infinite2025.com`
    });
}

function quitApp() {
    isQuitting = true;
    stopServer();
    app.quit();
}

// ===== App Lifecycle =====

app.whenReady().then(() => {
    // Start the backend server
    startServer();
    
    // Wait for server to be ready
    setTimeout(() => {
        createMainWindow();
        createTray();
    }, 3000);
});

app.on('window-all-closed', () => {
    // Don't quit on macOS
    if (process.platform !== 'darwin') {
        // Keep running in tray on Windows
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createMainWindow();
    }
});

app.on('before-quit', () => {
    isQuitting = true;
    stopServer();
});

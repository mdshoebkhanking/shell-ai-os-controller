const path = require('node:path')

const root = path.resolve(__dirname, '..', '..')
const windowsTargets = process.env.SHELL_ELECTRON_BUILDER_DIR_ONLY === '1'
  ? ['dir']
  : ['dir', 'nsis']

module.exports = {
  appId: 'com.shellai.oscontroller',
  productName: 'Shell AI',
  directories: {
    output: path.join(root, 'dist', 'electron')
  },
  compression: 'store',
  files: [
    'dist/**/*',
    'electron/**/*',
    'package.json'
  ],
  extraMetadata: {
    main: 'electron/main.cjs'
  },
  asar: true,
  win: {
    executableName: 'ShellAI',
    target: windowsTargets,
    icon: path.join(root, '.shell_runtime', 'windows_installer_staging', 'build_assets', 'shell-ai.ico')
  },
  nsis: {
    artifactName: 'shell-ai-os-controller-setup-${version}.${ext}',
    shortcutName: 'Shell AI',
    uninstallDisplayName: 'Shell AI',
    installerIcon: path.join(root, '.shell_runtime', 'windows_installer_staging', 'build_assets', 'shell-ai.ico'),
    uninstallerIcon: path.join(root, '.shell_runtime', 'windows_installer_staging', 'build_assets', 'shell-ai.ico'),
    installerHeaderIcon: path.join(root, '.shell_runtime', 'windows_installer_staging', 'build_assets', 'shell-ai.ico'),
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: 'always',
    createStartMenuShortcut: true,
    runAfterFinish: true
  },
  mac: {
    target: ['dir']
  }
}

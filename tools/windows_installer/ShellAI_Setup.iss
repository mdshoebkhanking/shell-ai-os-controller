#ifndef AppSource
  #define AppSource "..\..\shell-ai-os-controller-staging"
#endif

#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppPublisher "mdshoebking"
#define AppName "Shell AI OS Controller"
#define AppExeName "Start_ShellAI.bat"

[Setup]
AppId={{9D77E6BF-78C4-47D5-9F54-8E2464E84A2A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/mdshoebking
AppSupportURL=https://github.com/mdshoebking
AppUpdatesURL=https://github.com/mdshoebking
DefaultDirName={localappdata}\Programs\ShellAI
DefaultGroupName=Shell AI OS Controller
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=shell-ai-os-controller-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start Shell AI when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked
Name: "bootstrap"; Description: "Install or repair Shell AI dependencies now"; GroupDescription: "First run setup:"; Flags: checkedonce

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Shell AI OS Controller"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Repair Shell AI"; Filename: "{app}\Repair_ShellAI.bat"; WorkingDir: "{app}"
Name: "{group}\Windows Acceptance Test"; Filename: "{app}\Run_Windows_Acceptance_Test.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Shell AI OS Controller"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\Shell AI OS Controller"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\ONE_CLICK_INSTALL.bat"; Description: "Install or repair Shell AI dependencies"; WorkingDir: "{app}"; Flags: postinstall shellexec waituntilterminated skipifsilent; Tasks: bootstrap
Filename: "{app}\{#AppExeName}"; Description: "Launch Shell AI"; WorkingDir: "{app}"; Flags: postinstall shellexec nowait skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.shell_runtime\updates"
Type: filesandordirs; Name: "{app}\.shell_runtime\windows_installer_staging"

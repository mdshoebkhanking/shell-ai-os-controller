Unicode true
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!include "MUI2.nsh"
!include "LogicLib.nsh"

!ifndef AppSource
  !define AppSource "..\..\shell-ai-os-controller-staging"
!endif

!ifndef OutputDir
  !define OutputDir "..\..\dist"
!endif

!ifndef AppVersion
  !define AppVersion "1.0.0"
!endif

!ifndef AppExeName
  !define AppExeName "ShellAIApp\ShellAI.exe"
!endif

!ifndef LicenseFile
  !define LicenseFile "..\..\LICENSE"
!endif

!define AppName "Shell AI OS Controller"
!define AppPublisher "mdshoebking"
!define AppRegKey "Software\ShellAI"

Name "${AppName}"
Caption "${AppName} Setup"
BrandingText "${AppName}"
OutFile "${OutputDir}\shell-ai-os-controller-setup-${AppVersion}.exe"
InstallDir "$LOCALAPPDATA\Programs\ShellAI"
InstallDirRegKey HKCU "${AppRegKey}" "Install_Dir"

VIProductVersion "${AppVersion}.0"
VIAddVersionKey "ProductName" "${AppName}"
VIAddVersionKey "CompanyName" "${AppPublisher}"
VIAddVersionKey "FileDescription" "${AppName} NSIS Setup"
VIAddVersionKey "FileVersion" "${AppVersion}"
VIAddVersionKey "ProductVersion" "${AppVersion}"

!ifdef InstallerIcon
Icon "${InstallerIcon}"
UninstallIcon "${InstallerIcon}"
!define MUI_ICON "${InstallerIcon}"
!define MUI_UNICON "${InstallerIcon}"
!endif

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${AppExeName}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Shell AI"
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_UNFINISHPAGE_NOAUTOCLOSE

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LicenseFile}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Shell AI OS Controller" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "${AppSource}\*"

  WriteRegStr HKCU "${AppRegKey}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI" "DisplayName" "${AppName}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI" "DisplayVersion" "${AppVersion}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI" "Publisher" "${AppPublisher}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\Shell AI OS Controller"
  CreateShortCut "$SMPROGRAMS\Shell AI OS Controller\Shell AI OS Controller.lnk" "$INSTDIR\${AppExeName}" "" "$INSTDIR\${AppExeName}" 0
  CreateShortCut "$SMPROGRAMS\Shell AI OS Controller\Repair Shell AI.lnk" "$INSTDIR\Repair_ShellAI.bat" "" "$INSTDIR\Repair_ShellAI.bat" 0
  CreateShortCut "$SMPROGRAMS\Shell AI OS Controller\Windows Acceptance Test.lnk" "$INSTDIR\Run_Windows_Acceptance_Test.bat" "" "$INSTDIR\Run_Windows_Acceptance_Test.bat" 0
SectionEnd

Section "Desktop shortcut" SecDesktop
  CreateShortCut "$DESKTOP\Shell AI OS Controller.lnk" "$INSTDIR\${AppExeName}" "" "$INSTDIR\${AppExeName}" 0
SectionEnd

Section /o "Start Shell AI when Windows starts" SecStartup
  CreateShortCut "$SMSTARTUP\Shell AI OS Controller.lnk" "$INSTDIR\${AppExeName}" "" "$INSTDIR\${AppExeName}" 0
SectionEnd

Section /o "Install or repair Shell AI dependencies now" SecBootstrap
  ExecWait "$\"$INSTDIR\ONE_CLICK_INSTALL.bat$\""
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Shell AI OS Controller.lnk"
  Delete "$SMSTARTUP\Shell AI OS Controller.lnk"
  Delete "$SMPROGRAMS\Shell AI OS Controller\Shell AI OS Controller.lnk"
  Delete "$SMPROGRAMS\Shell AI OS Controller\Repair Shell AI.lnk"
  Delete "$SMPROGRAMS\Shell AI OS Controller\Windows Acceptance Test.lnk"
  RMDir "$SMPROGRAMS\Shell AI OS Controller"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ShellAI"
  DeleteRegKey HKCU "${AppRegKey}"

  RMDir /r "$INSTDIR\.shell_runtime\updates"
  RMDir /r "$INSTDIR\.shell_runtime\windows_installer_staging"
  RMDir /r "$INSTDIR\ShellAIApp"
  RMDir /r "$INSTDIR"
SectionEnd

; Inno Setup installer for the self-contained Windows build.

#define MyAppName "Scanora"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Prakshal Info Tech Pvt."
#define MyAppExeName "SmartImageSearch.exe"

[Setup]
AppId={{A7D7B9E4-4E61-4D1F-9B03-5AA1BDBD7E51}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

SetupIconFile=..\logo.ico
WizardImageFile=..\prakshal-logo.bmp
WizardSmallImageFile=..\prakshal-logo2.bmp

DefaultDirName={autopf}\SmartImageSearch
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist\installer
OutputBaseFilename=SmartImageSearch-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
; OCR results are session-only and no database is installed or removed.

[Files]
Source: "..\dist\SmartImageSearch.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; Remove the per-user index, OCR word-box cache, and settings on uninstall.
Type: filesandordirs; Name: "{localappdata}\SmartImageSearch"

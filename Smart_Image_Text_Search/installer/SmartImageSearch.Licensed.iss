; Licensing-enabled installer, built from the staged November 2 desktop executable.

#define MyAppName "Scanora"
#define MyAppVersion "1.0.1"
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
OutputBaseFilename=SmartImageSearch-Licensing-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\build\licensing-prompt-20261102\dist\SmartImageSearch.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
Type: files; Name: "{localappdata}\SmartImageSearch\licence.json"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\SmartImageSearch"
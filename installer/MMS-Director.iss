#define MyAppVersion "0.2.0"
[Setup]
AppId={{7AB108AE-8D9C-4DC4-92CE-FC74B60199A4}
AppName=MMS-Director
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\MMS-Director
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=MMS-Director-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\MMS-Director.exe
[Files]
Source: "..\dist\MMS-Director\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\MMS-Director"; Filename: "{app}\MMS-Director.exe"
Name: "{userdesktop}\MMS-Director"; Filename: "{app}\MMS-Director.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Crear acceso directo en el escritorio"

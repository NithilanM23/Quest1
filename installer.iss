; Inno Setup Script for Dialogue Frame Finder (Baseline Audio)
; Builds a self-contained one-touch installer .exe

#define MyAppName "Dialogue Frame Finder"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Quest Project"
#define MyAppExeName "launch.bat"

[Setup]
AppId={{D3F79B6A-8A1D-47C2-9E9A-24E01F82B3A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=DialogueFrameFinder_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Root scripts and configuration (only included active files)
Source: "launch.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "baseline_audio.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

; Public Web Frontend UI Assets
Source: "public\*"; DestDir: "{app}\public"; Flags: ignoreversion recursesubdirs createallsubdirs

; Core source modules (strictly only baseline dependencies)
Source: "src\__init__.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "src\ingest.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "src\asr_search.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "src\types.py"; DestDir: "{app}\src"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent

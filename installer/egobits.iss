; One offline wizard: native shell, Python backend, llama, model and WebView2.
; Requires Inno Setup >= 6.5.2 (single EXE > 2 GiB).
#ifndef RepoRoot
  #error RepoRoot must be passed by the verified build script
#endif
#include "generated-assets.iss"

[Setup]
AppId={{F57C7090-73DC-453B-96DF-8D9F3E215E10}
AppName=Rekord AI
AppVersion={#ReleaseVersion}
AppPublisher=EgoBits
DefaultDirName={localappdata}\Programs\Rekord AI
DefaultGroupName=Rekord AI
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir={#RepoRoot}\dist
OutputBaseFilename=Rekord_AI_Setup_{#ReleaseVersion}_x64
Compression=lzma2/fast
SolidCompression=no
DiskSpanning=no
WizardStyle=modern
SetupIconFile={#RepoRoot}\desktop\src-tauri\icons\rekord-ia.ico
UninstallDisplayIcon={app}\egobits-desktop.exe
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
AppMutex=Local\RekordAIApp
SetupMutex=Local\RekordAISetup

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked
Name: "watcher"; Description: "Abrir Rekord AI automaticamente al iniciar Rekordbox"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\desktop\src-tauri\target\x86_64-pc-windows-msvc\release\egobits-desktop.exe"; DestDir: "{app}"; Flags: ignoreversion; Hash: "{#ShellHash}"
Source: "{#RepoRoot}\build\backend\egobits-backend.exe"; DestDir: "{app}"; Flags: ignoreversion; Hash: "{#BackendHash}"
#include "generated-runtime-files.iss"
Source: "{#RepoRoot}\assets\licenses\*"; DestDir: "{app}\assets\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\assets\models\Qwen3.5-4B-Q4_K_M.gguf"; DestDir: "{app}\assets\models"; Flags: ignoreversion nocompression; Hash: "{#ModelHash}"; AfterInstall: VerifyModel
Source: "{#RepoRoot}\installer\offline_assets.json"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#RepoRoot}\release.json"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#RepoRoot}\installer\watch_rekordbox.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#RepoRoot}\build\toolchain\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Flags: dontcopy nocompression; Hash: "{#WebViewHash}"

[Icons]
Name: "{autoprograms}\Rekord AI"; Filename: "{app}\egobits-desktop.exe"
Name: "{autodesktop}\Rekord AI"; Filename: "{app}\egobits-desktop.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RekordAIEgoBitsWatcher"; ValueData: """{sys}\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\installer\watch_rekordbox.ps1"" -AppPath ""{app}\egobits-desktop.exe"""; Flags: uninsdeletevalue; Tasks: watcher

[Run]
Filename: "{app}\egobits-desktop.exe"; Description: "Abrir Rekord AI"; Flags: nowait postinstall skipifsilent; Check: CanLaunch

[Code]
#include "generated-runtime-checks.iss"

procedure VerifyRuntimeFile(FileName, ExpectedHash: String);
var InstalledPath, ActualHash: String;
begin
  InstalledPath := ExpandConstant(FileName);
  try
    ActualHash := GetSHA256OfFile(InstalledPath);
  except
    Log('Runtime verification failed: ' + InstalledPath);
    RaiseException('No se pudo leer el componente instalado: ' + InstalledPath);
  end;
  if CompareText(ActualHash, ExpectedHash) <> 0 then
    RaiseException('Un componente de IA local no supera la verificación de integridad.');
  Log('Runtime SHA-256 verified: ' + InstalledPath);
end;

function PayloadValid: Boolean;
begin
  Result := False;
  if not FileExists(ExpandConstant('{app}\egobits-desktop.exe')) or
     not FileExists(ExpandConstant('{app}\egobits-backend.exe')) then exit;
  try
    Result := (CompareText(GetSHA256OfFile(ExpandConstant('{app}\egobits-desktop.exe')), '{#ShellHash}') = 0) and
      (CompareText(GetSHA256OfFile(ExpandConstant('{app}\egobits-backend.exe')), '{#BackendHash}') = 0) and RuntimePayloadValid;
  except
    Result := False;
  end;
end;

function CanLaunch: Boolean;
begin
  Result := PayloadValid;
  if not Result then
    SuppressibleMsgBox('Rekord AI no puede iniciarse: falta un componente o cambió su integridad. Revisá el Historial de protección de Seguridad de Windows. No desactives el antivirus. La instalación necesita revisión.', mbError, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and not PayloadValid then
    RaiseException('No se pudo verificar Rekord AI instalado. Un componente falta, fue bloqueado o cambió. Revisá el Historial de protección de Seguridad de Windows; no desactives el antivirus.');
end;

function InitializeSetup: Boolean;
var Previous: String; Installed, Offered: Int64;
begin
  Result := True;
  if RegQueryStringValue(HKCU64, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F57C7090-73DC-453B-96DF-8D9F3E215E10}_is1', 'DisplayVersion', Previous) then begin
    if not StrToVersion(Previous, Installed) or not StrToVersion('{#ReleaseVersion}', Offered) then begin
      SuppressibleMsgBox('No se pudo comparar la versión instalada. Revisá la instalación existente antes de actualizar.', mbError, MB_OK, IDOK);
      Result := False;
    end else if ComparePackedVersion(Installed, Offered) > 0 then begin
      SuppressibleMsgBox('Ya tenés una versión más nueva de Rekord AI. Este instalador no puede reemplazarla por una anterior.', mbError, MB_OK, IDOK);
      Result := False;
    end;
  end;
end;

function WebViewInstalled: Boolean;
var Version: String;
begin
  Result := (RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
  if not Result then
    Result := (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer; Installer, Probe, AppPath: String;
begin
  Result := '';
  { Older releases did not create AppMutex. Require their tray app/backend to
    exit as well, without terminating a collection operation. }
  AppPath := ExpandConstant('{app}');
  StringChangeEx(AppPath, '''', '''''', True);
  Probe := '-NoProfile -NonInteractive -WindowStyle Hidden -Command "' +
    '$target = ''' + AppPath + '''; try { $running = @(Get-Process -Name egobits-desktop,egobits-backend -ErrorAction SilentlyContinue | Where-Object { $_.Path -and [IO.Path]::GetDirectoryName($_.Path) -eq $target }); if ($running.Count) { exit 10 }; exit 0 } catch { exit 11 }"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Probe, '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then begin
    Result := 'Rekord AI debe estar completamente cerrado para instalar o actualizar. Usá Salir desde su icono junto al reloj y esperá que terminen las operaciones. Luego reintentá.';
    exit;
  end;
  if WebViewInstalled then exit;
  WizardForm.PreparingLabel.Caption := 'Preparando el componente de Windows incluido. No requiere Internet...';
  ExtractTemporaryFile('MicrosoftEdgeWebView2RuntimeInstallerX64.exe');
  Installer := ExpandConstant('{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe');
  if CompareText(GetSHA256OfFile(Installer), '{#WebViewHash}') <> 0 then begin
    Result := 'El componente de Windows no supera la verificacion de integridad.';
    exit;
  end;
  if not Exec(Installer, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then begin
    Result := 'No se pudo instalar el componente de Windows.';
    exit;
  end;
  if Code = 3010 then NeedsRestart := True;
  if (Code <> 0) and (Code <> 3010) then
    Result := Format('El componente de Windows devolvio el codigo %d.', [Code])
  else if not WebViewInstalled then
    Result := 'WebView2 no quedo disponible. Reinicie Windows y vuelva a ejecutar el asistente.';
end;

procedure VerifyModel;
begin
  WizardForm.StatusLabel.Caption := 'Verificando el modelo de IA incluido...';
  if CompareText(GetSHA256OfFile(ExpandConstant('{app}\assets\models\Qwen3.5-4B-Q4_K_M.gguf')), '{#ModelHash}') <> 0 then
    RaiseException('El modelo no supera la verificacion de integridad. No se puede completar la instalacion.');
end;

; Installateur Windows de Chaînes de cotes 1D (Inno Setup 6). Lancé par construire_bureau.py :
;   iscc /DVersion=1.0.0 /DRacine=<dossier du dépôt> installateur.iss
; Installation pour l'utilisateur seul (aucun droit d'administrateur), icône du Bureau, menu Démarrer, désinstallation.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Racine
  #define Racine "."
#endif

[Setup]
AppId={{B7D41C5E-8A2F-4D63-9E10-5F3A6C8D2E41}
AppName=Chaînes de cotes 1D
AppVersion={#Version}
AppVerName=Chaînes de cotes 1D {#Version}
AppPublisher=Théo Brun
AppPublisherURL=https://github.com/theo33-oss/chaines-de-cotes-1D
AppSupportURL=https://github.com/theo33-oss/chaines-de-cotes-1D/issues
AppUpdatesURL=https://github.com/theo33-oss/chaines-de-cotes-1D/releases
DefaultDirName={localappdata}\Programs\ChainesDeCotes
DefaultGroupName=Chaînes de cotes 1D
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Racine}\dist
OutputBaseFilename=ChainesDeCotes_Installation_{#Version}
SetupIconFile={#Racine}\build\icone.ico
UninstallDisplayIcon={app}\ChainesDeCotes.exe
LicenseFile={#Racine}\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "{#Racine}\dist\ChainesDeCotes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Chaînes de cotes 1D"; Filename: "{app}\ChainesDeCotes.exe"
Name: "{group}\Limites connues"; Filename: "{app}\LIMITES.md"
Name: "{group}\Désinstaller Chaînes de cotes 1D"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Chaînes de cotes 1D"; Filename: "{app}\ChainesDeCotes.exe"; Tasks: bureau

[Run]
Filename: "{app}\ChainesDeCotes.exe"; Description: "Ouvrir Chaînes de cotes 1D"; Flags: nowait postinstall skipifsilent

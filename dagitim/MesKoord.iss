; MesKoord kurulum dosyası (Inno Setup 6).
; Doğrudan derlemeyin; araclar\surum_hazirla.py
; sürüm, yayıncı ve klasör bilgilerini /D parametreleriyle verir.
;
; Okullarda kullanım:
;  - Kurulum dosyasının yanına konan bütün .lic dosyaları C:\ProgramData\MesKoord içine kopyalanır;
;    lisans o bilgisayarın bütün kullanıcıları için geçerli olur.
;  - Sessiz kurulum (bilgisayar laboratuvarı vb.):  MesKoord_Kurulum_X.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
;  - Yeni sürüm eskisinin üzerine kurulur; veriler (Belgeler\MesKoord) ve lisans korunur.
;  - Çok kullanıcılı çalışma için Windows güvenlik duvarına yalnızca yerel ağdan (LocalSubnet) gelen
;    bağlantılara izin veren bir kural eklenir; kaldırılınca kural da silinir.
;
; 1.3.0 öncesi teknik ad KoordMES'ti. Güncellemede: Program Files\KoordMES klasörü Program Files\MesKoord'a
; geçer (içindeki .lic dosyaları ProgramData\MesKoord'a alınır), ProgramData\KoordMES'teki lisanslar taşınır,
; "KoordMES" güvenlik duvarı kuralı ve Windows açılış kaydı yeni adla yenilenir. Belgeler\KoordMES veri
; klasörünü program ilk açılışta kendisi Belgeler\MesKoord'a taşır.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppPublisher
  #define AppPublisher "MesKoord"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\MesKoord"
#endif
#ifndef OutputDir
  #define OutputDir "..\cikti"
#endif
#ifndef LicenseText
  #define LicenseText "LISANS_SOZLESMESI.txt"
#endif

[Setup]
; AppId hiçbir zaman değiştirilmez; değişirse yeni sürüm eskisinin üzerine kurulmaz.
AppId={{E2806E6F-8363-4C7E-9C5A-D2928AF548A6}
AppName=MesKoord
AppVersion={#AppVersion}
AppVerName=MesKoord {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=MesKoord Kurulum
DefaultDirName={autopf}\MesKoord
DefaultGroupName=MesKoord
DisableProgramGroupPage=yes
LicenseFile={#LicenseText}
OutputDir={#OutputDir}
OutputBaseFilename=MesKoord_Kurulum_{#AppVersion}
SetupIconFile=meskoord.ico
WizardImageFile=kurulum_buyuk.bmp,kurulum_buyuk_150.bmp,kurulum_buyuk_200.bmp
WizardSmallImageFile=kurulum_kucuk.bmp,kurulum_kucuk_150.bmp,kurulum_kucuk_200.bmp
UninstallDisplayIcon={app}\MesKoord.exe
UninstallDisplayName=MesKoord {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "masaustu"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek kısayollar:"

[InstallDelete]
; Eski sürümden kalan kütüphaneler yenileriyle karışmasın
Type: filesandordirs; Name: "{app}\_internal"
; 1.3.0 öncesi program dosyası (kurulum klasörü KoordMES adlı değilse yerinde güncellenir)
Type: files; Name: "{app}\KoordMES.exe"
; Ürün adı KoordMES / Hünerver iken oluşturulan kısayollar
Type: filesandordirs; Name: "{autoprograms}\KoordMES"
Type: files; Name: "{autodesktop}\KoordMES.lnk"
Type: filesandordirs; Name: "{autoprograms}\Hünerver"
Type: files; Name: "{autodesktop}\Hünerver.lnk"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{src}\*.lic"; DestDir: "{commonappdata}\MesKoord"; Flags: external skipifsourcedoesntexist ignoreversion uninsneveruninstall; Permissions: users-readexec

[Icons]
Name: "{group}\MesKoord"; Filename: "{app}\MesKoord.exe"
Name: "{group}\Kullanım Kılavuzu"; Filename: "{app}\KULLANIM_KILAVUZU.pdf"
Name: "{group}\MesKoord'u Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MesKoord"; Filename: "{app}\MesKoord.exe"; Tasks: masaustu

[Registry]
; Program "Windows açılışında arka planda başlat" seçeneğiyle bu değeri kendisi yazar; kaldırınca silinir
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MesKoord"; Flags: dontcreatekey uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "KoordMES"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KoordMES"""; Flags: runhidden; StatusMsg: "Güvenlik duvarı ayarlanıyor..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""MesKoord"""; Flags: runhidden; StatusMsg: "Güvenlik duvarı ayarlanıyor..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""MesKoord"" dir=in action=allow program=""{app}\MesKoord.exe"" enable=yes profile=any remoteip=localsubnet"; Flags: runhidden; StatusMsg: "Güvenlik duvarı ayarlanıyor..."
Filename: "{app}\MesKoord.exe"; Description: "MesKoord'u başlat"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""MesKoord"""; Flags: runhidden; RunOnceId: "GuvenlikDuvari"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KoordMES"""; Flags: runhidden; RunOnceId: "EskiGuvenlikDuvari"

[Messages]
turkish.FinishedLabel=MesKoord kuruldu. Verileriniz Belgeler\MesKoord klasöründe saklanır; programı kaldırsanız da silinmez.

[Code]
const
  ESKI_AD = 'KoordMES';
  RUN_ANAHTARI = 'Software\Microsoft\Windows\CurrentVersion\Run';

var
  EskiKlasor: String;

procedure InitializeWizard;
var
  Klasor: String;
begin
  { Önceki kurulum KoordMES adlı klasördeyse yeni sürüm yanındaki MesKoord klasörüne kurulur }
  Klasor := RemoveBackslash(WizardForm.DirEdit.Text);
  if CompareText(ExtractFileName(Klasor), ESKI_AD) = 0 then
  begin
    EskiKlasor := Klasor;
    WizardForm.DirEdit.Text := AddBackslash(ExtractFilePath(Klasor)) + 'MesKoord';
  end;
end;

procedure RegisterExtraCloseApplicationsResources;
begin
  RegisterExtraCloseApplicationsResource(False, ExpandConstant('{app}\') + ESKI_AD + '.exe');
  if EskiKlasor <> '' then
    RegisterExtraCloseApplicationsResource(False, AddBackslash(EskiKlasor) + ESKI_AD + '.exe');
end;

procedure LisanslariTasi(Kaynak: String; Sil: Boolean);
var
  Bul: TFindRec;
  Hedef: String;
begin
  Hedef := ExpandConstant('{commonappdata}\MesKoord');
  if FindFirst(AddBackslash(Kaynak) + '*.lic', Bul) then
  begin
    try
      repeat
        ForceDirectories(Hedef);
        if FileExists(AddBackslash(Hedef) + Bul.Name) or
           FileCopy(AddBackslash(Kaynak) + Bul.Name, AddBackslash(Hedef) + Bul.Name, True) then
        begin
          if Sil then
            DeleteFile(AddBackslash(Kaynak) + Bul.Name);
        end;
      until not FindNext(Bul);
    finally
      FindClose(Bul);
    end;
  end;
end;

procedure AcilisKaydiniYenile;
var
  Eski: String;
begin
  if RegQueryStringValue(HKCU, RUN_ANAHTARI, ESKI_AD, Eski) then
  begin
    RegWriteStringValue(HKCU, RUN_ANAHTARI, 'MesKoord', '"' + ExpandConstant('{app}\MesKoord.exe') + '" --arka-plan');
    RegDeleteValue(HKCU, RUN_ANAHTARI, ESKI_AD);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EskiOrtak: String;
begin
  if CurStep = ssInstall then
  begin
    EskiOrtak := ExpandConstant('{commonappdata}\') + ESKI_AD;
    LisanslariTasi(EskiOrtak, True);
    RemoveDir(EskiOrtak);
    if (EskiKlasor <> '') and (CompareText(EskiKlasor, RemoveBackslash(ExpandConstant('{app}'))) <> 0)
       and DirExists(EskiKlasor) then
    begin
      LisanslariTasi(EskiKlasor, False);
      DelTree(EskiKlasor, True, True, True);
    end;
  end;
  if CurStep = ssPostInstall then
    AcilisKaydiniYenile;
end;

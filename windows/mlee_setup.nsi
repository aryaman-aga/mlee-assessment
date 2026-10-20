; MLEE Assessment - Windows installer (NSIS 3)
;
;   makensis /DSTAGE=<staging dir> /DOUTFILE=<setup.exe> /DVERSION=1.0.0 mlee_setup.nsi
;
; The staging directory is produced by build_windows.ps1 and contains python\,
; tectonic\, texcache\, app\, the launcher .cmd files and the documentation.
; Installs per user (no administrator rights) into %LOCALAPPDATA%\Programs.

Unicode true
ManifestDPIAware true
SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel user

!ifndef STAGE
  !define STAGE "..\staging"
!endif
!ifndef OUTFILE
  !define OUTFILE "..\dist\MLEE_Assessment_Setup.exe"
!endif
!ifndef VERSION
  !define VERSION "1.0.0"
!endif

!define APPNAME "MLEE Assessment"
!define REGKEY "Software\MLEE Assessment"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\MLEE-Assessment"

Name "${APPNAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
InstallDirRegKey HKCU "${REGKEY}" "InstallDir"
BrandingText "${APPNAME} ${VERSION}"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "${APPNAME}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1033 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1033 "FileDescription" "${APPNAME} setup (Python analysis and PDF report toolkit)"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Bundled components keep their own licences; see THIRD_PARTY_NOTICES.txt"

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

!define MUI_ICON "mlee.ico"
!define MUI_UNICON "mlee.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Install ${APPNAME}"
!define MUI_WELCOMEPAGE_TEXT "This installs everything needed to run and test the MLEE assessment on this computer:$\r$\n$\r$\n  - Python 3.13 with NumPy, SciPy, scikit-learn, Matplotlib, seaborn and pandas$\r$\n  - the four task scripts and their datasets$\r$\n  - the Tectonic TeX engine with an offline TeX cache, to rebuild the PDF report$\r$\n$\r$\nNo administrator rights or internet connection are needed. Apart from Start-menu and desktop shortcuts, nothing outside the installation folder is changed."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Open the MLEE test console now"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchConsole
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\Staff Guide.html"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Show the staff guide"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "${APPNAME} needs Windows 10 or 11." /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
  ${AndIfNot} ${IsNativeARM64}
    MessageBox MB_OK|MB_ICONSTOP "${APPNAME} needs 64-bit Windows." /SD IDOK
    Abort
  ${EndIf}
FunctionEnd

Function LaunchConsole
  ExecShell "open" "$INSTDIR\MLEE Assessment.cmd"
FunctionEnd

Section "MLEE Assessment" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  ; Replace an older runtime completely so stale packages never mix in.
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\tectonic"
  RMDir /r "$INSTDIR\texcache"
  File /r /x "meta.tex" "${STAGE}\*"
  ; Keep a student name/ID already entered by the user when upgrading.
  SetOutPath "$INSTDIR\app\report"
  SetOverwrite off
  File "${STAGE}\app\report\meta.tex"
  SetOverwrite on
  SetOutPath "$INSTDIR"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\MLEE Assessment (test console).lnk" "$INSTDIR\MLEE Assessment.cmd" "" "$INSTDIR\mlee.ico"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Run analysis.lnk" "$INSTDIR\Run analysis.cmd" "" "$INSTDIR\mlee.ico"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Build report PDF.lnk" "$INSTDIR\Build report PDF.cmd" "" "$INSTDIR\mlee.ico"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\MLEE command prompt.lnk" "$INSTDIR\MLEE Command Prompt.cmd" "" "$INSTDIR\mlee.ico"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Project folder.lnk" "$INSTDIR\app"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Staff guide.lnk" "$INSTDIR\Staff Guide.html"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\MLEE Assessment.lnk" "$INSTDIR\MLEE Assessment.cmd" "" "$INSTDIR\mlee.ico"

  WriteRegStr HKCU "${REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${REGKEY}" "Version" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\mlee.ico"
  WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\MLEE Assessment.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  ; Only remove what the installer created; never the whole folder blindly.
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\tectonic"
  RMDir /r "$INSTDIR\texcache"
  RMDir /r "$INSTDIR\app"
  Delete "$INSTDIR\MLEE Assessment.cmd"
  Delete "$INSTDIR\Run analysis.cmd"
  Delete "$INSTDIR\Build report PDF.cmd"
  Delete "$INSTDIR\MLEE Command Prompt.cmd"
  Delete "$INSTDIR\_env.cmd"
  Delete "$INSTDIR\mlee.ico"
  Delete "$INSTDIR\Staff Guide.html"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTKEY}"
  DeleteRegKey HKCU "${REGKEY}"
SectionEnd

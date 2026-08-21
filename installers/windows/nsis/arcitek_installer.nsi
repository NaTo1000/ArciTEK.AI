; ArciTEK.AI Windows Installer
; NSIS (Nullsoft Scriptable Install System) Script
; "Every build is a work of art" - infinite♾2025
;
; Build: makensis arcitek_installer.nsi
; Output: ArciTEK_AI_Setup_v1.0.0_x64.exe

;--------------------------------
; Includes
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "nsDialogs.nsh"

;--------------------------------
; General Configuration
!define PRODUCT_NAME "ArciTEK.AI"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "infinite2025"
!define PRODUCT_WEB_SITE "https://infinite2025.com"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\arcitek-ai.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
!define PRODUCT_STARTMENU_REGVAL "NSIS:StartMenuDir"

; Installer attributes
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\..\..\dist\ArciTEK_AI_Setup_v${PRODUCT_VERSION}_x64.exe"
InstallDir "$PROGRAMFILES64\ArciTEK.AI"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show
RequestExecutionLevel admin
SetCompressor /SOLID lzma

;--------------------------------
; Interface Settings
!define MUI_ABORTWARNING
!define MUI_ICON "..\resources\arcitek_icon.ico"
!define MUI_UNICON "..\resources\arcitek_icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "..\resources\installer_header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\resources\installer_welcome.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "..\resources\installer_welcome.bmp"

; Branding
BrandingText "${PRODUCT_NAME} v${PRODUCT_VERSION} - infinite♾2025"

;--------------------------------
; Pages

; Welcome page
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${PRODUCT_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of ${PRODUCT_NAME} v${PRODUCT_VERSION}.$\r$\n$\r$\nArciTEK.AI is a quantum-enhanced AI development platform integrating multiple AI models, quantum computing platforms, and development tools.$\r$\n$\r$\n$\"Every build is a work of art$\" - infinite♾2025$\r$\n$\r$\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME

; License page
!define MUI_LICENSEPAGE_CHECKBOX
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"

; Components page
!insertmacro MUI_PAGE_COMPONENTS

; Directory page
!insertmacro MUI_PAGE_DIRECTORY

; Custom configuration page
Page custom ConfigPageCreate ConfigPageLeave

; Start menu page
var ICONS_GROUP
!define MUI_STARTMENUPAGE_NODISABLE
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "${PRODUCT_NAME}"
!define MUI_STARTMENUPAGE_REGISTRY_ROOT "${PRODUCT_UNINST_ROOT_KEY}"
!define MUI_STARTMENUPAGE_REGISTRY_KEY "${PRODUCT_UNINST_KEY}"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "${PRODUCT_STARTMENU_REGVAL}"
!insertmacro MUI_PAGE_STARTMENU Application $ICONS_GROUP

; Install page
!insertmacro MUI_PAGE_INSTFILES

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\arcitek-ai.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"
!define MUI_FINISHPAGE_LINK "Visit ${PRODUCT_WEB_SITE}"
!define MUI_FINISHPAGE_LINK_LOCATION "${PRODUCT_WEB_SITE}"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Variables
Var ConfigApiKey
Var ConfigQuantumPlatform
Var ConfigAutoUpdate
Var Dialog
Var Label
Var ApiKeyField
Var QuantumDropdown
Var AutoUpdateCheckbox

;--------------------------------
; Custom Configuration Page
Function ConfigPageCreate
    !insertmacro MUI_HEADER_TEXT "Configuration" "Configure ArciTEK.AI settings"
    
    nsDialogs::Create 1018
    Pop $Dialog
    
    ${If} $Dialog == error
        Abort
    ${EndIf}
    
    ; Title
    ${NSD_CreateLabel} 0 0 100% 20u "Configure your ArciTEK.AI installation:"
    Pop $Label
    
    ; API Key section
    ${NSD_CreateLabel} 0 30u 100% 12u "OpenAI API Key (optional - can be configured later):"
    Pop $Label
    
    ${NSD_CreatePassword} 0 44u 100% 12u ""
    Pop $ApiKeyField
    
    ; Quantum Platform
    ${NSD_CreateLabel} 0 66u 100% 12u "Primary Quantum Platform:"
    Pop $Label
    
    ${NSD_CreateDropList} 0 80u 100% 12u ""
    Pop $QuantumDropdown
    ${NSD_CB_AddString} $QuantumDropdown "IBM Quantum (Recommended)"
    ${NSD_CB_AddString} $QuantumDropdown "IonQ"
    ${NSD_CB_AddString} $QuantumDropdown "Google Quantum AI"
    ${NSD_CB_AddString} $QuantumDropdown "Amazon Braket"
    ${NSD_CB_AddString} $QuantumDropdown "Azure Quantum"
    ${NSD_CB_SelectString} $QuantumDropdown "IBM Quantum (Recommended)"
    
    ; Auto-update
    ${NSD_CreateCheckbox} 0 106u 100% 12u "Enable automatic updates"
    Pop $AutoUpdateCheckbox
    ${NSD_Check} $AutoUpdateCheckbox
    
    ; Info text
    ${NSD_CreateLabel} 0 130u 100% 30u "Note: All settings can be changed later using the Configuration Wizard. API keys are stored securely in your local environment."
    Pop $Label
    
    nsDialogs::Show
FunctionEnd

Function ConfigPageLeave
    ${NSD_GetText} $ApiKeyField $ConfigApiKey
    ${NSD_GetText} $QuantumDropdown $ConfigQuantumPlatform
    ${NSD_GetState} $AutoUpdateCheckbox $ConfigAutoUpdate
FunctionEnd

;--------------------------------
; Installer Sections

Section "ArciTEK.AI Core" SEC_CORE
    SectionIn RO ; Required section
    
    SetOutPath "$INSTDIR"
    SetOverwrite on
    
    ; Core application files
    File /r "..\..\arcitek_core\*.*"
    File /r "..\..\quantum\*.*"
    File /r "..\..\ai_models\*.*"
    File /r "..\..\tools\*.*"
    File /r "..\..\scripts\*.*"
    File "..\..\startup.sh"
    File "..\..\requirements.txt"
    File "..\..\package.json"
    File "..\..\VERSION"
    File "..\..\README.md"
    File "..\..\LICENSE"
    
    ; Windows-specific launcher
    File "..\resources\arcitek-ai.exe"
    File "..\resources\arcitek_icon.ico"
    
    ; Create config directory
    CreateDirectory "$INSTDIR\config"
    
    ; Write configuration
    FileOpen $0 "$INSTDIR\config\.env" w
    FileWrite $0 "# ArciTEK.AI Configuration$\r$\n"
    FileWrite $0 "# Generated by installer$\r$\n"
    FileWrite $0 "ARCITEK_HOME=$INSTDIR$\r$\n"
    FileWrite $0 "ARCITEK_VERSION=${PRODUCT_VERSION}$\r$\n"
    FileWrite $0 "ARCITEK_PORT=8000$\r$\n"
    ${If} $ConfigApiKey != ""
        FileWrite $0 "OPENAI_API_KEY=$ConfigApiKey$\r$\n"
    ${EndIf}
    FileWrite $0 "QUANTUM_PLATFORM=$ConfigQuantumPlatform$\r$\n"
    ${If} $ConfigAutoUpdate == ${BST_CHECKED}
        FileWrite $0 "AUTO_UPDATE=true$\r$\n"
    ${Else}
        FileWrite $0 "AUTO_UPDATE=false$\r$\n"
    ${EndIf}
    FileClose $0
SectionEnd

Section "Python Runtime" SEC_PYTHON
    SetOutPath "$INSTDIR\runtime\python"
    
    ; Download and install Python 3.11 embedded
    DetailPrint "Installing Python 3.11 runtime..."
    NSISdl::download "https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip" "$TEMP\python311.zip"
    nsisunz::UnzipToLog "$TEMP\python311.zip" "$INSTDIR\runtime\python"
    Delete "$TEMP\python311.zip"
    
    ; Install pip
    NSISdl::download "https://bootstrap.pypa.io/get-pip.py" "$TEMP\get-pip.py"
    nsExec::ExecToLog '"$INSTDIR\runtime\python\python.exe" "$TEMP\get-pip.py"'
    Delete "$TEMP\get-pip.py"
    
    ; Install Python dependencies
    DetailPrint "Installing Python dependencies..."
    nsExec::ExecToLog '"$INSTDIR\runtime\python\python.exe" -m pip install -r "$INSTDIR\requirements.txt" --quiet'
SectionEnd

Section "Node.js Runtime" SEC_NODEJS
    SetOutPath "$INSTDIR\runtime\nodejs"
    
    ; Download Node.js
    DetailPrint "Installing Node.js 22 runtime..."
    NSISdl::download "https://nodejs.org/dist/v22.13.0/node-v22.13.0-win-x64.zip" "$TEMP\nodejs.zip"
    nsisunz::UnzipToLog "$TEMP\nodejs.zip" "$INSTDIR\runtime\nodejs"
    Delete "$TEMP\nodejs.zip"
    
    ; Install Node.js dependencies
    DetailPrint "Installing Node.js dependencies..."
    nsExec::ExecToLog '"$INSTDIR\runtime\nodejs\node.exe" "$INSTDIR\runtime\nodejs\npm" install --prefix "$INSTDIR"'
SectionEnd

Section "Desktop Shortcut" SEC_DESKTOP
    ; Create desktop shortcut
    CreateShortCut "$DESKTOP\ArciTEK.AI.lnk" "$INSTDIR\arcitek-ai.exe" "" "$INSTDIR\arcitek_icon.ico" 0
SectionEnd

Section "Start Menu Shortcuts" SEC_STARTMENU
    !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    CreateDirectory "$SMPROGRAMS\$ICONS_GROUP"
    CreateShortCut "$SMPROGRAMS\$ICONS_GROUP\ArciTEK.AI.lnk" "$INSTDIR\arcitek-ai.exe" "" "$INSTDIR\arcitek_icon.ico"
    CreateShortCut "$SMPROGRAMS\$ICONS_GROUP\ArciTEK.AI Dashboard.lnk" "http://localhost:8000/dashboard"
    CreateShortCut "$SMPROGRAMS\$ICONS_GROUP\Configuration Wizard.lnk" "$INSTDIR\runtime\python\python.exe" '"$INSTDIR\scripts\config_wizard.py"'
    CreateShortCut "$SMPROGRAMS\$ICONS_GROUP\Uninstall.lnk" "$INSTDIR\uninst.exe"
    
    !insertmacro MUI_STARTMENU_WRITE_END
SectionEnd

Section "Add to PATH" SEC_PATH
    ; Add to system PATH
    EnVar::AddValue "PATH" "$INSTDIR"
    EnVar::AddValue "PATH" "$INSTDIR\runtime\python"
    EnVar::AddValue "PATH" "$INSTDIR\runtime\nodejs"
SectionEnd

Section "File Associations" SEC_FILEASSOC
    ; Register file associations
    WriteRegStr HKCR ".arcitek" "" "ArciTEK.AI.Project"
    WriteRegStr HKCR "ArciTEK.AI.Project" "" "ArciTEK.AI Project File"
    WriteRegStr HKCR "ArciTEK.AI.Project\DefaultIcon" "" "$INSTDIR\arcitek_icon.ico"
    WriteRegStr HKCR "ArciTEK.AI.Project\shell\open\command" "" '"$INSTDIR\arcitek-ai.exe" "%1"'
    
    WriteRegStr HKCR ".qcircuit" "" "ArciTEK.AI.QuantumCircuit"
    WriteRegStr HKCR "ArciTEK.AI.QuantumCircuit" "" "Quantum Circuit File"
    WriteRegStr HKCR "ArciTEK.AI.QuantumCircuit\DefaultIcon" "" "$INSTDIR\arcitek_icon.ico"
    WriteRegStr HKCR "ArciTEK.AI.QuantumCircuit\shell\open\command" "" '"$INSTDIR\arcitek-ai.exe" "%1"'
SectionEnd

Section "Auto-Start Service" SEC_AUTOSTART
    ; Create Windows service for background operation
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "ArciTEK.AI" '"$INSTDIR\arcitek-ai.exe" --background'
SectionEnd

;--------------------------------
; Component Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE} "Core ArciTEK.AI platform files (required)"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_PYTHON} "Python 3.11 runtime for quantum computing and AI models"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_NODEJS} "Node.js 22 runtime for web interface and tools"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "Create a desktop shortcut for quick access"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_STARTMENU} "Create Start Menu shortcuts"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_PATH} "Add ArciTEK.AI to system PATH for command-line access"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_FILEASSOC} "Associate .arcitek and .qcircuit files with ArciTEK.AI"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC_AUTOSTART} "Start ArciTEK.AI automatically with Windows"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Post-Install
Section -Post
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"
    
    ; Write registry keys
    WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\arcitek-ai.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\arcitek_icon.ico"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    
    ; Calculate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"
    
    ; Run initial configuration
    DetailPrint "Running initial configuration..."
    nsExec::ExecToLog '"$INSTDIR\runtime\python\python.exe" "$INSTDIR\scripts\config_wizard.py" --auto'
SectionEnd

;--------------------------------
; Uninstaller Section
Section Uninstall
    ; Remove Start Menu shortcuts
    !insertmacro MUI_STARTMENU_GETFOLDER "Application" $ICONS_GROUP
    Delete "$SMPROGRAMS\$ICONS_GROUP\ArciTEK.AI.lnk"
    Delete "$SMPROGRAMS\$ICONS_GROUP\ArciTEK.AI Dashboard.lnk"
    Delete "$SMPROGRAMS\$ICONS_GROUP\Configuration Wizard.lnk"
    Delete "$SMPROGRAMS\$ICONS_GROUP\Uninstall.lnk"
    RMDir "$SMPROGRAMS\$ICONS_GROUP"
    
    ; Remove desktop shortcut
    Delete "$DESKTOP\ArciTEK.AI.lnk"
    
    ; Remove from PATH
    EnVar::DeleteValue "PATH" "$INSTDIR"
    EnVar::DeleteValue "PATH" "$INSTDIR\runtime\python"
    EnVar::DeleteValue "PATH" "$INSTDIR\runtime\nodejs"
    
    ; Remove auto-start
    DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "ArciTEK.AI"
    
    ; Remove file associations
    DeleteRegKey HKCR ".arcitek"
    DeleteRegKey HKCR "ArciTEK.AI.Project"
    DeleteRegKey HKCR ".qcircuit"
    DeleteRegKey HKCR "ArciTEK.AI.QuantumCircuit"
    
    ; Remove registry keys
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
    
    ; Remove installation directory
    RMDir /r "$INSTDIR"
    
    SetAutoClose true
SectionEnd

;--------------------------------
; Version Check
Function .onInit
    ; Check Windows version
    ${IfNot} ${AtLeastWin10}
        MessageBox MB_OK|MB_ICONSTOP "ArciTEK.AI requires Windows 10 or later."
        Abort
    ${EndIf}
    
    ; Check 64-bit
    ${IfNot} ${RunningX64}
        MessageBox MB_OK|MB_ICONSTOP "ArciTEK.AI requires a 64-bit version of Windows."
        Abort
    ${EndIf}
    
    ; Check for existing installation
    ReadRegStr $0 ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString"
    ${If} $0 != ""
        MessageBox MB_YESNO|MB_ICONQUESTION "ArciTEK.AI is already installed. Would you like to upgrade?" IDYES upgrade IDNO abort
        abort:
            Abort
        upgrade:
            ExecWait '$0 /S'
    ${EndIf}
FunctionEnd

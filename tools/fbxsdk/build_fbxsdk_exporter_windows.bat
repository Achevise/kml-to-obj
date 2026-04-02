@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Build fbxsdk_exporter.exe on Windows (x64) using MSVC + Autodesk FBX SDK.
REM Usage:
REM   tools\fbxsdk\build_fbxsdk_exporter_windows.bat
REM Optional:
REM   set FBXSDK_ROOT=C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.9

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%\.."
set "SRC_CPP=%SCRIPT_DIR%src\fbxsdk_exporter.cpp"
set "OUT_DIR=%SCRIPT_DIR%bin"
set "OUT_EXE=%OUT_DIR%\fbxsdk_exporter.exe"

if not exist "%SRC_CPP%" (
  echo [ERROR] Source not found: %SRC_CPP%
  exit /b 1
)

if "%FBXSDK_ROOT%"=="" (
  set "FBXSDK_ROOT=C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.9"
)

if not exist "%FBXSDK_ROOT%\include\fbxsdk.h" (
  echo [ERROR] FBX SDK headers not found under: %FBXSDK_ROOT%\include
  echo         Set FBXSDK_ROOT and retry.
  exit /b 1
)

set "LIB_DIR=%FBXSDK_ROOT%\lib\vs2022\x64\release"
if not exist "%LIB_DIR%" set "LIB_DIR=%FBXSDK_ROOT%\lib\vs2019\x64\release"
if not exist "%LIB_DIR%" set "LIB_DIR=%FBXSDK_ROOT%\lib\vs2017\x64\release"
if not exist "%LIB_DIR%" set "LIB_DIR=%FBXSDK_ROOT%\lib\vs2015\x64\release"
if not exist "%LIB_DIR%" (
  echo [ERROR] Could not locate FBX SDK lib dir under %FBXSDK_ROOT%\lib
  exit /b 1
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

where cl >NUL 2>&1
if errorlevel 1 (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if not exist "%VSWHERE%" (
    echo [ERROR] cl.exe not found and vswhere.exe not found.
    echo         Open a "Developer Command Prompt for VS" or install Build Tools.
    exit /b 1
  )
  for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%I"
  if "%VSINSTALL%"=="" (
    echo [ERROR] Visual Studio with C++ tools not found.
    exit /b 1
  )
  call "%VSINSTALL%\VC\Auxiliary\Build\vcvars64.bat"
  if errorlevel 1 (
    echo [ERROR] Failed to initialize MSVC environment.
    exit /b 1
  )
)

set "FBX_LIB=libfbxsdk-md.lib"
if not exist "%LIB_DIR%\%FBX_LIB%" set "FBX_LIB=libfbxsdk.lib"
if not exist "%LIB_DIR%\%FBX_LIB%" (
  echo [ERROR] Could not find libfbxsdk library in %LIB_DIR%
  exit /b 1
)

echo [INFO] FBXSDK_ROOT=%FBXSDK_ROOT%
echo [INFO] LIB_DIR=%LIB_DIR%
echo [INFO] Building %OUT_EXE%

cl /nologo /std:c++17 /O2 /EHsc ^
  /I"%FBXSDK_ROOT%\include" ^
  "%SRC_CPP%" ^
  /Fe:"%OUT_EXE%" ^
  /link /LIBPATH:"%LIB_DIR%" %FBX_LIB%

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo [OK] Built: %OUT_EXE%
exit /b 0


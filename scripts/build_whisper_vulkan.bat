@echo off
setlocal
set "ROOT=%~dp0.."
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (echo [ERRO] vswhere nao encontrado & exit /b 1)

rem Capturar com for /f falha em silencio nesta maquina: redirecionar para arquivo.
"%VSWHERE%" -latest -products * -property installationPath > "%TEMP%\gtaviral_vsp.txt"
set /p VS=<"%TEMP%\gtaviral_vsp.txt"
if not exist "%VS%\VC\Auxiliary\Build\vcvars64.bat" (echo [ERRO] vcvars64.bat nao encontrado em "%VS%" & exit /b 1)
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" || exit /b 1

if "%VULKAN_SDK%"=="" (echo [ERRO] VULKAN_SDK vazio: instale o Vulkan SDK e abra um terminal novo & exit /b 1)

set "SRC=%ROOT%\tools\src\whisper.cpp"
if not exist "%SRC%" (
  git clone --depth 1 --branch v1.9.5 https://github.com/ggml-org/whisper.cpp "%SRC%" || exit /b 1
)

rem Usa o CMake do VS: existe um cmake do MinGW (WinLibs) no PATH que escolheria o compilador errado.
set "CMAKE=%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
"%CMAKE%" -S "%SRC%" -B "%SRC%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DGGML_VULKAN=1 -DWHISPER_BUILD_TESTS=OFF || exit /b 1
"%CMAKE%" --build "%SRC%\build" -j || exit /b 1

if not exist "%ROOT%\tools\whisper" mkdir "%ROOT%\tools\whisper"
copy /y "%SRC%\build\bin\*.exe" "%ROOT%\tools\whisper\" >nul || exit /b 1
copy /y "%SRC%\build\bin\*.dll" "%ROOT%\tools\whisper\" >nul 2>nul
echo [OK] whisper-cli em %ROOT%\tools\whisper

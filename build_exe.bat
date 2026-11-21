@echo off
rem Builds the portable Cosplay Studio (dist\Cosplay Studio\ + a release zip). Needs Python 3.10+ on PATH.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller PySide6 || goto :fail
python -m PyInstaller --noconfirm --clean --distpath "..\dist" --workpath "..\build_tmp" CosplayStudio.spec || goto :fail
copy /y README_users.txt "..\dist\Cosplay Studio\README.txt" >nul
copy /y THIRD_PARTY_NOTICES.txt "..\dist\Cosplay Studio\THIRD_PARTY_NOTICES.txt" >nul
if not exist "..\release" mkdir "..\release"
powershell -NoProfile -Command "Compress-Archive -Force -Path '..\dist\Cosplay Studio' -DestinationPath '..\release\CosplayStudio_1.0.1.zip'" || goto :fail
echo.
echo Done:  dist\Cosplay Studio\Cosplay Studio.exe   and   release\CosplayStudio_1.0.1.zip
pause
exit /b 0
:fail
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1

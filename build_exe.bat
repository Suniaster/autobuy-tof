@echo off
echo Building autobuyer.exe...

rmdir /s /q dist
rmdir /s /q build

python -m PyInstaller --noconfirm --onefile --console --name "autobuyer" ^
    --hidden-import "cv2" ^
    --hidden-import "numpy" ^
    --hidden-import "pyautogui" ^
    --hidden-import "mss" ^
    --hidden-import "keyboard" ^
    --hidden-import "win32gui" ^
    "src\autobuyer.py"

echo Build complete.
echo Copying assets...

mkdir "dist\assets"
xcopy "assets" "dist\assets" /E /I /Y

echo Please navigate to the 'dist' folder to find autobuyer.exe
pause

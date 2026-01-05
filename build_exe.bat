@echo off
echo Building autobuyer.exe...
python -m PyInstaller --noconfirm --onefile --console --name "autobuyer" ^
    --hidden-import "cv2" ^
    --hidden-import "numpy" ^
    --hidden-import "pyautogui" ^
    --hidden-import "mss" ^
    --hidden-import "keyboard" ^
    --hidden-import "win32gui" ^
    "autobuyer.py"

echo Build complete.
echo Copying template images...
copy "*.png" "dist\"
echo Please navigate to the 'dist' folder to find autobuyer.exe
pause

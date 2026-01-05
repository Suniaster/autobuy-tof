# Tower of Fantasy Autobuyer

A robust, resolution-independent automation script for purchasing items in *Tower of Fantasy*. This tool uses image recognition to automatically refresh the store, purchase items, and confirm transactions.

## ✨ Features

-   **Multi-Resolution Support**: Works on any screen resolution (720p, 1080p, 1440p, etc.) and handles non-standard UI scaling using smart multi-scale template matching.
-   **Dual Operation Modes**:
    -   **Mode 1 (Fast Mode)**: Runs continuously (foreground preferred) for maximum speed. Auto-refreshes store.
    -   **Mode 2 (Slow Mode)**: Designed for background monitoring. Can detect items while the game is minimized or in the background and will automatically restore the window to perform the purchase.
-   **Smart Control**:
    -   **F1**: Pause / Resume the bot instantly.
    -   **F2**: Stop and exit the script.
-   **Auto-Recovery**: Automatically resets to the "Refreshing" state if the buying process gets stuck or times out.

## 🛠 Prerequisites

-   Windows OS
-   **Administrator Privileges** (Required for the bot to interact with the game window).

## 🚀 Usage

1.  Run the executable **as Administrator**:
    ```bash
    autobuyer.exe
    ```

    **Running from Source:**
    ```bash
    python src/autobuyer.py
    ```
2.  Select your desired mode (1 for Speed, 2 for Background Use).
3.  The bot will wait for the "Tower of Fantasy" window to appear.
4.  Once active, it will begin the generic Shop loop:
    -   Scans for specific Item Template.
    -   Clicks "Buy".
    -   Clicks "Confirm".
    -   Clicks "OK".
    -   Refreshes (if in Fast Mode).

## ⚠️ Dangers & Disclaimers

> [!CAUTION]
> **USE AT YOUR OWN RISK.**

-   **Ban Risk**: Automating actions (botting) is strictly against the *Tower of Fantasy* Terms of Service. Using this script could lead to a **permanent account ban**.
-   **Detection**: While this script uses image recognition (which is harder to detect than memory injection), it uses `pyautogui` for mouse movements, which can be heuristically detected by anti-cheat systems if used for prolonged periods without breaks.
-   **Supervision**: Always supervise the bot. Do not leave it running unattended for long periods.
-   **Mouse Control**: The script takes control of your mouse to click. Do not try to use your computer for other tasks while the bot is actively buying.

## 📝 Templates

The bot relies on `.png` templates located in `assets/autobuyer/`:
-   `button_template.png`: The item or button to look for.
-   `confirm_template.png`: The "Confirm" button in the buy dialog.
-   `ok_template.png`: The "OK" button after purchase.
-   `refresh_icon_template.png`: The refresh button icon (for Fast Mode).

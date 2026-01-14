# Autobuyer V2 - Graph Based Automation

Automated buying bot for Tower of Fantasy (or any similar UI) using a generic Graph-based State Machine.

## Core Concepts

The application has been refactored from a hardcoded script to a flexible engine defined by **Vertices** (States) and **Edges** (Transitions).

### Objects
1.  **Vertex (State)**: Represents a screen or distinct state of the bot (e.g., "Refreshing", "Buying", "Confirming").
2.  **Edge (Transition)**: A link between states, triggered by an event.
    *   **Trigger**: Condition to fire the edge (e.g., "Find Template Image", "Wait 1 Second").
    *   **Action**: What to do when triggered (e.g., "Click the found image", "Wait").

## Project Structure

```
autobuyer/
├── assets/                 # Image templates (.png/.bmp)
├── graph.json              # The saved state machine configuration
├── graph.json.layout       # Editor layout positions
├── src/
│   ├── autobuyer_v2.py     # MAIN ENTRY POINT
│   ├── engine/             # Core Engine Package
│   │   ├── model.py        # Vertex/Edge Logic
│   │   ├── executor.py     # Runtime logic
│   │   ├── editor.py       # Visual Graph Editor
│   ├── helper/             # Legacy utilities
```

## How to Use

### 1. Visual Editor
Create and modify your automation logic visually.

```bash
python src/autobuyer_v2.py --edit
```

*   **Left Toolbar**: Select modes (Select, Add Node, Connect, Delete).
*   **Right Click**: Context menu for detailed editing.
*   **Paste (Ctrl+V)**: In the Edge Property dialog, stick an image from your clipboard to create a new template automatically.

### 2. Running the Bot
Execute the current `graph.json`.

```bash
python src/autobuyer_v2.py
```

*   **F1**: Pause/Resume
*   **F2**: Stop

## Dependencies
*   Python 3.x
*   OpenCV (`opencv-python`)
*   MSS (`mss`)
*   PyAutoGUI (`pyautogui`)
*   PyWin32 (`pywin32`)
*   **EasyOCR**: Required for 'OCR Watch' triggers. (Installed automatically via pip)
    *   Note: First time usage will download recognition models.

## Development
To switch back to the legacy v1 script, run `src/autobuyer.py`.

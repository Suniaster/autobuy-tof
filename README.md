# Autobuyer V2 - Graph Based Automation

Automated buying bot for Tower of Fantasy (or any similar UI) using a generic Graph-based State Machine.
This engine allows you to visually design automation flows using a flexible node-based editor.

## Core Concepts

The application uses a **Graph State Machine**:
*   **Vertices (States)**: Represents a distinct state of the bot (e.g., "Idle", "Scanning", "Buying").
*   **Edges (Transitions)**: Connections between states that define *when* to move to the next state and *what* to do during the transition.
    *   **Trigger**: The condition that activates the edge (e.g., "Image Found", "OCR Value > 10").
    *   **Action**: The operation performed when the edge is traversed (e.g., "Click", "Press Key").

## Features

### 🎮 Smart Game Integration
*   **Window Selection**: Automatically detects "Tower of Fantasy" windows. If multiple are found, you can select the specific client to target.
*   **Resolution Scaling**: All coordinates (clicks, regions) are resolution-independent. You can design on 1080p and run on 4k; the bot scales actions automatically.
*   **Background Mode**: (Experimental) Allows the bot to capture the game window even if it's not in the foreground.

### 🛠 Visual Editor
*   **Drag & Drop Interface**: Easily creating nodes and connecting them with edges.
*   **Interactive Selectors**:
    *   **Region Selector**: Visually draw a box on the game window for OCR or search regions.
    *   **Point Selector**: Click on the game window to record X/Y coordinates.
*   **Clipboard Integration**: Paste images directly from your clipboard into the "Template" or "Identity" fields to save them as assets automatically.
*   **Dark Mode**: Modern, comfortable dark UI based on CustomTkinter.
*   **Macro Export**: Save and name your automation graphs (`.json`) for easy sharing or switching.

### ⚡ Extensive Logic Support

**Triggers (Conditions):**
*   **Template Match**: Finds an image on screen. Supports `Invert` (Trigger if NOT found) and `Threshold` adjustments.
*   **OCR Watch**: Reads text/numbers from a defined region. Triggers based on numeric conditions (`>`, `<`, `=`, `!=`). Good for monitoring stamina, gold, etc.
*   **Immediate**: Instantly transitions to the next state (useful for logic flows).

**Actions (Outputs):**
*   **Click Match**: Clicks the center of the image found by the Trigger.
*   **Click Position**: Clicks a specific screen coordinate (Scaling supported).
*   **Press Key**: Taps or holds a keyboard key. Supports generic keys plus `left_click` for mouse actions.
*   **Wait**: Pauses for a set duration.
*   **Buzzer**: Plays a system sound (useful for alerts/alarms).
*   **Input Modifiers**: All inputs support `Alt`, `Ctrl`, and `Shift` modifiers.

## How to Use

### 1. Visual Editor
Create or modify your automation logic.

```bash
python src/autobuyer_v2.py --edit
```

*   **Left / Right Click**: Select / Context Menu.
*   **Toolbar**:
    *   `+`: Add Node
    *   `→`: Connect Nodes (Drag from Source to Target)
    *   `Trash`: Delete selected
*   **Ctrl+V**: Paste image into selected input fields.

### 2. Running the Bot
Execute the active `graph.json`.

```bash
python src/autobuyer_v2.py
```

*   **Window Selection**: If multiple game clients are open, the CLI will ask you to choose one.
*   **F1**: Pause / Resume the automation.
*   **F2**: Stop and Exit.

## Project Structure

```
autobuyer/
├── assets/                 # Image templates and saved assets
├── graph.json              # Default state machine configuration
├── src/
│   ├── autobuyer_v2.py     # Entry point (CLI & Runner)
│   ├── engine/             # Core Engine
│   │   ├── editor.py       # Visual Editor
│   │   ├── executor.py     # Runtime logic
│   │   ├── model.py        # Data structures
│   │   ├── triggers/       # Trigger implementations (OCR, Template)
│   │   ├── actions/        # Action implementations (Input, System)
```

## Dependencies

*   **Python 3.x**
*   **CustomTkinter** (UI)
*   **EasyOCR** (Text Recognition)
*   **OpenCV** (`opencv-python`)
*   **MSS** (Fast Screen Capture)
*   **PyAutoGUI** / **Keyboard** (Input Simulation)
*   **PyWin32** (Window Management)

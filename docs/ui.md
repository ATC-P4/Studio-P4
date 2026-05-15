# User Interface Reference

This section provides the technical API documentation for the **View layer** (built with PySide6). The UI is entirely decoupled from the business logic, relying on Data Transfer Objects (DTOs) to draw the screen and Qt Signals to communicate user actions.

To help you navigate the frontend components:

* **`MainWindow`**: The primary application shell. It catches the DTOs from the backend and coordinates all visual updates (designed primarily for sighted collaborators).
* **`StartupDialog`**: The initial launch window that handles the "New Project" vs. "Load Project" selection flow before the main studio opens.
* **`TrackWidget`**: The reusable UI element that visually represents an individual track's state (e.g., armed, muted, instrument name) within the main list.

*Note: The detailed documentation below is automatically generated directly from the Python source code docstrings.*

## Application Windows
::: ui.main_window.MainWindow

::: ui.startup_dialog.StartupDialog

## Components
::: ui.track_widget.TrackWidget
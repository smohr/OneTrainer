import platform
from pathlib import Path

# Kept get_icon_path as it's a generic utility used by the PySide6 code.
# Removed bind_mousewheel and the Tkinter-specific set_window_icon.

def get_icon_path() -> str | None:
    """Get the application icon path based on the current platform."""
    icon_dir = Path("resources/icons")
    system = platform.system()

    ico_path = icon_dir / "icon.ico"
    png_path = icon_dir / "icon.png"

    if system == "Windows":
        if ico_path.exists():
            return str(ico_path)
        elif png_path.exists(): # Fallback to PNG if ICO not found
            return str(png_path)
    elif system == "Linux":
        if png_path.exists():
            return str(png_path)
    elif system == "Darwin":  # macOS
        # macOS often uses .icns or relies on App bundles.
        # For direct window icon setting, .png is often supported.
        if png_path.exists(): # Prefer PNG for macOS window icons if available
            return str(png_path)
        elif ico_path.exists(): # Fallback, though less common for window icons on mac
             return str(ico_path)
    
    # Fallback if platform-specific not found or other platform
    if png_path.exists():
        return str(png_path)
    if ico_path.exists():
        return str(ico_path)
        
    print("Warning: Application icon file not found in resources/icons/")
    return None

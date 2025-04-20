#!/usr/bin/env python3
"""
Helper script to run the LaTeX2Video GUI with a patch to disable XInitThreads.
This script attempts to patch the _tkinter module to avoid XCB issues.
"""

import os
import sys
import importlib
import types
import tkinter as tk
from tkinter import ttk, messagebox

# Configure environment variables to help with X11/XCB issues
os.environ['QT_X11_NO_MITSHM'] = '1'  # For PyQt/PySide
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-dir'
os.environ['PYTHONUNBUFFERED'] = '1'  # Ensure output is not buffered

# Try to patch _tkinter to avoid XInitThreads
try:
    import _tkinter
    
    # Check if XInitThreads is already called
    if hasattr(_tkinter, '_tkinter_used_xinit_threads'):
        print("XInitThreads already patched.")
    else:
        # Save the original create function
        original_create = _tkinter.create
        
        # Define a patched create function that doesn't use XInitThreads
        def patched_create(*args, **kwargs):
            # Call the original create function
            result = original_create(*args, **kwargs)
            # Mark that we've patched XInitThreads
            _tkinter._tkinter_used_xinit_threads = True
            return result
        
        # Replace the create function with our patched version
        _tkinter.create = patched_create
        
        print("Successfully patched _tkinter.create to avoid XInitThreads issues.")
except Exception as e:
    print(f"Warning: Failed to patch _tkinter: {e}")
    print("Will try to run GUI anyway.")

def main():
    """Main function to run the GUI"""
    try:
        print("Attempting to run LaTeX2Video GUI (Patched Version)...")
        
        # Add the parent directory to the path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(script_dir)
        
        # Import the GUI module
        from src.gui_final import LaTeX2VideoGUI
        
        # Create the GUI
        root = tk.Tk()
        app = LaTeX2VideoGUI(root)
        root.mainloop()
        
        return 0
        
    except Exception as e:
        print(f"ERROR: Failed to run GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

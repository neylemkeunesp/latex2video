#!/usr/bin/env python3
"""
Helper script to run the LaTeX2Video GUI with proper error handling.
This script will try to run the GUI and provide helpful error messages
if it fails due to display issues.
"""

import os
import sys
import subprocess
import traceback
import ctypes

# Try to initialize X11 threads, but catch any errors
try:
    x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
    x11.XInitThreads()
    print("X11 threads initialized successfully")
except Exception as e:
    print(f"Warning: Could not initialize X11 threads: {e}")
    print("GUI may still work, but might be unstable with threading")

# Set environment variables to help with X11/XCB issues
os.environ['QT_X11_NO_MITSHM'] = '1'  # For PyQt/PySide
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-dir'
os.environ['PYTHONUNBUFFERED'] = '1'  # Ensure output is not buffered
os.environ['TK_LIBRARY'] = os.environ.get('TK_LIBRARY', '')  # Ensure Tk library is found
#os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':0')

def check_display():
    """Check if a display server is available"""
    return os.environ.get('DISPLAY') is not None

def suggest_cli():
    """Print a message suggesting the CLI version"""
    print("\n" + "="*80)
    print("SUGGESTION: Use the command-line interface instead:")
    print("  python run_cli.py assets/presentation.tex --save-scripts")
    print("\nFor more information, see README_CLI.md")
    print("="*80 + "\n")

def main():
    """Try to run the GUI and handle errors"""
    
    # Check if display is available
    if not check_display():
        print("ERROR: No display server available (DISPLAY environment variable not set).")
        print("You need a display server to run the GUI version.")
        print("\nOptions:")
        print("1. If you're using SSH, enable X11 forwarding with 'ssh -X' or 'ssh -Y'")
        print("2. If you're on a headless server, set up a VNC server")
        print("3. Use the command-line interface instead (recommended)")
        suggest_cli()
        return 1
    
    # Try to run the GUI
    try:
        print("Attempting to run LaTeX2Video GUI...")
        
        # Import the GUI module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from src.gui_final import LaTeX2VideoGUI
        import tkinter as tk
        print("Depois do import tkinter") 
        # Create the GUI
        root = tk.Tk()
        print("Depois da criação do Tk")
        app = LaTeX2VideoGUI(root)
        root.mainloop()
        
        return 0
        
    except ImportError as e:
        print(f"ERROR: Failed to import GUI modules: {e}")
        print("Make sure you have installed all required packages:")
        print("  pip install -r requirements.txt")
        return 1
        
    except tk.TclError as e:
        if "couldn't connect to display" in str(e):
            print(f"ERROR: {e}")
            print("\nThis error occurs when:")
            print("1. You don't have a display server available")
            print("2. X11 forwarding is not set up correctly")
            print("\nSee README_GUI.md for instructions on setting up X11 forwarding.")
            suggest_cli()
        else:
            print(f"ERROR: Tkinter error: {e}")
            traceback.print_exc()
        return 1
        
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Helper script to run the LaTeX2Video GUI with a fix for XCB issues.
This script avoids calling XInitThreads directly.
"""

import os
import sys
import subprocess
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import yaml
import re
import logging
from typing import List, Dict, Optional

# Configure environment variables to help with X11/XCB issues
os.environ['QT_X11_NO_MITSHM'] = '1'  # For PyQt/PySide
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-dir'
os.environ['PYTHONUNBUFFERED'] = '1'  # Ensure output is not buffered

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('latex2video_gui.log')
    ]
)

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
    """Main function to run the GUI"""
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
    
    # Try to run the GUI using a subprocess to avoid XInitThreads issues
    try:
        print("Attempting to run LaTeX2Video GUI (Fixed Version)...")
        
        # Import the GUI module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Get the current script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create a temporary Python script
        temp_script = os.path.join(script_dir, "temp_gui_launcher.py")
        with open(temp_script, "w") as f:
            f.write("""#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import ttk

# Add the parent directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import the GUI module
from src.gui_final import LaTeX2VideoGUI

# Create the GUI
root = tk.Tk()
app = LaTeX2VideoGUI(root)
root.mainloop()
""")
        
        # Make the script executable
        os.chmod(temp_script, 0o755)
        
        # Run the GUI in a subprocess to avoid XInitThreads issues
        cmd = [sys.executable, temp_script]
        
        # Run the subprocess
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        # Check if there was an error
        if process.returncode != 0:
            print(f"ERROR: Failed to run GUI: {stderr}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

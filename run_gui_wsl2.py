#!/usr/bin/env python3
"""
Helper script to run the LaTeX2Video GUI with proper error handling for WSL2.
This script will try to run the GUI and provide helpful error messages
if it fails due to display issues.
"""

import os
import sys
import subprocess
import traceback
import time

# Set environment variables for WSL2
os.environ['DISPLAY'] = ':0'
os.environ['LIBGL_ALWAYS_INDIRECT'] = '1'
os.environ['QT_X11_NO_MITSHM'] = '1'
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-dir'
os.environ['PYTHONUNBUFFERED'] = '1'

def check_display():
    """Check if a display server is available"""
    return os.environ.get('DISPLAY') is not None

def suggest_cli():
    """Print a message suggesting the CLI version"""
    print("\n" + "="*80)
    print("SUGGESTION: Use the command-line interface instead:")
    print("  python3 run_cli.py assets/presentation.tex --save-scripts")
    print("\nFor more information, see README_CLI.md")
    print("="*80 + "\n")

def check_x11():
    """Check if X11 is working by running a simple X11 application"""
    try:
        print("Checking X11 connection...")
        # Start xclock in the background
        process = subprocess.Popen(['xclock'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Wait a bit to see if it starts
        time.sleep(1)
        # Check if the process is still running
        if process.poll() is None:
            # Process is still running, so X11 is working
            # Kill the process
            process.terminate()
            return True
        return False
    except Exception as e:
        print(f"X11 check error: {e}")
        return False

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
    
    # Check if X11 is working
    if not check_x11():
        print("ERROR: X11 connection test failed.")
        print("X11 forwarding is not working correctly.")
        print("\nIf you're using WSL2, make sure you have an X server running on Windows.")
        print("Popular X servers for Windows include:")
        print("- VcXsrv (https://sourceforge.net/projects/vcxsrv/)")
        print("- Xming (https://sourceforge.net/projects/xming/)")
        print("- X410 (https://x410.dev/)")
        suggest_cli()
        return 1
    
    print("X11 connection test successful!")
    
    # Check if run_cli.py has a --gui option
    try:
        print("Checking if run_cli.py supports --gui option...")
        help_output = subprocess.check_output(['python3', 'run_cli.py', '--help'], stderr=subprocess.STDOUT, text=True)
        if '--gui' in help_output:
            print("run_cli.py supports --gui option, trying to use it...")
            # Try to run the GUI using the CLI version with --gui flag
            try:
                print("Attempting to run LaTeX2Video GUI via CLI...")
                
                # Use the CLI version with --gui flag
                result = subprocess.run(
                    ['python3', 'run_cli.py', '--gui'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode != 0:
                    print(f"ERROR: Failed to run GUI via CLI: {result.stderr}")
                    print("Falling back to direct GUI import...")
                else:
                    print("GUI launched successfully via CLI.")
                    return 0
                
            except Exception as e:
                print(f"ERROR: Failed to run GUI via CLI: {e}")
                print("Falling back to direct GUI import...")
        else:
            print("run_cli.py does not support --gui option, falling back to direct GUI import...")
    except Exception as e:
        print(f"Error checking run_cli.py: {e}")
        print("Falling back to direct GUI import...")
    
    # Try to run the GUI directly
    try:
        print("Attempting to run LaTeX2Video GUI directly...")
        
        # Import the GUI module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # First check if pdf2image is installed
        try:
            import pdf2image
            print("pdf2image is installed.")
        except ImportError:
            print("ERROR: pdf2image is not installed.")
            print("This is a required dependency for the GUI.")
            print("Please install it with: pip install pdf2image")
            print("You may also need to install poppler-utils:")
            print("  On Ubuntu/Debian: sudo apt-get install poppler-utils")
            print("  On macOS: brew install poppler")
            print("  On Windows: See https://github.com/Belval/pdf2image#windows")
            return 1
        
        # Try to import and run the GUI
        from src.gui_final import LaTeX2VideoGUI
        import tkinter as tk
        
        # Create the GUI
        root = tk.Tk()
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

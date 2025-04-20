#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from src.gui_final import LaTeX2VideoGUI

def main():
    """Main entry point for the LaTeX2Video application"""
    root = tk.Tk()
    app = LaTeX2VideoGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

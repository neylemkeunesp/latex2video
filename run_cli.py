#!/usr/bin/env python3
"""
Command-line wrapper for LaTeX2Video that doesn't require a GUI.
This script provides a simple way to run the automated video generation
process without needing a display server.
"""

import os
import sys
import argparse
from src.automated_video_generation import main as automated_main

def main():
    """
    Parse command-line arguments and run the automated video generation process.
    """
    parser = argparse.ArgumentParser(description="Generate a narrated video from a LaTeX presentation without requiring a GUI.")
    parser.add_argument("latex_file", help="Path to the input LaTeX (.tex) file.")
    parser.add_argument("-c", "--config", default="config/config.yaml", help="Path to the configuration YAML file.")
    parser.add_argument("-s", "--save-scripts", action="store_true", help="Save the generated scripts to files.")
    
    args = parser.parse_args()
    
    # Call the main function from automated_video_generation
    sys.argv = [sys.argv[0]] + [args.latex_file]
    if args.config != "config/config.yaml":
        sys.argv.extend(["-c", args.config])
    if args.save_scripts:
        sys.argv.append("--save-scripts")
    
    automated_main()

if __name__ == "__main__":
    main()

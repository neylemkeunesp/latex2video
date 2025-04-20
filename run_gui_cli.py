#!/usr/bin/env python3
"""
Simplified GUI for LaTeX2Video that uses the CLI version under the hood.
This script provides a basic GUI interface that calls the CLI commands,
avoiding the XCB errors that occur with the full Tkinter GUI in WSL2.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Set environment variables for WSL2
os.environ['DISPLAY'] = ':0'
os.environ['LIBGL_ALWAYS_INDIRECT'] = '1'
os.environ['QT_X11_NO_MITSHM'] = '1'
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-dir'
os.environ['PYTHONUNBUFFERED'] = '1'

class SimplifiedGUI:
    """A simplified GUI that uses the CLI version under the hood"""
    def __init__(self, root):
        self.root = root
        self.root.title("LaTeX2Video (CLI-based GUI)")
        self.root.geometry("600x400")
        
        # Initialize variables
        self.latex_file_path = tk.StringVar()
        self.config_file_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        
        # Set default paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path.set(os.path.join(script_dir, "config", "config.yaml"))
        self.output_dir.set(os.path.join(script_dir, "output"))
        
        # Create the main UI
        self.create_ui()
        
        # Initialize status
        self.update_status("Ready")
    
    def create_ui(self):
        """Create the main user interface"""
        # Create main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create file selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        # LaTeX file selection
        ttk.Label(file_frame, text="LaTeX File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.latex_file_path, width=40).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_latex_file).grid(row=0, column=2, padx=5, pady=5)
        
        # Config file selection
        ttk.Label(file_frame, text="Config File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.config_file_path, width=40).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_config_file).grid(row=1, column=2, padx=5, pady=5)
        
        # Output directory selection
        ttk.Label(file_frame, text="Output Directory:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.output_dir, width=40).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_output_dir).grid(row=2, column=2, padx=5, pady=5)
        
        # Configure grid column weights
        file_frame.columnconfigure(1, weight=1)
        
        # Create actions frame
        actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create buttons for different actions
        ttk.Button(actions_frame, text="Generate Scripts", command=self.generate_scripts).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="Generate Images", command=self.generate_images).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="Generate Audio", command=self.generate_audio).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="Assemble Video", command=self.assemble_video).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="Generate All", command=self.generate_all).pack(fill=tk.X, pady=5)
        
        # Create status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
    
    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def browse_latex_file(self):
        """Open file dialog to select LaTeX file"""
        file_path = filedialog.askopenfilename(
            title="Select LaTeX File",
            filetypes=[("LaTeX Files", "*.tex"), ("All Files", "*.*")]
        )
        if file_path:
            self.latex_file_path.set(file_path)
            self.update_status(f"LaTeX file selected: {file_path}")
    
    def browse_config_file(self):
        """Open file dialog to select config file"""
        file_path = filedialog.askopenfilename(
            title="Select Config File",
            filetypes=[("YAML Files", "*.yaml"), ("All Files", "*.*")]
        )
        if file_path:
            self.config_file_path.set(file_path)
            self.update_status(f"Config file selected: {file_path}")
    
    def browse_output_dir(self):
        """Open directory dialog to select output directory"""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir.set(dir_path)
            self.update_status(f"Output directory selected: {dir_path}")
    
    def run_cli_command(self, args, wait_message, success_message):
        """Run a CLI command and show progress"""
        latex_file = self.latex_file_path.get()
        config_file = self.config_file_path.get()
        
        if not latex_file:
            messagebox.showerror("Error", "Please select a LaTeX file first.")
            return False
        
        if not os.path.exists(latex_file):
            messagebox.showerror("Error", f"LaTeX file not found: {latex_file}")
            return False
        
        # Build the command
        cmd = ["python3", "run_cli.py", latex_file]
        
        # Add config file if specified
        if config_file and os.path.exists(config_file):
            cmd.extend(["-c", config_file])
        
        # Add any additional arguments
        cmd.extend(args)
        
        self.update_status(wait_message)
        
        try:
            # Run the command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Show a progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing")
            progress_window.geometry("400x300")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Add a progress bar
            ttk.Label(progress_window, text=wait_message).pack(pady=10)
            progress_bar = ttk.Progressbar(progress_window, mode="indeterminate", length=300)
            progress_bar.pack(pady=10, padx=10, fill=tk.X)
            progress_bar.start()
            
            # Add a text area for output
            output_text = tk.Text(progress_window, wrap=tk.WORD, height=10)
            output_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
            
            # Add a cancel button
            cancel_button = ttk.Button(progress_window, text="Cancel", command=lambda: process.terminate())
            cancel_button.pack(pady=10)
            
            # Function to update the output text
            def update_output():
                if process.poll() is None:
                    # Process is still running
                    try:
                        # Read any available output
                        stdout_line = process.stdout.readline()
                        if stdout_line:
                            output_text.insert(tk.END, stdout_line)
                            output_text.see(tk.END)
                        
                        stderr_line = process.stderr.readline()
                        if stderr_line:
                            output_text.insert(tk.END, stderr_line)
                            output_text.see(tk.END)
                        
                        # Schedule the next update
                        self.root.after(100, update_output)
                    except Exception as e:
                        output_text.insert(tk.END, f"Error reading output: {e}\n")
                        output_text.see(tk.END)
                        self.root.after(100, update_output)
                else:
                    # Process has finished
                    progress_bar.stop()
                    cancel_button.config(text="Close", command=progress_window.destroy)
                    
                    # Read any remaining output
                    stdout, stderr = process.communicate()
                    if stdout:
                        output_text.insert(tk.END, stdout)
                    if stderr:
                        output_text.insert(tk.END, stderr)
                    
                    output_text.see(tk.END)
                    
                    # Show success or error message
                    if process.returncode == 0:
                        self.update_status(success_message)
                        messagebox.showinfo("Success", success_message)
                    else:
                        error_msg = f"Command failed with return code {process.returncode}"
                        self.update_status(error_msg)
                        messagebox.showerror("Error", error_msg)
            
            # Start updating the output
            update_output()
            
            return True
            
        except Exception as e:
            self.update_status(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to run command: {e}")
            return False
    
    def generate_scripts(self):
        """Generate narration scripts"""
        self.run_cli_command(
            ["--save-scripts"],
            "Generating narration scripts...",
            "Narration scripts generated successfully."
        )
    
    def generate_images(self):
        """Generate slide images"""
        self.run_cli_command(
            ["--images-only"],
            "Generating slide images...",
            "Slide images generated successfully."
        )
    
    def generate_audio(self):
        """Generate audio files"""
        self.run_cli_command(
            ["--audio-only"],
            "Generating audio files...",
            "Audio files generated successfully."
        )
    
    def assemble_video(self):
        """Assemble video from existing images and audio"""
        self.run_cli_command(
            ["--assemble-only"],
            "Assembling video...",
            "Video assembled successfully."
        )
    
    def generate_all(self):
        """Generate everything: scripts, images, audio, and video"""
        self.run_cli_command(
            [],
            "Generating everything...",
            "Video generation complete."
        )

def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = SimplifiedGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Modified version of gui_final.py for WSL2 compatibility.
This version avoids using threading which can cause XCB errors in WSL2.
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import yaml
import re
from typing import List, Dict, Optional

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.latex_parser import parse_latex_file, Slide
from src.chatgpt_script_generator import format_slide_for_chatgpt, clean_chatgpt_response
from src.image_generator import generate_slide_images
from src.audio_generator import generate_all_audio
from src.simple_video_assembler import assemble_video

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'latex2video_gui.log'))
    ]
)

class RedirectText:
    """Class to redirect stdout/stderr to a tkinter Text widget"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, string):
        self.buffer += string
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")

    def flush(self):
        pass

class LaTeX2VideoGUI:
    """Main GUI application for LaTeX2Video (WSL2 compatible version)"""
    def __init__(self, root):
        self.root = root
        self.root.title("LaTeX2Video (WSL2 Compatible)")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize variables
        self.latex_file_path = tk.StringVar()
        self.config_file_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.current_slide_index = 0
        self.slides = []
        self.narrations = []
        self.config = {}
        
        # Set default paths
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_file_path.set(os.path.join(script_dir, "config", "config.yaml"))
        self.output_dir.set(os.path.join(script_dir, "output"))
        
        # Load config if exists
        self.load_config()
        
        # Create the main UI
        self.create_ui()
        
        # Initialize status
        self.update_status("Ready")

    def load_config(self):
        """Load configuration from YAML file"""
        config_path = self.config_file_path.get()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                logging.info(f"Configuration loaded from {config_path}")
                
                # Add output_dir to config
                self.config['output_dir'] = self.output_dir.get()
                
                # Ensure output directories exist
                os.makedirs(self.output_dir.get(), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir.get(), 'slides'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir.get(), 'audio'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir.get(), 'temp_pdf'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir.get(), 'chatgpt_prompts'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir.get(), 'chatgpt_responses'), exist_ok=True)
                
                return True
            except Exception as e:
                logging.error(f"Error loading config: {e}")
                messagebox.showerror("Error", f"Failed to load configuration: {e}")
                return False
        else:
            logging.warning(f"Config file not found: {config_path}")
            return False

    def create_ui(self):
        """Create the main user interface"""
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create top frame for file selection
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # LaTeX file selection
        ttk.Label(top_frame, text="LaTeX File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(top_frame, textvariable=self.latex_file_path, width=50).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(top_frame, text="Browse...", command=self.browse_latex_file).grid(row=0, column=2, padx=5, pady=5)
        
        # Config file selection
        ttk.Label(top_frame, text="Config File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(top_frame, textvariable=self.config_file_path, width=50).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(top_frame, text="Browse...", command=self.browse_config_file).grid(row=1, column=2, padx=5, pady=5)
        
        # Output directory selection
        ttk.Label(top_frame, text="Output Directory:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(top_frame, textvariable=self.output_dir, width=50).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(top_frame, text="Browse...", command=self.browse_output_dir).grid(row=2, column=2, padx=5, pady=5)
        
        # Configure grid column weights
        top_frame.columnconfigure(1, weight=1)
        
        # Create middle frame with notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create editor tab
        editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(editor_frame, text="Narration Editor")
        
        # Create editor controls
        editor_controls = ttk.Frame(editor_frame)
        editor_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(editor_controls, text="Parse LaTeX", command=self.parse_latex).pack(side=tk.LEFT, padx=5)
        ttk.Button(editor_controls, text="Generate Scripts", command=self.generate_scripts).pack(side=tk.LEFT, padx=5)
        ttk.Button(editor_controls, text="Save Scripts", command=self.save_scripts).pack(side=tk.LEFT, padx=5)
        ttk.Button(editor_controls, text="Load Scripts", command=self.load_scripts).pack(side=tk.LEFT, padx=5)
        
        # Create slide navigation
        nav_frame = ttk.Frame(editor_controls)
        nav_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(nav_frame, text="< Prev", command=self.prev_slide).pack(side=tk.LEFT, padx=2)
        self.slide_label = ttk.Label(nav_frame, text="Slide: 0/0")
        self.slide_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="Next >", command=self.next_slide).pack(side=tk.LEFT, padx=2)
        
        # Create editor panes
        editor_panes = ttk.PanedWindow(editor_frame, orient=tk.HORIZONTAL)
        editor_panes.pack(fill=tk.BOTH, expand=True)
        
        # Left pane - slide content
        left_frame = ttk.Frame(editor_panes)
        ttk.Label(left_frame, text="Slide Content:").pack(anchor=tk.W, pady=(0, 5))
        self.slide_content_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=20, width=50)
        self.slide_content_text.pack(fill=tk.BOTH, expand=True)
        self.slide_content_text.config(state=tk.DISABLED)
        editor_panes.add(left_frame, weight=1)
        
        # Right pane - narration script
        right_frame = ttk.Frame(editor_panes)
        ttk.Label(right_frame, text="Narration Script:").pack(anchor=tk.W, pady=(0, 5))
        self.narration_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=20, width=50)
        self.narration_text.pack(fill=tk.BOTH, expand=True)
        editor_panes.add(right_frame, weight=1)
        
        # Create generation tab
        generation_frame = ttk.Frame(self.notebook)
        self.notebook.add(generation_frame, text="Video Generation")
        
        # Create generation controls
        gen_controls = ttk.Frame(generation_frame)
        gen_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(gen_controls, text="Generate Images", command=self.generate_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_controls, text="Generate Audio", command=self.generate_audio).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_controls, text="Assemble Video", command=self.assemble_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(gen_controls, text="Generate All", command=self.generate_all).pack(side=tk.LEFT, padx=5)
        
        # Create progress bar
        self.progress_frame = ttk.Frame(generation_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.progress_frame, text="Progress:").pack(side=tk.LEFT, padx=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_label = ttk.Label(self.progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        # Create log output
        ttk.Label(generation_frame, text="Log Output:").pack(anchor=tk.W, pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(generation_frame, wrap=tk.WORD, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # Redirect stdout and stderr to the log text widget
        self.stdout_redirect = RedirectText(self.log_text)
        self.stderr_redirect = RedirectText(self.log_text)
        sys.stdout = self.stdout_redirect
        sys.stderr = self.stderr_redirect
        
        # Create bottom frame for status
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(bottom_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X)
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        logging.info(message)

    def update_progress(self, value, max_value):
        """Update the progress bar"""
        percentage = int(value / max_value * 100)
        self.progress_bar['value'] = percentage
        self.progress_label.config(text=f"{percentage}%")
        self.root.update_idletasks()

    def on_close(self):
        """Handle window close event"""
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        
        # Close the window
        self.root.destroy()

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
            self.load_config()
            self.update_status(f"Config file selected: {file_path}")

    def browse_output_dir(self):
        """Open directory dialog to select output directory"""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir.set(dir_path)
            self.config['output_dir'] = dir_path
            
            # Ensure output directories exist
            os.makedirs(dir_path, exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'slides'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'audio'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'temp_pdf'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'chatgpt_prompts'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'chatgpt_responses'), exist_ok=True)
            
            self.update_status(f"Output directory selected: {dir_path}")

    def parse_latex(self):
        """Parse the LaTeX file and extract slides"""
        latex_file = self.latex_file_path.get()
        if not latex_file:
            messagebox.showerror("Error", "Please select a LaTeX file first.")
            return
        
        if not os.path.exists(latex_file):
            messagebox.showerror("Error", f"LaTeX file not found: {latex_file}")
            return
        
        self.update_status("Parsing LaTeX file...")
        
        try:
            # Parse LaTeX file
            self.slides = parse_latex_file(latex_file)
            
            if not self.slides:
                messagebox.showerror("Error", "Failed to parse slides from LaTeX file.")
                self.update_status("Failed to parse LaTeX file.")
                return
            
            # Initialize narrations list with empty strings
            self.narrations = [""] * len(self.slides)
            
            # Update UI
            self.current_slide_index = 0
            self.update_slide_display()
            
            self.update_status(f"Successfully parsed {len(self.slides)} slides.")
            messagebox.showinfo("Success", f"Successfully parsed {len(self.slides)} slides.")
            
        except Exception as e:
            logging.error(f"Error parsing LaTeX file: {e}")
            messagebox.showerror("Error", f"Failed to parse LaTeX file: {e}")
            self.update_status("Error parsing LaTeX file.")

    def generate_scripts(self):
        """Generate narration scripts for all slides"""
        if not self.slides:
            messagebox.showerror("Error", "No slides available. Please parse a LaTeX file first.")
            return
        
        self.update_status("Generating narration scripts...")
        
        try:
            # Generate scripts for all slides
            for i, slide in enumerate(self.slides):
                # Update progress
                self.update_progress(i, len(self.slides))
                
                # Format slide for script generation
                formatted_content = format_slide_for_chatgpt(slide, self.slides, i)
                
                # For now, we'll use a simple template-based approach
                # In a real implementation, this would call the OpenAI API
                
                # Simple template-based narration
                if slide.title == "Title Page":
                    narration = f"Bem-vindos à nossa apresentação sobre {slide.content.replace('Title: ', '').replace('Author: ', 'por ')}."
                elif slide.title == "Outline":
                    narration = "Vamos ver os principais tópicos que serão abordados nesta apresentação."
                elif slide.title.startswith("Section:"):
                    section_name = slide.title.replace("Section:", "").strip()
                    narration = f"Agora vamos falar sobre {section_name}."
                else:
                    # Basic narration for content slides
                    narration = f"{slide.title}. "
                    
                    # Add content, removing LaTeX commands
                    content_text = re.sub(r'\\[a-zA-Z]+(\{.*?\})?', '', slide.content)
                    content_text = re.sub(r'\$.*?\$', '', content_text)  # Remove math
                    content_text = re.sub(r'\s+', ' ', content_text).strip()
                    
                    if content_text:
                        narration += content_text
                    else:
                        narration += f"Este slide apresenta informações sobre {slide.title}."
                
                # Store the narration
                self.narrations[i] = narration
                
                # Process UI events to keep the GUI responsive
                self.root.update()
            
            # Update the display
            self.update_progress(len(self.slides), len(self.slides))
            self.update_slide_display()
            
            self.update_status("Narration scripts generated.")
            messagebox.showinfo("Success", "Narration scripts generated for all slides.")
            
        except Exception as e:
            logging.error(f"Error generating scripts: {e}")
            messagebox.showerror("Error", f"Failed to generate scripts: {e}")
            self.update_status("Error generating scripts.")

    def save_scripts(self):
        """Save the current narration scripts"""
        if not self.slides or not self.narrations:
            messagebox.showerror("Error", "No narration scripts to save.")
            return
        
        # Update the current narration from the text widget
        current_narration = self.narration_text.get("1.0", tk.END).strip()
        if self.current_slide_index < len(self.narrations):
            self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files
        output_dir = os.path.join(self.output_dir.get(), 'chatgpt_responses')
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            for i, narration in enumerate(self.narrations):
                # Update progress
                self.update_progress(i, len(self.narrations))
                
                file_path = os.path.join(output_dir, f"slide_{i+1}_response.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(narration)
                
                # Process UI events to keep the GUI responsive
                self.root.update()
            
            self.update_progress(len(self.narrations), len(self.narrations))
            self.update_status("Narration scripts saved.")
            messagebox.showinfo("Success", f"Narration scripts saved to {output_dir}")
            
        except Exception as e:
            logging.error(f"Error saving scripts: {e}")
            messagebox.showerror("Error", f"Failed to save scripts: {e}")
            self.update_status("Error saving scripts.")

    def load_scripts(self):
        """Load narration scripts from files"""
        if not self.slides:
            messagebox.showerror("Error", "No slides available. Please parse a LaTeX file first.")
            return
        
        output_dir = os.path.join(self.output_dir.get(), 'chatgpt_responses')
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", f"Scripts directory not found: {output_dir}")
            return
        
        try:
            # Load scripts for all slides
            for i in range(len(self.slides)):
                # Update progress
                self.update_progress(i, len(self.slides))
                
                file_path = os.path.join(output_dir, f"slide_{i+1}_response.txt")
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.narrations[i] = f.read().strip()
                
                # Process UI events to keep the GUI responsive
                self.root.update()
            
            # Update the display
            self.update_progress(len(self.slides), len(self.slides))
            self.update_slide_display()
            
            self.update_status("Narration scripts loaded.")
            messagebox.showinfo("Success", "Narration scripts loaded.")
            
        except Exception as e:
            logging.error(f"Error loading scripts: {e}")
            messagebox.showerror("Error", f"Failed to load scripts: {e}")
            self.update_status("Error loading scripts.")

    def prev_slide(self):
        """Navigate to the previous slide"""
        if not self.slides:
            return
        
        # Save current narration
        current_narration = self.narration_text.get("1.0", tk.END).strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Move to previous slide
        if self.current_slide_index > 0:
            self.current_slide_index -= 1
            self.update_slide_display()

    def next_slide(self):
        """Navigate to the next slide"""
        if not self.slides:
            return
        
        # Save current narration
        current_narration = self.narration_text.get("1.0", tk.END).strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Move to next slide
        if self.current_slide_index < len(self.slides) - 1:
            self.current_slide_index += 1
            self.update_slide_display()

    def update_slide_display(self):
        """Update the display with the current slide"""
        if not self.slides or self.current_slide_index >= len(self.slides):
            return
        
        # Get current slide and narration
        slide = self.slides[self.current_slide_index]
        narration = self.narrations[self.current_slide_index] if self.current_slide_index < len(self.narrations) else ""
        
        # Update slide content
        self.slide_content_text.config(state=tk.NORMAL)
        self.slide_content_text.delete("1.0", tk.END)
        self.slide_content_text.insert(tk.END, f"Title: {slide.title}\n\n")
        self.slide_content_text.insert(tk.END, slide.content)
        self.slide_content_text.config(state=tk.DISABLED)
        
        # Update narration text
        self.narration_text.delete("1.0", tk.END)
        self.narration_text.insert(tk.END, narration)
        
        # Update slide label
        self.slide_label.config(text=f"Slide: {self.current_slide_index + 1}/{len(self.slides)}")

    def generate_images(self):
        """Generate images from the LaTeX file (non-threaded version)"""
        if not self.load_config():
            return
        
        latex_file = self.latex_file_path.get()
        if not latex_file or not os.path.exists(latex_file):
            messagebox.showerror("Error", "Please select a valid LaTeX file first.")
            return
        
        self.update_status("Generating slide images...")
        self.progress_bar['value'] = 0
        
        try:
            # Add the LaTeX file path to the configuration
            self.config['latex_file_path'] = os.path.abspath(latex_file)
            
            # Generate slide images
            image_paths = generate_slide_images(latex_file, self.config)
            
            if not image_paths:
                messagebox.showerror("Error", "Failed to generate slide images.")
                self.update_status("Failed to generate slide images.")
                return
            
            self.update_progress(len(image_paths), len(image_paths))
            self.update_status(f"Generated {len(image_paths)} slide images.")
            messagebox.showinfo("Success", f"Generated {len(image_paths)} slide images.")
            
        except Exception as e:
            logging.error(f"Error generating images: {e}")
            messagebox.showerror("Error", f"Failed to generate images: {e}")
            self.update_status("Error generating images.")

    def generate_audio(self):
        """Generate audio files from narration scripts (non-threaded version)"""
        if not self.load_config():
            return
        
        if not self.slides or not self.narrations:
            messagebox.showerror("Error", "No narration scripts available. Please generate scripts first.")
            return
        
        # Save current narration
        current_narration = self.narration_text.get("1.0", tk.END).strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files first
        self.save_scripts()
        
        self.update_status("Generating audio files...")
        self.progress_bar['value'] = 0
        
        try:
            # Generate audio files
            audio_paths = generate_all_audio(self.narrations, self.config)
            
            if not audio_paths:
                messagebox.showerror("Error", "Failed to generate audio files.")
                self.update_status("Failed to generate audio files.")
                return
            
            self.update_progress(len(audio_paths), len(audio_paths))
            self.update_status(f"Generated {len(audio_paths)} audio files.")
            messagebox.showinfo("Success", f"Generated {len(audio_paths)} audio files.")
            
        except Exception as e:
            logging.error(f"Error generating audio: {e}")
            messagebox.showerror("Error", f"Failed to generate audio: {e}")
            self.update_status("Error generating audio.")

    def assemble_video(self):
        """Assemble the final video from images and audio (non-threaded version)"""
        if not self.load_config():
            return
        
        # Check if images and audio files exist
        slides_dir = os.path.join(self.output_dir.get(), 'slides')
        audio_dir = os.path.join(self.output_dir.get(), 'audio')
        
        if not os.path.exists(slides_dir) or not os.listdir(slides_dir):
            messagebox.showerror("Error", "No slide images found. Please generate images first.")
            return
        
        if not os.path.exists(audio_dir) or not os.listdir(audio_dir):
            messagebox.showerror("Error", "No audio files found. Please generate audio first.")
            return
        
        self.update_status("Assembling video...")
        self.progress_bar['value'] = 0
        
        try:
            # Get image and audio files
            image_files = sorted([os.path.join(slides_dir, f) for f in os.listdir(slides_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
            audio_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith('.mp3')])
            
            if len(image_files) != len(audio_files):
                messagebox.showerror("Error", 
                    f"Mismatch between number of images ({len(image_files)}) and audio files ({len(audio_files)}).")
                self.update_status("Failed to assemble video.")
                return
            
            # Update progress periodically during video assembly
            self.update_progress(0, 100)
            self.root.update()
            
            # Assemble video
            output_path = assemble_video(image_files, audio_files, self.config)
            
            if not output_path:
                messagebox.showerror("Error", "Failed to assemble video.")
                self.update_status("Failed to assemble video.")
                return
            
            self.update_progress(100, 100)
            self.update_status(f"Video assembled: {output_path}")
            messagebox.showinfo("Success", f"Video assembled: {output_path}")
            
        except Exception as e:
            logging.error(f"Error assembling video: {e}")
            messagebox.showerror("Error", f"Failed to assemble video: {e}")
            self.update_status("Error assembling video.")

    def generate_all(self):
        """Generate everything: images, audio, and video (non-threaded version)"""
        if not self.load_config():
            return
        
        latex_file = self.latex_file_path.get()
        if not latex_file or not os.path.exists(latex_file):
            messagebox.showerror("Error", "Please select a valid LaTeX file first.")
            return
        
        if not self.slides or not self.narrations:
            messagebox.showerror("Error", "No slides or narrations available. Please parse LaTeX and generate scripts first.")
            return
        
        # Save current narration
        current_narration = self.narration_text.get("1.0", tk.END).strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files
        self.save_scripts()
        
        self.update_status("Generating everything...")
        self.progress_bar['value'] = 0
        
        try:
            # Add the LaTeX file path to the configuration
            self.config['latex_file_path'] = os.path.abspath(latex_file)
            
            # 1. Generate slide images
            self.update_status("Step 1: Generating slide images...")
            self.update_progress(0, 100)
            self.root.update()
            
            image_paths = generate_slide_images(latex_file, self.config)
            
            if not image_paths:
                messagebox.showerror("Error", "Failed to generate slide images.")
                self.update_status("Failed to generate slide images.")
                return
            
            self.update_status(f"Generated {len(image_paths)} slide images.")
            self.update_progress(33, 100)
            self.root.update()
            
            # 2. Generate audio files
            self.update_status("Step 2: Generating audio files...")
            audio_paths = generate_all_audio(self.narrations, self.config)
            
            if not audio_paths:
                messagebox.showerror("Error", "Failed to generate audio files.")
                self.update_status("Failed to generate audio files.")
                return
            
            self.update_status(f"Generated {len(audio_paths)} audio files.")
            self.update_progress(66, 100)
            self.root.update()
            
            # 3. Assemble video
            self.update_status("Step 3: Assembling final video...")
            
            # Check if the number of images matches the number of audio files
            if len(image_paths) != len(audio_paths):
                messagebox.showwarning("Warning", 
                    f"Mismatch between number of images ({len(image_paths)}) and audio files ({len(audio_paths)}). Using the minimum number.")
                # Use the minimum number of files
                count = min(len(image_paths), len(audio_paths))
                image_paths = image_paths[:count]
                audio_paths = audio_paths[:count]
            
            output_path = assemble_video(image_paths, audio_paths, self.config)
            
            if not output_path:
                messagebox.showerror("Error", "Failed to assemble video.")
                self.update_status("Failed to assemble video.")
                return
            
            self.update_progress(100, 100)
            self.update_status(f"Video generation complete: {output_path}")
            messagebox.showinfo("Success", f"Video generation complete!\nVideo saved to: {output_path}")
            
        except Exception as e:
            logging.error(f"Error in generate all process: {e}")
            messagebox.showerror("Error", f"Failed to complete video generation: {e}")
            self.update_status("Error in video generation process.")

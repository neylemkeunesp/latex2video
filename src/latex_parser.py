import re
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Slide:
    """Represents a single slide with its content."""
    def __init__(self, frame_number: int, title: str, content: str):
        self.frame_number = frame_number
        self.title = title
        self.content = content

    def __repr__(self):
        return f"Slide(frame_number={self.frame_number}, title='{self.title}', content_len={len(self.content)})"

def extract_frame_title(frame_content: str) -> str:
    """Extracts the frametitle from the frame content."""
    match = re.search(r'\\frametitle\{(.*?)\}', frame_content, re.DOTALL)
    return match.group(1).strip() if match else "Untitled Frame"

def clean_latex_content(content: str) -> str:
    """Removes common LaTeX commands for cleaner text extraction."""
    # Remove comments
    content = re.sub(r'%.*?\n', '\n', content)
    # Remove \frametitle command itself
    content = re.sub(r'\\frametitle\{.*?\}', '', content, flags=re.DOTALL)
    # Remove itemize/enumerate environments but keep content
    content = re.sub(r'\\begin\{(itemize|enumerate|description)\}', '', content)
    content = re.sub(r'\\end\{(itemize|enumerate|description)\}', '', content)
    # Remove \item tags
    content = re.sub(r'\\item\s*', '- ', content)
    # Remove \begin{align*} \end{align*} but keep content (for now)
    content = re.sub(r'\\begin\{align\*?\}', '', content)
    content = re.sub(r'\\end\{align\*?\}', '', content)
    # Remove leading/trailing whitespace from lines and the whole block
    lines = [line.strip() for line in content.strip().split('\n')]
    return '\n'.join(filter(None, lines)) # Remove empty lines

def parse_latex_file(file_path: str) -> List[Slide]:
    """Parses a LaTeX Beamer file and extracts slides."""
    logging.info(f"Parsing LaTeX file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            latex_content = f.read()
    except FileNotFoundError:
        logging.error(f"LaTeX file not found: {file_path}")
        return []
    except Exception as e:
        logging.error(f"Error reading LaTeX file {file_path}: {e}")
        return []

    # Find all frames using a non-greedy match
    # Exclude the title page frame if it's empty or just contains \titlepage
    frames = re.findall(r'\\begin\{frame\}(.*?)\\end\{frame\}', latex_content, re.DOTALL)
    
    slides: List[Slide] = []
    frame_counter = 0
    for i, frame_content in enumerate(frames):
        # Skip the typical title page frame
        if '\\titlepage' in frame_content and len(frame_content.strip()) < 20:
             logging.info(f"Skipping potential title page frame {i+1}")
             continue
             
        frame_counter += 1
        title = extract_frame_title(frame_content)
        cleaned_content = clean_latex_content(frame_content)
        
        if not cleaned_content.strip():
             logging.warning(f"Frame {frame_counter} appears empty after cleaning. Title: '{title}'")
             # Optionally skip empty frames or handle them differently
             # continue 

        slide = Slide(frame_number=frame_counter, title=title, content=cleaned_content)
        slides.append(slide)
        logging.debug(f"Parsed slide {frame_counter}: Title='{title}'")

    logging.info(f"Successfully parsed {len(slides)} slides (excluding title page).")
    return slides

if __name__ == '__main__':
    # Example usage:
    sample_file = '../assets/presentation.tex' # Adjust path if running directly
    parsed_slides = parse_latex_file(sample_file)
    for slide in parsed_slides:
        print(f"--- Slide {slide.frame_number}: {slide.title} ---")
        print(slide.content)
        print("-" * (len(slide.title) + 14))

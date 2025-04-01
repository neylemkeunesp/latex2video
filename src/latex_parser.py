import re
import os
import logging
import subprocess
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
    frames = re.findall(r'\\begin\{frame\}(.*?)\\end\{frame\}', latex_content, re.DOTALL)
    
    # Extract document title and author for use in slides
    title_match = re.search(r'\\title\{(.*?)\}', latex_content, re.DOTALL)
    doc_title = title_match.group(1).strip() if title_match else "Presentation Title"
    author_match = re.search(r'\\author\{(.*?)\}', latex_content, re.DOTALL)
    doc_author = author_match.group(1).strip() if author_match else ""
    
    # Get the number of pages in the PDF
    pdf_path = os.path.join('output', 'temp_pdf', os.path.splitext(os.path.basename(file_path))[0] + '.pdf')
    pdf_page_count = 14  # Default to 14 pages if we can't determine the actual count
    
    try:
        if os.path.exists(pdf_path):
            result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, check=True)
            match = re.search(r'Pages:\s+(\d+)', result.stdout)
            if match:
                pdf_page_count = int(match.group(1))
                logging.info(f"PDF has {pdf_page_count} pages")
    except Exception as e:
        logging.warning(f"Could not determine PDF page count: {e}")
    
    # Create slides to match the PDF page count
    parsed_slides: List[Slide] = []
    
    # First slide is always the title page
    parsed_slides.append(Slide(
        frame_number=1,
        title="Title Page",
        content=f"Title: {doc_title}\nAuthor: {doc_author}"
    ))
    
    # Second slide is the outline/TOC
    parsed_slides.append(Slide(
        frame_number=2,
        title="Outline",
        content="This slide shows the outline of the presentation."
    ))
    
    # Process the actual content frames
    frame_titles = []
    for i, frame_content in enumerate(frames):
        # Skip the title page frame
        if '\\titlepage' in frame_content:
            continue
            
        title = extract_frame_title(frame_content)
        frame_titles.append(title)
        cleaned_content = clean_latex_content(frame_content)
        
        if not cleaned_content.strip():
            logging.warning(f"Frame appears empty after cleaning. Title: '{title}'")
            cleaned_content = f"This slide covers {title}."
    
    # Distribute the content frames across the remaining PDF pages
    content_frames = len(frame_titles)
    remaining_pages = pdf_page_count - 2  # Subtract title and outline pages
    
    if content_frames == 0:
        logging.warning("No content frames found in LaTeX file")
        return parsed_slides
    
    # Calculate how many PDF pages each content frame gets
    pages_per_frame = remaining_pages / content_frames
    
    # Create slides for each PDF page
    frame_index = 0
    for page in range(2, pdf_page_count):
        # Determine which content frame this page belongs to
        frame_position = (page - 2) / pages_per_frame
        current_frame_index = min(int(frame_position), content_frames - 1)
        
        if current_frame_index != frame_index:
            frame_index = current_frame_index
        
        # Get the title and content for this frame
        title = frame_titles[frame_index]
        
        # Get the frame content for this slide
        frame_content = frames[frame_index + (1 if '\\titlepage' in frames[0] else 0)]
        content = clean_latex_content(frame_content)
        
        # If the content is empty, use a placeholder
        if not content.strip():
            content = f"This slide covers {title}."
        
        # For continuation pages, add a note that this is a continuation
        if not frame_position.is_integer():
            # This is a continuation page for the current frame
            # Add a note at the beginning but keep the full content
            content = f"Continuation of {title}.\n\n{content}"
        
        parsed_slides.append(Slide(
            frame_number=page + 1,  # +1 because frame_number is 1-indexed
            title=title,
            content=content
        ))
    
    logging.info(f"Successfully parsed {len(parsed_slides)} slides to match PDF page count of {pdf_page_count}.")
    return parsed_slides

if __name__ == '__main__':
    # Example usage:
    sample_file = '../assets/presentation.tex' # Adjust path if running directly
    parsed_slides = parse_latex_file(sample_file)
    for slide in parsed_slides:
        print(f"--- Slide {slide.frame_number}: {slide.title} ---")
        print(slide.content)
        print("-" * (len(slide.title) + 14))

import re
import os
import logging
import subprocess
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """Extract text from PDF using pdftotext."""
    try:
        logging.info(f"Extracting text from PDF: {pdf_path}")
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error extracting text from PDF: {e}")
        return None

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
    # Try to match frametitle with balanced braces
    # This is a more robust approach that handles nested braces
    frame_title = "Untitled Frame"
    
    # First, look for \frametitle{ pattern
    title_start = frame_content.find("\\frametitle{")
    if title_start >= 0:
        # Found the start of the title
        title_start += len("\\frametitle{")
        brace_count = 1  # We've already seen one opening brace
        title_end = title_start
        
        # Find the matching closing brace
        while title_end < len(frame_content) and brace_count > 0:
            if frame_content[title_end] == '{':
                brace_count += 1
            elif frame_content[title_end] == '}':
                brace_count -= 1
            title_end += 1
        
        if brace_count == 0:  # Found the matching closing brace
            # Extract the title (excluding the closing brace)
            frame_title = frame_content[title_start:title_end-1].strip()
    
    # If the above method fails, try the simple regex approach as a fallback
    if frame_title == "Untitled Frame":
        match = re.search(r'\\frametitle\{(.*?)\}', frame_content, re.DOTALL)
        if match:
            frame_title = match.group(1).strip()
    
    # If still no title found, try to extract the first non-empty line as the title
    if frame_title == "Untitled Frame":
        # Clean the content first to remove LaTeX commands
        cleaned_content = clean_latex_content(frame_content)
        lines = cleaned_content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('-') and not line.startswith('Continuation of'):
                # Found a potential title
                frame_title = line
                break
    
    return frame_title

# Move the clean_latex_content function above extract_frame_title since we now use it there
def clean_latex_content(content: str) -> str:
    """Removes common LaTeX commands for cleaner text extraction."""
    # Make a copy of the original content
    original_content = content
    
    # Remove comments
    content = re.sub(r'%.*?\n', '\n', content)
      
    # Handle frametitle with balanced braces
    title_start = content.find("\\frametitle{")
    while title_start >= 0:
        # Found the start of the title
        brace_count = 1  # We've already seen one opening brace
        title_end = title_start + len("\\frametitle{")
        
        # Find the matching closing brace
        while title_end < len(content) and brace_count > 0:
            if content[title_end] == '{':
                brace_count += 1
            elif content[title_end] == '}':
                brace_count -= 1
            title_end += 1
        
        if brace_count == 0:  # Found the matching closing brace
            # Remove the frametitle command
            content = content[:title_start] + content[title_end:]
        else:
            # If we couldn't find the matching brace, just remove what we can
            content = content[:title_start] + content[title_start + len("\\frametitle{"):]
        
        # Look for the next frametitle
        title_start = content.find("\\frametitle{")
    
    # Special handling for itemize/enumerate environments
    # Extract items from itemize/enumerate environments
    itemize_pattern = re.compile(r'\\begin\{(itemize|enumerate|description)\}(.*?)\\end\{\1\}', re.DOTALL)
    itemize_matches = list(itemize_pattern.finditer(content))
    
    for match in itemize_matches:
        env_type = match.group(1)
        items_content = match.group(2)
        
        # Extract individual items
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', items_content, re.DOTALL)
        items = [item.strip() for item in items if item.strip()]
        
        # Format as a list
        formatted_items = '\n'.join([f"- {item}" for item in items])
        
        # Replace the entire environment with the formatted list
        content = content.replace(match.group(0), formatted_items)
    
    # If no itemize environments were found but there are \item commands, handle them directly
    if not itemize_matches and '\\item' in content:
        # Extract individual items
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, re.DOTALL)
        items = [item.strip() for item in items if item.strip()]
        
        if items:
            # Format as a list
            formatted_items = '\n'.join([f"- {item}" for item in items])
            
            # Replace all \item commands with the formatted list
            content = re.sub(r'\\item\s*.*', '', content, flags=re.DOTALL)
            content += '\n' + formatted_items
    
    # Handle math environments with balanced delimiters
    # For math environments like align, eqnarray, etc., we'll keep the content but remove the environment tags
    for env in ['align', 'eqnarray', 'equation', 'gather', 'multline']:
        content = re.sub(r'\\begin\{' + env + r'\*?\}', '', content)
        content = re.sub(r'\\end\{' + env + r'\*?\}', '', content)
    
    # Handle matrix environments - preserve the structure but remove the environment tags
    for env in ['pmatrix', 'bmatrix', 'vmatrix', 'Vmatrix', 'matrix']:
        content = re.sub(r'\\begin\{' + env + r'\}', '', content)
        content = re.sub(r'\\end\{' + env + r'\}', '', content)
    
    # Handle inline math delimiters $...$ and \(...\) with balanced matching
    # We need to handle double dollar signs first to avoid partial matches
    
    # Function to find matching closing delimiter with proper nesting
    def find_matching_delimiter(s, start, open_delim, close_delim):
        """Find the matching closing delimiter with proper nesting."""
        count = 1
        i = start
        while i < len(s) and count > 0:
            if s[i:i+len(open_delim)] == open_delim:
                count += 1
                i += len(open_delim)
            elif s[i:i+len(close_delim)] == close_delim:
                count -= 1
                i += len(close_delim)
            else:
                i += 1
        return i if count == 0 else -1
    
    # Handle double dollar math ($$...$$)
    i = 0
    while i < len(content):
        start = content.find('$$', i)
        if start == -1:
            break
        end = content.find('$$', start + 2)
        if end == -1:
            break
        # Extract the math content
        math_content = content[start+2:end]
        # Keep the math content but remove the delimiters
        content = content[:start] + math_content + content[end+2:]
        i = start + len(math_content)
    
    # Handle single dollar math ($...$)
    i = 0
    while i < len(content):
        start = content.find('$', i)
        if start == -1 or (start > 0 and content[start-1] == '$'):  # Skip if it's part of $$
            i = start + 1 if start != -1 else len(content)
            continue
        end = content.find('$', start + 1)
        if end == -1:
            break
        # Extract the math content
        math_content = content[start+1:end]
        # Keep the math content but remove the delimiters
        content = content[:start] + math_content + content[end+1:]
        i = start + len(math_content)
    
    # Handle \(...\) math
    i = 0
    while i < len(content):
        start = content.find('\\(', i)
        if start == -1:
            break
        end = content.find('\\)', start + 2)
        if end == -1:
            break
        # Extract the math content
        math_content = content[start+2:end]
        # Keep the math content but remove the delimiters
        content = content[:start] + math_content + content[end+2:]
        i = start + len(math_content)
    
    # Handle \[...\] math
    i = 0
    while i < len(content):
        start = content.find('\\[', i)
        if start == -1:
            break
        end = content.find('\\]', start + 2)
        if end == -1:
            break
        # Extract the math content
        math_content = content[start+2:end]
        # Keep the math content but remove the delimiters
        content = content[:start] + math_content + content[end+2:]
        i = start + len(math_content)
    
    # Preserve essential math commands
    math_commands = [
        'frac', 'sqrt', 'int', 'sum', 'prod', 'lim', 'infty', 'partial',
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
        'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'pi', 'rho', 'sigma',
        'tau', 'upsilon', 'phi', 'chi', 'psi', 'omega'
    ]
    
    # Create a pattern that matches any LaTeX command except the essential math commands
    non_math_command_pattern = r'\\(?!(?:' + '|'.join(math_commands) + r')\b)[a-zA-Z]+(\{.*?\}|\[.*?\])*'
    
    # Extract image paths and include them in the content
    def replace_image(match):
        # Extract the image path from the includegraphics command
        img_match = re.search(r'\\includegraphics(?:\[.*?\])?\{(.*?)\}', match.group(0))
        if img_match:
            img_path = img_match.group(1)
            return f"[Image: {img_path}]"
        return "[Image]"
    
    # Replace includegraphics commands with image information
    content = re.sub(r'\\includegraphics(?:\[.*?\])?\{.*?\}', replace_image, content, flags=re.DOTALL)
    content = re.sub(r'\\textbf\{(.*?)\}', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'\\textit\{(.*?)\}', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'\\emph\{(.*?)\}', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'\\underline\{(.*?)\}', r'\1', content, flags=re.DOTALL)
    
    # Remove other LaTeX commands that might remain, except essential math commands
    content = re.sub(non_math_command_pattern, '', content, flags=re.DOTALL)
    
    # Remove leading/trailing whitespace from lines and the whole block
    lines = [line.strip() for line in content.strip().split('\n')]
    
    # Remove empty lines
    cleaned_content = '\n'.join(filter(None, lines))
    
    # If the cleaned content is empty, try a more aggressive approach
    if not cleaned_content.strip():
        # Try to extract any text content from the original
        text_content = re.sub(r'\\[a-zA-Z]+(\{.*?\}|\[.*?\])*', '', original_content, flags=re.DOTALL)
        text_content = re.sub(r'[{}\\]', '', text_content)
        
        # Remove leading/trailing whitespace from lines and the whole block
        lines = [line.strip() for line in text_content.strip().split('\n')]
        
        # Remove empty lines
        cleaned_content = '\n'.join(filter(None, lines))
    
    return cleaned_content



def parse_pdf_file(pdf_path: str) -> List[Slide]:
    """Parses a PDF file and extracts slides."""
    logging.info(f"Parsing PDF file: {pdf_path}")
    
    # Extract text from PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    if not pdf_text:
        logging.error(f"Failed to extract text from PDF: {pdf_path}")
        return []
    
    # Get the number of pages in the PDF
    pdf_page_count = 0
    try:
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, check=True)
        match = re.search(r'Pages:\s+(\d+)', result.stdout)
        if match:
            pdf_page_count = int(match.group(1))
            logging.info(f"PDF has {pdf_page_count} pages")
    except Exception as e:
        logging.error(f"Error getting page count from PDF: {e}")
        return []
    
    # Split text by page (pdftotext adds form feeds between pages)
    pages = pdf_text.split('\f')
    
    # Create slides from pages
    slides = []
    
    # First slide is usually the title page
    if len(pages) > 0:
        title_page_text = pages[0].strip()
        title_lines = [line for line in title_page_text.split('\n') if line.strip()]
        
        # Try to extract title and author from the first page
        title = title_lines[0] if title_lines else "Presentation Title"
        author = title_lines[1] if len(title_lines) > 1 else ""
        
        slides.append(Slide(
            frame_number=1,
            title="Title Page",
            content=f"Title: {title}\nAuthor: {author}"
        ))
    
    # Second slide is usually the outline/TOC
    if len(pages) > 1:
        outline_text = pages[1].strip()
        
        # Check if this page looks like an outline
        is_outline = False
        outline_keywords = ["outline", "contents", "agenda", "sumário", "índice", "conteúdo"]
        for keyword in outline_keywords:
            if keyword.lower() in outline_text.lower():
                is_outline = True
                break
        
        if is_outline:
            slides.append(Slide(
                frame_number=2,
                title="Outline",
                content=outline_text
            ))
            start_idx = 2  # Start content slides from page 3
        else:
            # If second page doesn't look like an outline, add a default outline slide
            slides.append(Slide(
                frame_number=2,
                title="Outline",
                content="This slide shows the outline of the presentation."
            ))
            start_idx = 1  # Start content slides from page 2
    else:
        # If there's only one page, add a default outline slide
        slides.append(Slide(
            frame_number=2,
            title="Outline",
            content="This slide shows the outline of the presentation."
        ))
        start_idx = 1  # Start content slides from page 2 (though there aren't any more pages)
    
    # Process the remaining pages as content slides
    for i in range(start_idx, len(pages)):
        page_text = pages[i].strip()
        if not page_text:
            continue
        
        # Try to extract a title from the page
        lines = page_text.split('\n')
        title = "Untitled Slide"
        content = page_text
        
        # Try to find a title in the first few lines
        for j in range(min(3, len(lines))):
            if lines[j].strip() and not lines[j].strip().startswith('-'):
                title = lines[j].strip()
                # Remove the title from the content
                content = '\n'.join(lines[j+1:])
                break
        
        # Add the slide
        slides.append(Slide(
            frame_number=i+1,
            title=title,
            content=content
        ))
        
        # Log the extracted content for debugging
        logging.info(f"Slide {i+1}: {title}")
        logging.info(f"Extracted Content:\n{content}")
        logging.info("-" * 80)
    
    logging.info(f"Successfully parsed {len(slides)} slides from PDF.")
    return slides

def parse_latex_file(file_path: str) -> List[Slide]:
    """Parses a LaTeX Beamer file or PDF file and extracts slides."""
    # Check if the file is a PDF
    if file_path.lower().endswith('.pdf'):
        logging.info(f"Detected PDF file: {file_path}")
        return parse_pdf_file(file_path)
    
    # Otherwise, treat it as a LaTeX file
    logging.info(f"Parsing LaTeX file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            latex_content = f.read()
    except FileNotFoundError:
        logging.error(f"LaTeX file not found: {file_path}")
        # Check if there's a PDF with the same base name
        pdf_path = os.path.splitext(file_path)[0] + '.pdf'
        if os.path.exists(pdf_path):
            logging.info(f"Found PDF file with same base name: {pdf_path}")
            return parse_pdf_file(pdf_path)
        return []
    except Exception as e:
        logging.error(f"Error reading LaTeX file {file_path}: {e}")
        return []

    # Find all frames using a non-greedy match
    # Try different patterns for frame detection
    frames = []
    
    # Pattern 1: Standard \begin{frame}...\end{frame}
    frames_pattern1 = re.findall(r'\\begin\{frame\}(.*?)\\end\{frame\}', latex_content, re.DOTALL)
    if frames_pattern1:
        logging.info(f"Found {len(frames_pattern1)} frames using standard pattern")
        frames.extend(frames_pattern1)
    
    # Pattern 2: \begin{frame}[options]...\end{frame}
    frames_pattern2 = re.findall(r'\\begin\{frame\}\[(.*?)\](.*?)\\end\{frame\}', latex_content, re.DOTALL)
    if frames_pattern2:
        logging.info(f"Found {len(frames_pattern2)} frames with options")
        frames.extend([content for _, content in frames_pattern2])
    
    # Pattern 3: \frame{...} (older LaTeX syntax)
    # Make sure we're not matching \frametitle{...}
    #frames_pattern3 = re.findall(r'(?<!title)\\frame\{(.*?)\}', latex_content, re.DOTALL)
    frames_pattern3 = re.findall(r'(?<!title)\\frame\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', latex_content, re.DOTALL)

    if frames_pattern3:
        logging.info(f"Found {len(frames_pattern3)} frames using \\frame{{...}} syntax")
        frames.extend(frames_pattern3)
    # Pattern 4: \begin{frame}{title}...\end{frame}
    frames_pattern4 = re.findall(r'\\begin\{frame\}\{(.*?)\}(.*?)\\end\{frame\}', latex_content, re.DOTALL)
    if frames_pattern4:
        logging.info(f"Found {len(frames_pattern4)} frames with inline titles")
        frames.extend([content for _, content in frames_pattern4])
    
    logging.info(f"Total frames found: {len(frames)}")
    
    # If no frames were found, try a more aggressive approach
    if not frames:
        logging.warning("No frames found with standard patterns. Trying more aggressive pattern matching...")
        
        # Split the content by \begin{frame} and \end{frame}
        frame_starts = [m.start() for m in re.finditer(r'\\begin\{frame\}', latex_content)]
        frame_ends = [m.start() for m in re.finditer(r'\\end\{frame\}', latex_content)]
        
        if len(frame_starts) > 0 and len(frame_ends) > 0:
            logging.info(f"Found {len(frame_starts)} frame starts and {len(frame_ends)} frame ends")
            
            # Match starts and ends
            for i in range(min(len(frame_starts), len(frame_ends))):
                if frame_starts[i] < frame_ends[i]:
                    frame_content = latex_content[frame_starts[i] + len('\\begin{frame}'):frame_ends[i]]
                    frames.append(frame_content)
            logging.info(f"Extracted {len(frames)} frames using position-based matching")
    
    # If still no frames, try to estimate based on the PDF page count
    if not frames and pdf_page_count > 2:  # If we have more than title and TOC
        logging.warning("No frames found with any pattern. Creating dummy frames based on PDF page count...")
        
        # Create dummy frames for each page beyond title and TOC
        for i in range(pdf_page_count - 2):
            frames.append(f"\\frametitle{{Slide {i+3}}}\nContent for slide {i+3}")
        
        logging.info(f"Created {len(frames)} dummy frames based on PDF page count")
    
    # Extract document title and author for use in slides
    title_match = re.search(r'\\title\{(.*?)\}', latex_content, re.DOTALL)
    doc_title = title_match.group(1).strip() if title_match else "Presentation Title"
    author_match = re.search(r'\\author\{(.*?)\}', latex_content, re.DOTALL)
    doc_author = author_match.group(1).strip() if author_match else ""
    
    # Get the number of pages in the PDF
    # First check in the source directory
    source_dir = os.path.dirname(os.path.abspath(file_path))
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    pdf_path_source = os.path.join(source_dir, base_name + '.pdf')
    
    # Also check in the output directory
    pdf_path_output = os.path.join('output', 'temp_pdf', base_name + '.pdf')
    
    pdf_page_count = 0  # Initialize to 0
    
    # Try to get page count from source directory first
    try:
        if os.path.exists(pdf_path_source):
            logging.info(f"Found PDF in source directory: {pdf_path_source}")
            result = subprocess.run(['pdfinfo', pdf_path_source], capture_output=True, text=True, check=True)
            match = re.search(r'Pages:\s+(\d+)', result.stdout)
            if match:
                pdf_page_count = int(match.group(1))
                logging.info(f"PDF in source directory has {pdf_page_count} pages")
        # If not found in source directory or couldn't get page count, try output directory
        elif os.path.exists(pdf_path_output):
            logging.info(f"Found PDF in output directory: {pdf_path_output}")
            result = subprocess.run(['pdfinfo', pdf_path_output], capture_output=True, text=True, check=True)
            match = re.search(r'Pages:\s+(\d+)', result.stdout)
            if match:
                pdf_page_count = int(match.group(1))
                logging.info(f"PDF in output directory has {pdf_page_count} pages")
        else:
            logging.warning(f"PDF not found in either source directory ({pdf_path_source}) or output directory ({pdf_path_output})")
    except Exception as e:
        logging.warning(f"Could not determine PDF page count: {e}")
    
    # If we still don't have a page count, try to estimate from the number of frames
    if pdf_page_count == 0:
        # Count the number of frames in the LaTeX file
        frame_count = len(frames)
        
        # Add 2 for title and outline slides
        estimated_page_count = frame_count + 2
        
        logging.warning(f"Could not determine PDF page count from file. Estimating {estimated_page_count} pages based on {frame_count} frames plus title and outline slides.")
        pdf_page_count = estimated_page_count
    
    # Create slides to match the PDF page count
    parsed_slides: List[Slide] = []
    
    # First slide is always the title page
    parsed_slides.append(Slide(
        frame_number=1,
        title="Title Page",
        content=f"Title: {doc_title}\nAuthor: {doc_author}"
    ))
    # Find the outline slide if it exists
    outline_slide_index = -1
    for i, frame_content in enumerate(frames):
        # Check if this frame is an outline/TOC slide
        if '\\tableofcontents' in frame_content or 'Outline' in frame_content or 'Sumário' in frame_content:
            outline_slide_index = i
            break
    
    # Add a default outline slide if we didn't find one
    if outline_slide_index == -1:
        parsed_slides.append(Slide(
            frame_number=2,
            title="Outline",
            content="This slide shows the outline of the presentation."
        ))
    else:
        # Extract the outline slide content
        outline_content = clean_latex_content(frames[outline_slide_index])
        if not outline_content.strip():
            outline_content = "This slide shows the outline of the presentation."
        
        # Add the outline slide as slide 2
        parsed_slides.append(Slide(
            frame_number=2,
            title="Outline",
            content=outline_content
        ))
        
        # Remove the outline slide from frames so we don't process it again
        frames.pop(outline_slide_index)
    
    # Process the actual content frames and create slides
    start_frame_number = 3  # Start content slides at frame 3 (after title and outline)
    for i, frame_content in enumerate(frames):
        # Skip the title page frame
        if '\\titlepage' in frame_content:
            continue
        
        # Calculate the frame number
        frame_number = i + start_frame_number
        if frame_number > pdf_page_count:
            break  # Don't create more slides than PDF pages
            
        # Extract title and content
        title = extract_frame_title(frame_content)
        cleaned_content = clean_latex_content(frame_content)
        
        # Ensure we have content
        if not cleaned_content.strip():
            logging.warning(f"Frame appears empty after cleaning. Title: '{title}'")
            cleaned_content = f"This slide covers {title}."
        
        # Log the extracted content for debugging
        logging.info(f"Slide {frame_number}: {title}")
        logging.info(f"Extracted Content:\n{cleaned_content}")
        logging.info("-" * 80)
        
        # Add the slide to our collection
        parsed_slides.append(Slide(
            frame_number=frame_number,
            title=title,
            content=cleaned_content
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

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

def clean_latex_content(content: str) -> str:
    """Removes comments and frametitle from LaTeX content."""
    # Remove comments
    content = re.sub(r'%.*?\n', '\n', content)

    # Remove frametitle command and its argument
    content = re.sub(r'\\frametitle\{.*?\}', '', content, flags=re.DOTALL)

    return content


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
    """Parses a LaTeX Beamer file or PDF file and extracts slides, including \section as slides."""
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

    # --- NEW: Find all \section and frame occurrences with their positions ---
    # Pattern for \section{...}
    section_pattern = re.compile(r'\\section\{(.*?)\}', re.DOTALL)
    # Patterns for frames
    frame_patterns = [
        re.compile(r'\\begin\{frame\}(.*?)\\end\{frame\}', re.DOTALL),
        re.compile(r'\\begin\{frame\}\[(.*?)\](.*?)\\end\{frame\}', re.DOTALL),
        re.compile(r'(?<!title)\\frame\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL),
        re.compile(r'\\begin\{frame\}\{(.*?)\}(.*?)\\end\{frame\}', re.DOTALL),
    ]

    # Find all \section occurrences
    section_matches = [(m.start(), m.end(), m.group(1).strip()) for m in section_pattern.finditer(latex_content)]

    # Find all frame occurrences (with their positions and content)
    frame_matches = []
    for pat in frame_patterns:
        for m in pat.finditer(latex_content):
            # For patterns with two groups (title, content), use content
            if len(m.groups()) == 2:
                frame_matches.append((m.start(), m.end(), m.group(2)))
            else:
                frame_matches.append((m.start(), m.end(), m.group(1)))

    # Merge all slide-like elements (sections and frames) by their position in the file
    all_slide_matches = []
    for start, end, title in section_matches:
        all_slide_matches.append({'type': 'section', 'start': start, 'end': end, 'title': title, 'content': title})
    for start, end, content in frame_matches:
        all_slide_matches.append({'type': 'frame', 'start': start, 'end': end, 'content': content})

    # Sort by position in the file
    all_slide_matches.sort(key=lambda x: x['start'])

    # Extract document title and author for use in slides
    title_match = re.search(r'\\title\{(.*?)\}', latex_content, re.DOTALL)
    doc_title = title_match.group(1).strip() if title_match else "Presentation Title"
    author_match = re.search(r'\\author\{(.*?)\}', latex_content, re.DOTALL)
    doc_author = author_match.group(1).strip() if author_match else ""

    # Get the number of pages in the PDF
    source_dir = os.path.dirname(os.path.abspath(file_path))
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    pdf_path_source = os.path.join(source_dir, base_name + '.pdf')
    pdf_path_output = os.path.join('output', 'temp_pdf', base_name + '.pdf')
    pdf_page_count = 0  # Initialize to 0

    try:
        if os.path.exists(pdf_path_source):
            logging.info(f"Found PDF in source directory: {pdf_path_source}")
            result = subprocess.run(['pdfinfo', pdf_path_source], capture_output=True, text=True, check=True)
            match = re.search(r'Pages:\s+(\d+)', result.stdout)
            if match:
                pdf_page_count = int(match.group(1))
                logging.info(f"PDF in source directory has {pdf_page_count} pages")
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

    # If we still don't have a page count, estimate from number of slides
    if pdf_page_count == 0:
        estimated_page_count = len(all_slide_matches) + 2
        logging.warning(f"Could not determine PDF page count from file. Estimating {estimated_page_count} pages based on {len(all_slide_matches)} slides plus title and outline.")
        pdf_page_count = estimated_page_count

    # --- Build slides ---
    parsed_slides: List[Slide] = []

    # Title page
    parsed_slides.append(Slide(
        frame_number=1,
        title="Title Page",
        content=f"Title: {doc_title}\nAuthor: {doc_author}"
    ))

    # Outline slide
    parsed_slides.append(Slide(
        frame_number=2,
        title="Outline",
        content="This slide shows the outline of the presentation."
    ))

    # Content slides (section and frame slides, in order)
    frame_number = 3
    last_title = None
    for slide_match in all_slide_matches:
        if frame_number > pdf_page_count:
            break
        if slide_match['type'] == 'section':
            section_title = slide_match['title'].strip()
            # Não adicionar se for igual a Title Page, Outline ou ao título do documento
            if section_title.lower() in ["title page", "outline"]:
                continue
            if doc_title and section_title.strip().lower() == doc_title.strip().lower():
                continue
            # Não adicionar se for igual ao último título adicionado
            if last_title is not None and section_title == last_title:
                continue
            parsed_slides.append(Slide(
                frame_number=frame_number,
                title=section_title,
                content=section_title
            ))
            last_title = section_title
        else:
            # Frame slide: extract title and content as antes
            title = extract_frame_title(slide_match['content'])
            cleaned_content = clean_latex_content(slide_match['content'])
            # Não adicionar se o título for igual ao último título adicionado
            if last_title is not None and title == last_title:
                continue
            # Não adicionar se o título for igual ao título do documento ou "Title Page"
            if title.strip().lower() == "title page":
                continue
            if doc_title and title.strip().lower() == doc_title.strip().lower():
                continue
            if not cleaned_content.strip():
                logging.warning(f"Frame appears empty after cleaning. Title: '{title}'")
                cleaned_content = f"This slide covers {title}."
            parsed_slides.append(Slide(
                frame_number=frame_number,
                title=title,
                content=cleaned_content
            ))
            last_title = title
        frame_number += 1

    logging.info(f"Successfully parsed {len(parsed_slides)} slides (including sections as slides) to match PDF page count of {pdf_page_count}.")
    return parsed_slides

if __name__ == '__main__':
    # Example usage:
    sample_file = '../assets/presentation.tex' # Adjust path if running directly
    parsed_slides = parse_latex_file(sample_file)
    for slide in parsed_slides:
        print(f"--- Slide {slide.frame_number}: {slide.title} ---")
        print(slide.content)
        print("-" * (len(slide.title) + 14))

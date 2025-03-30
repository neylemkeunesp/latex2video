import os
import sys
import logging
from typing import List, Dict
import re

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.latex_parser import parse_latex_file, Slide

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def format_slide_for_chatgpt(slide: Slide) -> str:
    """
    Format a slide's content for sending to ChatGPT-4o.
    Includes special handling for mathematical formulas.
    """
    # Start with the slide title
    formatted_content = f"# {slide.title}\n\n"
    
    # Process the content
    content = slide.content
    
    # Handle special case for slide 3 (A Técnica dos Multiplicadores de Lagrange)
    if slide.title == "A Técnica dos Multiplicadores de Lagrange" and "\\frac{\\partial L}{\\partial x}" in content:
        # This is a manual fix for the specific align environment in slide 3
        content = content.replace(
            "\\frac{\\partial L}{\\partial x} &= 0 \\\\\n\\frac{\\partial L}{\\partial y} &= 0 \\\\\n\\frac{\\partial L}{\\partial \\lambda} &= 0",
            "SISTEMA DE EQUAÇÕES:\nFORMULA: \\frac{\\partial L}{\\partial x} = 0\nFORMULA: \\frac{\\partial L}{\\partial y} = 0\nFORMULA: \\frac{\\partial L}{\\partial \\lambda} = 0"
        )
    
    # Identify and mark mathematical formulas
    # Look for LaTeX math delimiters and environments
    math_patterns = [
        (r'\$\$(.*?)\$\$', r'FORMULA: \1'),  # Display math
        (r'\$(.*?)\$', r'FORMULA: \1'),      # Inline math
        (r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', r'FORMULA: \1'),  # Equation environment
    ]
    
    for pattern, replacement in math_patterns:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # General handling for align environments (for other slides)
    align_pattern = re.compile(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', re.DOTALL)
    align_matches = list(align_pattern.finditer(content))
    
    for match in align_matches:
        align_content = match.group(1)
        # Split by newline or \\ to get individual equations
        equations = re.split(r'\\\\|\n', align_content)
        equations = [eq.strip() for eq in equations if eq.strip()]
        
        # Format each equation
        formatted_equations = []
        for eq in equations:
            # Remove alignment markers
            eq = re.sub(r'&', '', eq)
            formatted_equations.append(f"FORMULA: {eq}")
        
        # Join with newlines
        replacement = "SISTEMA DE EQUAÇÕES:\n" + "\n".join(formatted_equations)
        
        # Replace in content
        content = content.replace(match.group(0), replacement)
    
    # Add the processed content
    formatted_content += content
    
    # Add instructions for ChatGPT-4o
    formatted_content += "\n\n---\n\n"
    formatted_content += "Por favor, crie um script de narração para este slide que explique o conteúdo de forma clara e concisa. "
    formatted_content += "Dê atenção especial às fórmulas matemáticas, explicando-as de maneira simples e compreensível. "
    formatted_content += "O script deve ser adequado para narração em um vídeo educacional."
    
    return formatted_content

def generate_chatgpt_prompts(latex_file_path: str) -> List[Dict[str, str]]:
    """
    Generate prompts for ChatGPT-4o from a LaTeX presentation file.
    Returns a list of dictionaries with slide number, title, and formatted content.
    """
    logging.info(f"Parsing LaTeX file: {latex_file_path}")
    slides = parse_latex_file(latex_file_path)
    
    if not slides:
        logging.error("Failed to parse slides from LaTeX file.")
        return []
    
    prompts = []
    for slide in slides:
        formatted_content = format_slide_for_chatgpt(slide)
        prompts.append({
            "slide_number": slide.frame_number,
            "title": slide.title,
            "prompt": formatted_content
        })
    
    logging.info(f"Generated {len(prompts)} prompts for ChatGPT-4o")
    return prompts

def save_prompts_to_files(prompts: List[Dict[str, str]], output_dir: str) -> List[str]:
    """
    Save each prompt to a separate text file.
    Returns a list of file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    file_paths = []
    for prompt in prompts:
        file_name = f"slide_{prompt['slide_number']}_prompt.txt"
        file_path = os.path.join(output_dir, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt['prompt'])
        
        file_paths.append(file_path)
        logging.info(f"Saved prompt for slide {prompt['slide_number']} to {file_path}")
    
    return file_paths

def main():
    """Main function to extract slide content and format for ChatGPT-4o."""
    if len(sys.argv) < 2:
        print("Usage: python chatgpt_script_generator.py <path_to_latex_file> [output_directory]")
        sys.exit(1)
    
    latex_file_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/chatgpt_prompts"
    
    prompts = generate_chatgpt_prompts(latex_file_path)
    if not prompts:
        print("No prompts generated. Exiting.")
        sys.exit(1)
    
    file_paths = save_prompts_to_files(prompts, output_dir)
    
    print(f"\nGenerated {len(file_paths)} prompt files in {output_dir}")
    print("\nInstructions:")
    print("1. Open each prompt file")
    print("2. Copy the content and send it to ChatGPT-4o")
    print("3. Save the response as a script for your video narration")

if __name__ == "__main__":
    main()

import re
import logging
from typing import List, Dict
from .latex_parser import Slide  # Assuming latex_parser.py is in the same directory
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Basic mapping for common LaTeX math symbols to spoken Portuguese
MATH_SPEAK_MAP_PT = {
    r'\lambda': 'lambda',
    r'\partial': 'a derivada parcial',
    r'\frac': 'a fração com numerador', # Needs special handling for numerator/denominator
    r'\times': 'vezes',
    r'\cdot': 'vezes',
    r'\leq': 'menor ou igual a',
    r'\geq': 'maior ou igual a',
    r'\neq': 'diferente de',
    r'\approx': 'aproximadamente igual a',
    r'\int': 'a integral',
    r'\sum': 'o somatório',
    r'\lim': 'o limite',
    r'\sin': 'seno',
    r'\cos': 'cosseno',
    r'\tan': 'tangente',
    r'\log': 'logaritmo',
    r'\ln': 'logaritmo natural',
    r'\pi': 'pi',
    r'\alpha': 'alfa',
    r'\beta': 'beta',
    r'\gamma': 'gama',
    # Add more mappings as needed
}

# More complex patterns
COMPLEX_PATTERNS_PT = [
    # Fractions: \frac{num}{den} -> a fração com numerador num e denominador den
    (re.compile(r'\\frac\{(.*?)\}\{(.*?)\}'), r'a fração com numerador \1 e denominador \2'),
    # Subscripts: x_i -> x índice i
    (re.compile(r'([a-zA-Z0-9]+)_\{?([a-zA-Z0-9]+)\}?'), r'\1 índice \2'),
    # Superscripts: x^2 -> x elevado a 2
    (re.compile(r'([a-zA-Z0-9\)]+)\^\{?([a-zA-Z0-9\-\+]+)\}?'), r'\1 elevado a \2'),
    # Function notation: f(x,y) -> f de x, y
    (re.compile(r'([a-zA-Z]+)\((.*?)\)'), r'\1 de \2'),
]

def latex_math_to_speakable_text_pt(math_content: str) -> str:
    """Converts LaTeX math notation to speakable Portuguese text."""
    
    # Remove $...$ or $$...$$ delimiters
    text = re.sub(r'\${1,2}(.*?)\${1,2}', r'\1', math_content).strip()
    
    # Apply complex pattern replacements first
    for pattern, replacement in COMPLEX_PATTERNS_PT:
        text = pattern.sub(replacement, text)

    # Apply simple symbol replacements
    for latex, spoken in MATH_SPEAK_MAP_PT.items():
        # Use word boundaries to avoid partial matches within words
        text = re.sub(r'(?<!\\)' + re.escape(latex) + r'\b', spoken, text) 

    # Handle common structures like align environments
    text = re.sub(r'\\begin\{align\*?\}', 'Temos o seguinte sistema de equações:', text)
    text = re.sub(r'\\end\{align\*?\}', '', text)
    text = re.sub(r'&=', 'é igual a', text) # Alignment point often means equals
    text = re.sub(r'\\\\', '. Próxima equação:', text) # New line in align

    # Replace common symbols
    text = text.replace('=', ' igual a ')
    text = text.replace('+', ' mais ')
    text = text.replace('-', ' menos ')
    text = text.replace('*', ' vezes ')
    text = text.replace('/', ' dividido por ')
    text = text.replace('>', ' maior que ')
    text = text.replace('<', ' menor que ')
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Specific cleanup for function arguments like "x, y" -> "x e y"
    text = re.sub(r'(\b[a-zA-Z]\b)\s*,\s*(\b[a-zA-Z]\b)', r'\1 e \2', text)

    return text

def generate_narration_for_slide(slide: Slide, config: Dict) -> str:
    """Generates the narration script for a single slide."""
    narration_config = config.get('narration', {})
    math_pause_duration = narration_config.get('math_pause', 0.5)
    
    # Start with the title
    narration = f"{slide.title}. " if slide.title != "Untitled Frame" else ""

    # Process content line by line or block by block
    content_lines = slide.content.split('\n')
    processed_lines = []
    
    in_math_block = False
    math_block = ""

    for line in content_lines:
        line = line.strip()
        if not line:
            continue

        # Basic detection of math environments (can be improved)
        is_math_line = '$' in line or '\\[' in line or '\\(' in line or any(cmd in line for cmd in MATH_SPEAK_MAP_PT) or any(p.search(line) for p, _ in COMPLEX_PATTERNS_PT)
        
        if is_math_line:
            # Add a slight pause before math explanation
            processed_lines.append(f"<break time=\"{math_pause_duration}s\"/>") 
            speakable_math = latex_math_to_speakable_text_pt(line)
            processed_lines.append(speakable_math)
            # Add a slight pause after math explanation
            processed_lines.append(f"<break time=\"{math_pause_duration}s\"/>")
        else:
            # Simple text line, maybe add sentence-ending pause if needed
            # For now, just add the line. Add '.' if it doesn't end with punctuation.
            if line[-1] not in ['.', '!', '?']:
                 line += '.'
            processed_lines.append(line)

    narration += " ".join(processed_lines)
    
    # Final cleanup
    narration = re.sub(r'\s+', ' ', narration).strip()
    # Ensure pauses aren't duplicated
    narration = re.sub(r'(<break.*?>)\s*\1', r'\1', narration) 
    # Remove break at the very beginning or end
    narration = re.sub(r'^<break.*?>\s*', '', narration)
    narration = re.sub(r'\s*<break.*?>$', '', narration)

    logging.debug(f"Generated narration for slide {slide.frame_number}: {narration[:100]}...")
    return narration

def generate_all_narrations(slides: List[Slide], config: Dict) -> List[str]:
    """Generates narration scripts for all slides."""
    logging.info(f"Generating narration for {len(slides)} slides...")
    all_narrations = []
    for slide in slides:
        narration = generate_narration_for_slide(slide, config)
        all_narrations.append(narration)
    logging.info("Finished generating all narrations.")
    return all_narrations


if __name__ == '__main__':
    # Example usage:
    from latex_parser import parse_latex_file # Run from parent directory or adjust import

    # Load config first to get narration settings
    try:
        with open('../config/config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        cfg = {}

    sample_latex_file = '../assets/presentation.tex'
    parsed_slides = parse_latex_file(sample_latex_file)
    
    if parsed_slides:
        narrations = generate_all_narrations(parsed_slides, cfg)
        for i, narration in enumerate(narrations):
            print(f"--- Narration for Slide {i+1} ---")
            print(narration)
            print("-" * 30)
    else:
        print("Could not parse slides to generate narrations.")

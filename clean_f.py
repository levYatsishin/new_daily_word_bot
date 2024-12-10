import re

def clean_wordlist(input_file, output_file):
    # Read the input file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove empty quotes
    content = content.replace("", "")
    
    # Remove standalone page numbers (digits followed by newline)
    content = re.sub(r'\n\d+\n', '\n', content)
    
    # Remove single letters marking sections (single uppercase letter on a line)
    content = re.sub(r'\n[A-ZА-Я]\n', '\n', content)
    
    # Join lines not starting with uppercase letter to previous line
    content = re.sub(r'\n(?![А-ЯA-Z])', ' ', content)
    
    # Remove multiple consecutive newlines
    content = re.sub(r'\n\s*\n', '\n', content)
    
    # Remove leading/trailing whitespace
    content = content.strip()
    
    # Write the cleaned content to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

# Usage
input_file = 'wordlists/fenia.txt'
output_file = 'wordlists/fenia_cleaned.txt'
clean_wordlist(input_file, output_file)
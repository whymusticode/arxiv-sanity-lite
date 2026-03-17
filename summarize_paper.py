#!/usr/bin/env python3
"""
Intelligent paper preprocessing for LLM analysis.
Reduces token count while preserving informative content.

Strategy (in order):
1. Strip HTML cruft (nav, scripts, buttons, sidebars)
2. Clean formatting artifacts
3. If still over budget:
   - Remove/compress references section
   - Remove least-referenced appendices
   - Trim acknowledgments, author bios
   - Compress figure/table captions
   - Last resort: trim middle sentences from long paragraphs
"""

import os
import sys
import re
import requests
from bs4 import BeautifulSoup, NavigableString, Comment

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def extract_arxiv_id(url_or_id):
    """Extract arxiv ID from URL or return the ID directly."""
    if url_or_id.startswith('http'):
        parts = url_or_id.split('/')
        arxiv_id = parts[-1]
        arxiv_id = re.sub(r'v\d+$', '', arxiv_id)
        return arxiv_id
    return url_or_id


def get_paper_html(arxiv_id):
    """Fetch the HTML version of the paper from arxiv."""
    url = f"https://arxiv.org/html/{arxiv_id}v1"
    print(f"Fetching paper from: {url}", file=sys.stderr)
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def count_tokens(text, encoding="cl100k_base"):
    """Count tokens using tiktoken if available, else estimate."""
    if TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding(encoding)
        return len(enc.encode(text))
    else:
        return len(text) // 4


def clean_html_cruft(soup):
    """Remove navigation, scripts, styles, buttons, and other cruft."""
    # Remove these tags entirely
    for tag in soup.find_all(['script', 'style', 'nav', 'noscript', 'iframe', 'svg']):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove elements by class patterns (navigation, buttons, etc.)
    cruft_patterns = [
        'ltx_page_logo', 'ltx_page_footer', 'ltx_page_navbar',
        'arxiv-', 'toggle', 'modal', 'sidebar', 'nav-', 'btn',
        'download', 'share', 'social', 'cookie', 'banner',
        'ltx_role_navigation', 'ltx_pagination'
    ]
    for pattern in cruft_patterns:
        for el in soup.find_all(class_=re.compile(pattern, re.I)):
            el.decompose()

    # Remove elements by id patterns
    id_patterns = ['nav', 'sidebar', 'footer', 'header', 'menu', 'modal']
    for pattern in id_patterns:
        for el in soup.find_all(id=re.compile(pattern, re.I)):
            el.decompose()

    # Remove links that are just navigation (Report Issue, Why HTML, etc.)
    for a in soup.find_all('a'):
        text = a.get_text().strip().lower()
        if text in ['report issue', 'why html?', 'back to abstract', 'download pdf',
                    'toggle navigation', 'skip to main content']:
            a.decompose()

    return soup


def extract_text_clean(soup):
    """Extract clean text from soup, preserving structure."""
    # Get text with some structure preservation
    lines = []

    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'figcaption', 'caption']):
        text = element.get_text(separator=' ', strip=True)
        if not text:
            continue

        # Add section markers for headings
        if element.name in ['h1', 'h2']:
            lines.append(f"\n\n=== {text} ===\n")
        elif element.name in ['h3', 'h4']:
            lines.append(f"\n== {text} ==\n")
        else:
            lines.append(text)

    return '\n'.join(lines)


def identify_sections(soup):
    """Identify and tag sections by type."""
    sections = {
        'abstract': [],
        'introduction': [],
        'methods': [],
        'results': [],
        'discussion': [],
        'conclusion': [],
        'references': [],
        'appendix': [],
        'acknowledgments': [],
        'other': []
    }

    section_keywords = {
        'abstract': ['abstract'],
        'introduction': ['introduction', 'intro'],
        'methods': ['method', 'approach', 'methodology', 'model', 'architecture', 'framework'],
        'results': ['result', 'experiment', 'evaluation', 'performance'],
        'discussion': ['discussion', 'analysis'],
        'conclusion': ['conclusion', 'summary', 'future work'],
        'references': ['reference', 'bibliography'],
        'appendix': ['appendix', 'supplementary', 'supplemental'],
        'acknowledgments': ['acknowledgment', 'acknowledgement', 'funding']
    }

    current_section = 'other'

    for element in soup.find_all(['section', 'div', 'h1', 'h2', 'h3']):
        # Check if this element indicates a new section
        text = element.get_text()[:200].lower()
        element_id = (element.get('id') or '').lower()
        element_class = ' '.join(element.get('class') or []).lower()

        for section_type, keywords in section_keywords.items():
            if any(kw in text or kw in element_id or kw in element_class for kw in keywords):
                current_section = section_type
                break

        if element.name in ['section', 'div']:
            section_text = element.get_text(separator=' ', strip=True)
            if section_text:
                sections[current_section].append(section_text)

    return sections


def compress_references(text):
    """Compress references section - keep titles but remove URLs, DOIs, etc."""
    # Pattern to identify reference entries
    lines = text.split('\n')
    compressed = []
    in_references = False

    for line in lines:
        lower = line.lower().strip()

        if 'reference' in lower and len(lower) < 50:
            in_references = True
            compressed.append(line)
            continue

        if in_references:
            # Keep author names and titles, remove URLs, DOIs, page numbers
            line = re.sub(r'https?://\S+', '', line)
            line = re.sub(r'doi:\S+', '', line, flags=re.I)
            line = re.sub(r'arXiv:\S+', '', line, flags=re.I)
            line = re.sub(r'pp?\.\s*\d+[-–]\d+', '', line)
            line = re.sub(r'\d{4}\.\d{4,}', '', line)  # arxiv IDs
            line = re.sub(r'\s+', ' ', line).strip()

            if len(line) > 20:  # Keep if still substantial
                compressed.append(line)
        else:
            compressed.append(line)

    return '\n'.join(compressed)


def trim_paragraphs(text, target_reduction_ratio=0.7):
    """Trim middle sentences from long paragraphs."""
    paragraphs = text.split('\n\n')
    trimmed = []

    for para in paragraphs:
        # Don't trim headings or short paragraphs
        if para.startswith('=') or len(para) < 500:
            trimmed.append(para)
            continue

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', para)

        if len(sentences) <= 3:
            trimmed.append(para)
            continue

        # Keep first sentence, last sentence, and some middle
        n_keep = max(3, int(len(sentences) * target_reduction_ratio))

        # Keep beginning and end, sample from middle
        if n_keep >= len(sentences):
            trimmed.append(para)
        else:
            keep_start = n_keep // 2
            keep_end = n_keep - keep_start
            kept = sentences[:keep_start] + ['[...]'] + sentences[-keep_end:]
            trimmed.append(' '.join(kept))

    return '\n\n'.join(trimmed)


def remove_appendices(soup, keep_first_n=1):
    """Remove appendices except the first N."""
    appendix_count = 0
    for section in soup.find_all(['section', 'div']):
        text = section.get_text()[:100].lower()
        section_id = (section.get('id') or '').lower()
        section_class = ' '.join(section.get('class') or []).lower()

        if 'appendix' in text or 'appendix' in section_id or 'supplementary' in text:
            appendix_count += 1
            if appendix_count > keep_first_n:
                section.decompose()

    return soup


def remove_acknowledgments(soup):
    """Remove acknowledgments/funding sections."""
    for section in soup.find_all(['section', 'div', 'p']):
        text = section.get_text()[:100].lower()
        if any(kw in text for kw in ['acknowledgment', 'acknowledgement', 'this work was supported',
                                      'we thank', 'the authors thank', 'funding']):
            # Check if it's a dedicated section (not just a mention)
            if section.name in ['section', 'div'] or len(section.get_text()) < 500:
                section.decompose()
    return soup


def preprocess_paper(arxiv_id, target_tokens=200000):
    """
    Main preprocessing function. Intelligently reduces paper to target token count.

    Args:
        arxiv_id: arXiv paper ID or URL
        target_tokens: Target maximum token count (default 200k)

    Returns:
        tuple: (processed_text, token_count, output_filepath, stats)
    """
    arxiv_id = extract_arxiv_id(arxiv_id)

    # Fetch paper
    html_content = get_paper_html(arxiv_id)
    original_size = len(html_content)

    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Step 1: Remove HTML cruft
    soup = clean_html_cruft(soup)
    text = extract_text_clean(soup)
    tokens = count_tokens(text)

    stats = {
        'original_html_size': original_size,
        'after_cruft_removal': tokens,
        'steps_applied': ['cruft_removal']
    }

    # Save the clean version (before any reduction) for reference
    clean_text = text
    clean_tokens = tokens
    base_dir = os.path.dirname(os.path.abspath(__file__))
    clean_filename = f"clean_{arxiv_id}.txt"
    clean_filepath = os.path.join(base_dir, clean_filename)

    with open(clean_filepath, 'w') as f:
        f.write(f"Paper: {arxiv_id}\n")
        f.write(f"Token count: {clean_tokens}\n")
        f.write(f"This is the clean version (cruft removed, no reduction)\n")
        f.write("=" * 80 + "\n\n")
        f.write(clean_text)

    stats['clean_filepath'] = clean_filepath

    # Step 2: If still over budget, compress references
    if tokens > target_tokens:
        text = compress_references(text)
        tokens = count_tokens(text)
        stats['after_reference_compression'] = tokens
        stats['steps_applied'].append('reference_compression')

    # Step 3: If still over, remove appendices
    if tokens > target_tokens:
        soup = BeautifulSoup(html_content, 'html.parser')
        soup = clean_html_cruft(soup)
        soup = remove_appendices(soup, keep_first_n=0)
        text = extract_text_clean(soup)
        text = compress_references(text)
        tokens = count_tokens(text)
        stats['after_appendix_removal'] = tokens
        stats['steps_applied'].append('appendix_removal')

    # Step 4: If still over, remove acknowledgments
    if tokens > target_tokens:
        soup = BeautifulSoup(html_content, 'html.parser')
        soup = clean_html_cruft(soup)
        soup = remove_appendices(soup, keep_first_n=0)
        soup = remove_acknowledgments(soup)
        text = extract_text_clean(soup)
        text = compress_references(text)
        tokens = count_tokens(text)
        stats['after_acknowledgment_removal'] = tokens
        stats['steps_applied'].append('acknowledgment_removal')

    # Step 5: Last resort - trim paragraphs
    if tokens > target_tokens:
        # Calculate how much we need to reduce
        ratio = target_tokens / tokens
        text = trim_paragraphs(text, target_reduction_ratio=max(0.5, ratio))
        tokens = count_tokens(text)
        stats['after_paragraph_trimming'] = tokens
        stats['steps_applied'].append('paragraph_trimming')

    # Step 6: Hard truncate if still over (shouldn't happen often)
    if tokens > target_tokens and TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding("cl100k_base")
        token_list = enc.encode(text)
        text = enc.decode(token_list[:target_tokens])
        tokens = target_tokens
        stats['hard_truncated'] = True
        stats['steps_applied'].append('hard_truncate')

    stats['final_tokens'] = tokens

    # Write to output file
    output_filename = f"preprocessed_{arxiv_id}.txt"
    output_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)

    with open(output_filepath, 'w') as f:
        f.write(f"Paper: {arxiv_id}\n")
        f.write(f"Original HTML size: {stats['original_html_size']} chars\n")
        f.write(f"Final token count: {stats['final_tokens']}\n")
        f.write(f"Steps applied: {', '.join(stats['steps_applied'])}\n")
        f.write("=" * 80 + "\n\n")
        f.write(text)

    return text, tokens, output_filepath, stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 summarize_paper.py <arxiv_url_or_id> [target_tokens]")
        print("Example: python3 summarize_paper.py 2510.18876 200000")
        print("\nThis preprocesses a paper for LLM analysis by intelligently")
        print("removing cruft and low-information content to meet token budget.")
        sys.exit(1)

    arxiv_input = sys.argv[1]
    target_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 200000

    try:
        text, token_count, output_path, stats = preprocess_paper(
            arxiv_input,
            target_tokens=target_tokens
        )

        print(f"\n{'='*80}")
        print(f"PREPROCESSED - {token_count} tokens (target: {target_tokens})")
        print(f"Steps: {', '.join(stats['steps_applied'])}")
        print(f"Clean version: {stats.get('clean_filepath', 'N/A')}")
        print(f"Preprocessed:  {output_path}")
        print("=" * 80 + "\n")

        # Show first 2000 chars as preview
        print(text[:2000])
        if len(text) > 2000:
            print(f"\n... [{len(text) - 2000} more characters] ...")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

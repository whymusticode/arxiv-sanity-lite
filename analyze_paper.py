#!/usr/bin/env python3
"""
Analyze an arXiv paper using Claude API
Usage: python3 analyze_paper.py <arxiv_url_or_id>
Example: python3 analyze_paper.py https://arxiv.org/html/2510.18876v1
Example: python3 analyze_paper.py 2510.18876
"""

import os
import sys
import requests
from anthropic import Anthropic

def extract_arxiv_id(url_or_id):
    """Extract arxiv ID from URL or return the ID directly"""
    if url_or_id.startswith('http'):
        # Extract ID from URL
        parts = url_or_id.split('/')
        arxiv_id = parts[-1].replace('v1', '').replace('v2', '').replace('v3', '')
        return arxiv_id
    return url_or_id

def get_paper_html(arxiv_id):
    """Fetch the HTML version of the paper from arxiv"""
    url = f"https://arxiv.org/html/{arxiv_id}v1"
    print(f"Fetching paper from: {url}", file=sys.stderr)

    response = requests.get(url)
    response.raise_for_status()
    return response.text

def analyze_with_claude(html_content, prompt):
    """Send the paper HTML to Claude API with the prompt"""
    # api_key = os.environ.get('ANTHROPIC_API_KEY')
    api_key = 'REDACTED_API_KEY' # never upload this to the internet 
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    print("Sending to Claude API...", file=sys.stderr)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\nHere is the paper HTML:\n\n{html_content}"
            }
        ]
    )

    return message.content[0].text

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_paper.py <arxiv_url_or_id>")
        print("Example: python3 analyze_paper.py https://arxiv.org/html/2510.18876v1")
        print("Example: python3 analyze_paper.py 2510.18876")
        sys.exit(1)

    # Load prompt from prompt.jinja
    try:
        with open('prompt.jinja', 'r') as f:
            prompt = f.read().strip()
    except FileNotFoundError:
        print("Error: prompt.jinja not found", file=sys.stderr)
        sys.exit(1)

    arxiv_input = sys.argv[1]
    arxiv_id = extract_arxiv_id(arxiv_input)

    try:
        # Fetch paper HTML
        html_content = get_paper_html(arxiv_id)

        # Analyze with Claude
        analysis = analyze_with_claude(html_content, prompt)

        # Print the result
        print("\n" + "="*80)
        print("CLAUDE ANALYSIS")
        print("="*80 + "\n")
        print(analysis)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
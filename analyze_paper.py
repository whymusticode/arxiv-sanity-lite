#!/usr/bin/env python3
"""
Analyze an arXiv paper using Claude API
Usage: python3 analyze_paper.py <arxiv_url_or_id>
Example: python3 analyze_paper.py https://arxiv.org/html/2510.18876v1
Example: python3 analyze_paper.py 2510.18876

TODO
make it interactive so I can ask followup questions
Semantic Chunking + Embedding-Based Retrieval
"""


# def smart_truncate_with_embeddings(content, query, max_chars=200000):
#     """Use embeddings to find most relevant sections"""
    
#     # Split into semantic chunks (paragraphs, sections)
#     chunks = split_into_chunks(content, chunk_size=2000)
    
#     # Get embeddings for query and all chunks
#     client = Anthropic(api_key=api_key)
#     query_embedding = get_embedding(client, query)
#     chunk_embeddings = [get_embedding(client, chunk) for chunk in chunks]
    
#     # Calculate similarity scores
#     similarities = [cosine_similarity(query_embedding, ce) for ce in chunk_embeddings]
    
#     # Sort chunks by relevance and take top ones
#     ranked_chunks = sorted(zip(chunks, similarities), key=lambda x: x[1], reverse=True)
    
#     selected_content = []
#     current_length = 0
#     for chunk, score in ranked_chunks:
#         if current_length + len(chunk) > max_chars:
#             break
#         selected_content.append(chunk)
#         current_length += len(chunk)
    
#     return "\n\n".join(selected_content)

# def get_embedding(client, text):
#     """Get embedding from Claude or use a dedicated embedding model"""
#     # Note: You might want to use a dedicated embedding API like Voyage AI
#     # which Anthropic recommends, or OpenAI's embedding API
#     pass

# def cosine_similarity(a, b):
#     return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


import os
import sys
import requests
from anthropic import Anthropic
import numpy as np

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

def truncate_content(content, max_chars=200000):
    content_len = len(content)
    if content_len <= max_chars:
        return content
    print(f"Truncating from {content_len} to {max_chars}")
    truncated = content[:max_chars]
    return truncated

def analyze_with_claude(html_content, prompt):
    """Send the paper HTML to Claude API with the prompt"""
    # api_key = os.environ.get('ANTHROPIC_API_KEY')
    with open('api_key.txt', 'r') as file:
        api_key = file.read()

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)
    html_content = truncate_content(html_content)

    print("Sending to Claude API...", file=sys.stderr)
# claude-sonnet-4-5-20250929
# claude-haiku-4-5-20251001
# claude-opus-4-1-20250805
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
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
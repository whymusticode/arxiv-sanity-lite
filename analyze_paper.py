#!/usr/bin/env python3
"""
Analyze an arXiv paper using Claude API with intelligent preprocessing.
Includes interactive REPL for follow-up questions.

Usage: python3 analyze_paper.py <arxiv_url_or_id>
Example: python3 analyze_paper.py https://arxiv.org/html/2510.18876v1
Example: python3 analyze_paper.py 2510.18876
"""

import os
import sys
from bs4 import BeautifulSoup
from anthropic import Anthropic

# Import only what we need from summarize_paper
from summarize_paper import extract_arxiv_id, get_paper_html, extract_text_raw, count_tokens

# Lock files for REPL signaling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPL_ACTIVE_FILE = os.path.join(BASE_DIR, '.repl_active')
REPL_STOP_FILE = os.path.join(BASE_DIR, '.repl_stop')


def get_client():
    """Get Anthropic client"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return Anthropic(api_key=api_key)


def should_stop_repl():
    """Check if REPL should stop (another action triggered)"""
    return os.path.exists(REPL_STOP_FILE)


def cleanup_repl_files():
    """Clean up REPL signal files"""
    for f in [REPL_ACTIVE_FILE, REPL_STOP_FILE]:
        if os.path.exists(f):
            os.remove(f)


def start_repl_session():
    """Mark REPL as active"""
    cleanup_repl_files()  # Clean up any stale files
    with open(REPL_ACTIVE_FILE, 'w') as f:
        f.write(str(os.getpid()))


def run_repl(client, paper_content, conversation_history):
    """
    Run interactive REPL for follow-up questions.
    Exits when user types 'exit'/'quit' or another Flask action signals stop.
    """
    print("\n" + "="*80)
    print("INTERACTIVE MODE - Ask follow-up questions about the paper")
    print("Type 'exit' or 'quit' to end, or interact with the web UI")
    print("="*80 + "\n")

    start_repl_session()

    try:
        while True:
            # Check for stop signal before prompting
            if should_stop_repl():
                print("[Another action detected - ending REPL]")
                break

            try:
                user_input = input("You: ").strip()
            except EOFError:
                print("\nEnding interactive session.")
                break

            # Check stop signal after input too
            if should_stop_repl():
                print("[Another action detected - ending REPL]")
                break

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Ending interactive session.")
                break

            # Add user message to history
            conversation_history.append({
                "role": "user",
                "content": user_input
            })

            # Send to Claude
            print("Thinking...")
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=f"You are analyzing an academic paper. Here is the preprocessed content:\n\n{paper_content}",
                messages=conversation_history
            )

            response = message.content[0].text

            # Add assistant response to history
            conversation_history.append({
                "role": "assistant",
                "content": response
            })

            print(f"\nClaude: {response}\n")

    except KeyboardInterrupt:
        print("\n[Interrupted]")
    finally:
        cleanup_repl_files()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_paper.py <arxiv_url_or_id>")
        print("Example: python3 analyze_paper.py https://arxiv.org/html/2510.18876v1")
        print("Example: python3 analyze_paper.py 2510.18876")
        sys.exit(1)

    # Load prompt from prompt.jinja
    try:
        with open(os.path.join(BASE_DIR, 'prompt.jinja'), 'r') as f:
            prompt = f.read().strip()
    except FileNotFoundError:
        print("Error: prompt.jinja not found", file=sys.stderr)
        sys.exit(1)

    arxiv_input = sys.argv[1]
    arxiv_id = extract_arxiv_id(arxiv_input)

    try:
        # Fetch and do minimal preprocessing (just remove scripts/styles)
        print("Fetching paper...", file=sys.stderr)
        html_content = get_paper_html(arxiv_id)
        soup = BeautifulSoup(html_content, 'html.parser')
        paper_content = extract_text_raw(soup)
        token_count = count_tokens(paper_content)
        print(f"Paper: {token_count} tokens", file=sys.stderr)

        # Get Claude client
        client = get_client()

        # Initial analysis
        print("Sending to Claude API...", file=sys.stderr)
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\nHere is the preprocessed paper:\n\n{paper_content}"
                }
            ]
        )

        initial_response = message.content[0].text

        # Print the result
        print("\n" + "="*80)
        print("CLAUDE ANALYSIS")
        print("="*80 + "\n")
        print(initial_response)

        # Start conversation history for REPL
        conversation_history = [
            {
                "role": "user",
                "content": f"{prompt}\n\n[Paper content provided in system context]"
            },
            {
                "role": "assistant",
                "content": initial_response
            }
        ]

        # Enter interactive REPL
        run_repl(client, paper_content, conversation_history)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
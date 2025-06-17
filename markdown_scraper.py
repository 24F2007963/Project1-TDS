import os
import json
from pathlib import Path

def extract_markdown_to_json(repo_path, output_dir):
    repo_path = Path(repo_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".md"):
                full_path = Path(root) / file
                relative_path = full_path.relative_to(repo_path)
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                data = {
                    "source": str(relative_path),     # e.g., week1/index.md
                    "type": "course",                 # for discourse, use "discourse"
                    "text": content
                }

                output_filename = str(relative_path).replace(os.sep, "__") + ".json"
                output_path = output_dir / output_filename
                with open(output_path, "w", encoding="utf-8") as f_out:
                    json.dump(data, f_out, indent=2)

    print(f"✅ Extracted markdown content to JSON in: {output_dir}")

extract_markdown_to_json(
    repo_path="C:/Users/smriti.rani/Documents/New folder/iitm/Tools in DS/Course Source",
    output_dir="C:/Users/smriti.rani/Documents/New folder/iitm/Tools in DS/git project1/Project1-TDS/scraped/course"
)


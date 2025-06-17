import os
import json
import hashlib
from pathlib import Path
from openai import OpenAI
import tiktoken
# from dotenv import load_dotenv

enc = tiktoken.encoding_for_model("text-embedding-3-small")
MAX_TOKENS = 8000

# ---------------------------
# Configurations
# ---------------------------
API_KEY = os.getenv("AIPIPE_TOKEN")
if not API_KEY:
    raise ValueError("Missing AIPROXY_TOKEN environment variable")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://aipipe.org/openai/v1"  # or your preferred proxy
)

MODEL = "text-embedding-3-small"
DATA_DIR = Path(__file__).parent / "scraped"
EMBEDDINGS_DIR = Path(__file__).parent / "embeddings"
EMBEDDINGS_DIR.mkdir(exist_ok=True)

# ---------------------------
# Utilities
# ---------------------------

def split_text(text, max_tokens=1000):
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = enc.decode(tokens[i:i + max_tokens])
        chunks.append(chunk)
    return chunks

def embed_text(text: str):
    try:
        response = client.embeddings.create(
            model=MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return None


def load_json_files(folder: Path):
    docs = []
    for file in folder.glob("*.json"):
        with file.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    docs.extend(data)
                else:
                    docs.append(data)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON: {file}")
    return docs

def compute_hash(text: str):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def process_documents(docs, content_key: str, source_type: str):
    embeddings = []
    for doc in docs:
        full_text = doc.get(content_key, "").strip()
        if not full_text:
            continue
        print('new doc started')
        # Split long text into chunks
        chunks = split_text(full_text)

        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            if vector:
                embeddings.append({
                    "text": chunk,
                    "embedding": vector,
                    "source": source_type,
                    "chunk_index": i,
                    "meta": doc
                })

    return embeddings

# ---------------------------
# Main Execution
# ---------------------------

if __name__ == "__main__":
    print("Generating embeddings...")

    course_docs = load_json_files(DATA_DIR / "course")
    post_docs = load_json_files(DATA_DIR / "posts")

    course_embeddings = process_documents(course_docs, "text", "course")
    post_embeddings = process_documents(post_docs, "content", "discourse")

    all_embeddings = course_embeddings + post_embeddings

    output_path = EMBEDDINGS_DIR / "all_embeddings.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(all_embeddings, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(all_embeddings)} embeddings to {output_path}")

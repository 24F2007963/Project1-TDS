import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from openai import OpenAI  # ✅ new import
import numpy as np
from typing import Optional

# Initialize OpenAI client with proxy
client = OpenAI(
    base_url="http://aiproxy.sanand.workers.dev/openai/v1",  # ✅ proxy endpoint
    api_key=os.getenv("AIPROXY_TOKEN")
)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(BASE_DIR, "scraped", "posts")
COURSE_DIR = os.path.join(BASE_DIR, "scraped", "course")


# ----------------------------
# Utility to load JSON files
# ----------------------------

def load_embeddings(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Load saved embeddings once on startup
EMBEDDINGS_PATH = os.path.join(BASE_DIR, r"embeddings\all_embeddings.json")
doc_embeddings = load_embeddings(EMBEDDINGS_PATH)

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def find_top_k_similar(query_vec, docs, k=5):
    scores = []
    for doc in docs:
        score = cosine_similarity(query_vec, doc["embedding"])
        scores.append((score, doc))
    scores.sort(key=lambda x: x[0], reverse=True)
    return [doc for score, doc in scores[:k]]

def generate_link(meta: dict):
    if meta.get("source") == "post":
        topic_id = meta.get("meta", {}).get("topic_id")
        post_number = meta.get("meta", {}).get("post_number")
        slug = meta.get("meta", {}).get("slug")
        if topic_id and post_number and slug:
            return f"https://discourse.onlinedegree.iitm.ac.in/t/{slug}/{topic_id}/{post_number}"
    # Default link for course content
    return "https://tds.s-anand.net/#/tds-gpt-reviewer"

def load_json_files_from_dir(directory_path):
    documents = []
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        documents.extend(data)
                    else:
                        documents.append(data)
                except json.JSONDecodeError as e:
                    print(f"Skipping {filename}, JSON decode error: {e}")
    return documents

# ----------------------------
# Load Posts and Course Data
# ----------------------------

post_docs = load_json_files_from_dir(POSTS_DIR)
course_docs = load_json_files_from_dir(COURSE_DIR)

# ----------------------------
# Request and Response Models
# ----------------------------

class QueryRequest(BaseModel):
    question: str

class Link(BaseModel):
    url: str
    text: str

class QueryResponse(BaseModel):
    answer: str
    links: List[Link]

# ----------------------------
# FastAPI Endpoint
# ----------------------------

async def ask_question(request: QueryRequest):
    user_query = request.question

    # Step 1: Embed the user query
    try:
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=user_query
        )
        query_embedding = embedding_response.data[0].embedding
    except Exception as e:
        return {"answer": f"Embedding error: {str(e)}", "links": []}

    # Step 2: Find top matching docs by similarity
    top_docs = find_top_k_similar(query_embedding, doc_embeddings, k=5)

    # Step 3: Build context from top docs
    context = "\n\n---\n\n".join([doc["text"] for doc in top_docs])

    # Step 4: Compose prompt
    prompt = f"""You are a helpful teaching assistant. Use the context below to answer the user's question.

Context:
{context}

Question: {user_query}
Answer:"""

    # Step 5: Call GPT chat completion
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful teaching assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=512
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {"answer": f"Error generating response: {str(e)}", "links": []}

    # Step 6: Generate relevant links for top docs
    links = []
    for doc in top_docs:
        url = generate_link(doc)
        # Avoid duplicates
        if url not in [l.url for l in links]:
            links.append({"url": url, "text": doc["text"][:80] + ("..." if len(doc["text"]) > 80 else "")})

    return {"answer": answer, "links": links}
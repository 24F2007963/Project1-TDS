import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from openai import OpenAI  # ✅ new import
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Initialize OpenAI client with proxy
client = OpenAI(
    base_url="http://aiproxy.sanand.workers.dev/openai/v1",  # ✅ proxy endpoint
    api_key=os.getenv("AIPROXY_TOKEN")
)

app = FastAPI()

# ----------------------------
# Utility to load JSON files
# ----------------------------

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(BASE_DIR, "scraped", "posts")
COURSE_DIR = os.path.join(BASE_DIR, "scraped", "course")

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

@app.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    user_query = request.question

    # Step 1: Combine context
    context_chunks = []
    for item in course_docs:
        context_chunks.append(item.get("text", ""))
    for item in post_docs:
        context_chunks.append(item.get("content", ""))

    context = "\n\n---\n\n".join(context_chunks[:30])  # Limit context for prompt length

    # Step 2: Compose prompt
    prompt = f"""You are a helpful teaching assistant. Use the context below to answer the user's question. And 

Context:
{context}

Question: {user_query}
Answer:"""

    # Step 3: Call OpenAI proxy
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
        return {
            "answer": f"Error generating response: {str(e)}",
            "links": []
        }

    # Step 4: Prepare dummy links (or implement retrieval later)
    links = [
        {"url": "https://discourse.onlinedegree.iitm.ac.in/", "text": "IITM Discourse"},
        {"url": "https://github.com/s-anand/tds-course", "text": "Course GitHub Repo"}
    ]

    return {"answer": answer, "links": links}

import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from openai import OpenAI  # ✅ new import
import numpy as np
from typing import Optional
import re

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
EMBEDDINGS_PATH = os.path.join(BASE_DIR, "embeddings","all_embeddings.json")
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

def slugify(text: str) -> str:
    text = text.lower()
    # Replace non-alphanumeric characters (except hyphens) with a space
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Replace spaces and multiple hyphens with a single hyphen
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def generate_link(meta: dict):
    if meta.get("source") == "discourse":
        topic_id = meta.get("meta", {}).get("topic_id")
        post_number = meta.get("meta", {}).get("post_number")
        slug = slugify(meta.get("meta", {}).get("topic_title"))
        if topic_id and post_number :
            return f"https://discourse.onlinedegree.iitm.ac.in/t/{slug}/{topic_id}/{post_number}"
    elif meta.get("source") == "course":
        source_path = meta.get("meta", {}).get("source")
        filename = os.path.basename(source_path)
        filename_no_ext = os.path.splitext(filename)[0]
        final_file = filename_no_ext.split('\\')
        slug = slugify(final_file[-1])
        return f"https://tds.s-anand.net/#/{slug}"
    # Default link for course content
    return "https://tds.s-anand.net/#/README"

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
    image: Optional[str] = None  # Could be base64 encoded image or a URL
    link: Optional[str] = None

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
    user_image = request.image
    user_links = request.link

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

    context_parts = [doc["text"] for doc in top_docs]
    generated_links = [] # To store links from top_docs
    for doc in top_docs:
        url = generate_link(doc)
        if url not in [l["url"] for l in generated_links]:
            generated_links.append({"url": url, "text": doc["text"][:80] + ("..." if len(doc["text"]) > 80 else "")})


    # Process user-provided links
    if user_links:
        fetched_content = await fetch_url_content(user_links)
        if fetched_content:
            context_parts.append(f"Content from {user_links}:\n{fetched_content}")
            generated_links.append({"url": user_links, "text": f"User provided link: {user_links}"})


    context = "\n\n---\n\n".join(context_parts)

    # Step 4: Compose prompt and messages for multimodal LLM
    messages = [
        {"role": "system", "content": "You are a helpful teaching assistant. Use the provided context and any additional user inputs (like images or links) to answer the user's question. Prioritize information from the context. If an image is provided, analyze it if relevant to the question."},
    ]

    # Add image to messages if provided
    if user_image:
        # Determine image type. For the curl example, it's a .webp.
        image_mime_type = "image/webp" # Explicitly setting based on your example

        # Prepend the data URI prefix if it's not already there
        if not user_image.startswith("http://") and not user_image.startswith("https://") and not user_image.startswith("data:image/"):
            image_url_with_prefix = f"data:{image_mime_type};base64,{user_image}"
        else:
            image_url_with_prefix = user_image # Already a URL or has data URI prefix

        image_content = {"type": "image_url", "image_url": {"url": image_url_with_prefix}}

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": f"Question: {user_query}\n\nContext:\n{context}"},
                image_content
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": f"Question: {user_query}\n\nContext:\n{context}"
        })


    # Step 5: Call GPT chat completion
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=512
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        if user_image:
            try:
                messages_without_image = [
                    {"role": "system", "content": "You are a helpful teaching assistant. Use the provided context and any additional user inputs (like images or links) to answer the user's question. Prioritize information from the context. If an image is provided, analyze it if relevant to the question."},
                    {"role": "user", "content": f"Question: {user_query}\n\nContext:\n{context}"} # Only text content
                ]
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_without_image,
                    temperature=0.2,
                    max_tokens=512
                )
            
                answer = response.choices[0].message.content.strip() 
            except Exception as e2:
                return {"answer": f"Error generating response: {str(e2)}", "links": []}
        else:
            return {"answer": f"Error generating response: {str(e)}", "links": []}

    # Step 6: Generate relevant links for top docs
    links = []
    if user_links:
        for urls in user_links:
            links.append({"url": urls, "text": "check this discord post"})
    for doc in top_docs:
        url = generate_link(doc)
        # Avoid duplicates
        if url not in [l["url"] for l in links]:
            links.append({"url": url, "text": doc["text"][:80] + ("..." if len(doc["text"]) > 80 else "")})
    return {"answer": answer, "links": links}
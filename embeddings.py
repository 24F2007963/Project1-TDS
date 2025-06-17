import os, json
import openai
import dotenv

dotenv.load_dotenv()
openai.api_key = os.getenv("AIPROXY_TOKEN")
openai.api_base = "http://aiproxy.sanand.workers.dev/openai/v1"

def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def load_docs(dir_path, field):
    docs = []
    for fname in os.listdir(dir_path):
        if fname.endswith(".json"):
            with open(os.path.join(dir_path, fname), encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    docs.extend(data)
                else:
                    docs.append(data)
    return [{"text": d.get(field, ""), "meta": d} for d in docs if d.get(field, "").strip()]

def embed_and_save(docs, outfile):
    embedded = []
    for d in docs:
        embedding = get_embedding(d["text"])
        embedded.append({ "embedding": embedding, "text": d["text"], "meta": d["meta"] })
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(embedded, f)

if __name__ == "__main__":
    base = os.path.dirname(__file__)
    course_docs = load_docs(os.path.join(base, "scraped", "course"), "text")
    post_docs = load_docs(os.path.join(base, "scraped", "posts"), "content")

    embed_and_save(course_docs, os.path.join(base, "course_embeddings.json"))
    embed_and_save(post_docs, os.path.join(base, "post_embeddings.json"))

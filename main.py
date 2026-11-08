from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import chromadb

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ChromaDB connection ──
client = chromadb.PersistentClient(path="./data")
collection = client.get_or_create_collection(name="documents")


class IngestRequest(BaseModel):
    file_path: str
    file_name: str


class QueryRequest(BaseModel):
    question: str


class DeleteRequest(BaseModel):
    fileName: str


@app.get("/")
def root():
    return {"status": "Python AI Engine is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/ingest")
async def ingest(request: IngestRequest):
    try:
        from ingest import process_file
        result = process_file(request.file_path, request.file_name)
        return {"success": True, "message": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/query")
async def query(request: QueryRequest):
    try:
        from retriever import get_answer
        result = get_answer(request.question)
        return {
            "success": True,
            "answer": result["answer"],
            "sources": result["sources"],
            "is_image_request": result.get("is_image_request", False)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/delete")
async def delete(request: DeleteRequest):
    try:
        existing = collection.get()
        ids_to_delete = [
            id for id, meta in zip(existing['ids'], existing['metadatas'])
            if meta.get('source') == request.fileName
        ]
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
        return {"success": True, "message": f"Deleted {len(ids_to_delete)} chunks"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/stats")
async def get_stats():
    try:
        import os
        existing = collection.get()
        total_chunks = len(existing['documents'])
        sources = set()
        for meta in existing['metadatas']:
            if meta.get('source'):
                sources.add(meta.get('source'))

        uploads_folder = "../backend/uploads"
        uploaded_files = []
        if os.path.exists(uploads_folder):
            for f in os.listdir(uploads_folder):
                if f.endswith(('.pdf', '.docx', '.txt')):
                    parts = f.split('-', 1)
                    clean = parts[1] if len(parts) > 1 else f
                    uploaded_files.append(clean)

        return {
            "success": True,
            "total_chunks": total_chunks,
            "total_docs": len(set(uploaded_files)),
            "documents": list(set(uploaded_files))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/clear-memory")
async def clear_memory():
    try:
        from retriever import conversation_history
        conversation_history.clear()
        return {"success": True, "message": "Memory cleared!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/images")
async def get_images(keyword: str = "image"):
    try:
        from image_extractor import search_images_by_keyword
        uploads_folder = "../backend/uploads"
        images, status = search_images_by_keyword(keyword, uploads_folder)
        return {
            "success": True,
            "count": len(images),
            "images": images[:6]
        }
    except Exception as e:
        return {"success": False, "error": str(e), "images": []}


@app.get("/analyse-image")
async def analyse_image(keyword: str = "image", question: str = "describe this image"):
    try:
        from image_extractor import search_images_by_keyword
        import ollama

        uploads_folder = "../backend/uploads"
        images, status = search_images_by_keyword(keyword, uploads_folder)

        if not images:
            return {"success": False, "answer": "No images found to analyse.", "images": []}

        img = images[0]

        response = ollama.chat(
            model='llava',
            messages=[{
                'role': 'user',
                'content': question,
                'images': [img['base64']]
            }]
        )

        answer = response['message']['content']
        return {"success": True, "answer": answer, "images": [img]}

    except Exception as e:
        return {"success": False, "answer": str(e), "images": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

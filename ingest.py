import os
import fitz
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.PersistentClient(path="./data")
collection = client.get_or_create_collection(name="documents")


def extract_pages(file_path, file_name):
    ext = os.path.splitext(file_name)[1].lower()
    pages = []

    if ext == ".pdf":
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                pages.append({"page": i + 1, "text": text})
        doc.close()

    elif ext == ".docx":
        import docx as python_docx
        doc = python_docx.Document(file_path)

        full_text = []

        # Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())

        # Extract ALL table content
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        row_text.append(cell_text)
                if row_text:
                    full_text.append(" | ".join(row_text))

        combined = "\n".join(full_text)

        # Split into chunks
        chunk_size = 500
        step = 450
        for i in range(0, max(1, len(combined) - chunk_size + 1), step):
            chunk = combined[i:i+chunk_size].strip()
            if chunk:
                pages.append({"page": i//step + 1, "text": chunk})

        if not pages and combined:
            pages.append({"page": 1, "text": combined})

    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            full = f.read()
        chunk_size = 500
        step = 450
        for i in range(0, max(1, len(full)), step):
            chunk = full[i:i+chunk_size].strip()
            if chunk:
                pages.append({"page": i//step + 1, "text": chunk})

    return pages


def chunk_page(text, page_num, file_name, chunk_size=150, overlap=30):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i+chunk_size]
        chunk = " ".join(chunk_words)
        if len(chunk.strip()) > 20:
            chunks.append({
                "text": chunk,
                "page": page_num,
                "source": file_name
            })
        i += chunk_size - overlap
    return chunks


def is_already_uploaded(file_name):
    try:
        existing = collection.get()
        for meta in existing['metadatas']:
            if meta.get('source') == file_name:
                return True
        return False
    except:
        return False


def process_file(file_path, file_name):
    try:
        if is_already_uploaded(file_name):
            print(f"⚠️ {file_name} already uploaded")
            return f"{file_name} already uploaded!"

        print(f"📄 Processing: {file_name}")
        pages = extract_pages(file_path, file_name)

        if not pages:
            return "No text found in file"

        all_chunks = []
        for page_data in pages:
            page_chunks = chunk_page(
                page_data["text"],
                page_data["page"],
                file_name
            )
            all_chunks.extend(page_chunks)

        print(f"✅ {len(pages)} pages → {len(all_chunks)} chunks")

        # Store in batches
        batch_size = 50
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i+batch_size]
            texts = [c["text"] for c in batch]
            embeddings = model.encode(texts).tolist()
            ids = [f"{file_name}_p{c['page']}_c{i+j}" for j,
                   c in enumerate(batch)]
            metas = [{"source": c["source"], "page": c["page"]} for c in batch]
            collection.add(documents=texts, embeddings=embeddings,
                           ids=ids, metadatas=metas)

        print(f"✅ Stored {len(all_chunks)} chunks for {file_name}")
        return f"Successfully processed {file_name} — {len(all_chunks)} chunks stored"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"

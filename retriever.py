import ollama
import chromadb
import os
import re
import fitz
from sentence_transformers import SentenceTransformer
from collections import defaultdict

model = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.PersistentClient(path="./data")
collection = client.get_or_create_collection(name="documents")

last_shown_sources = []
last_selected_source = None
conversation_history = []

UPLOADS_FOLDER = "../backend/uploads"


def get_all_sources():
    try:
        existing = collection.get()
        sources = set()
        for meta in existing['metadatas']:
            if meta.get('source'):
                sources.add(meta.get('source'))
        return list(sources)
    except:
        return []


def get_file_path(source_name):
    try:
        for file in os.listdir(UPLOADS_FOLDER):
            parts = file.split('-', 1)
            clean = parts[1] if len(parts) > 1 else file
            if clean == source_name:
                return os.path.join(UPLOADS_FOLDER, file)
        return None
    except:
        return None


def get_page_text(file_path, page_num):
    try:
        doc = fitz.open(file_path)
        if page_num <= len(doc):
            text = doc[page_num - 1].get_text()
            doc.close()
            return text
        doc.close()
        return ""
    except:
        return ""


def read_docx_full(file_path):
    try:
        import docx as python_docx
        doc = python_docx.Document(file_path)
        lines = []
        for p in doc.paragraphs:
            if p.text.strip():
                lines.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception as e:
        print(f"❌ DOCX read error: {e}")
        return ""


def find_section(file_path, question):
    try:
        q_lower = question.lower()
        acts = re.findall(r'\bact\s+([ivxlcdm]+|\d+)\b', q_lower)
        scenes = re.findall(r'\bscene\s+([ivxlcdm]+|\d+)\b', q_lower)
        chapters = re.findall(r'\bchapter\s+([ivxlcdm]+|\d+)\b', q_lower)

        if not (acts or scenes or chapters):
            return None

        roman = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
                 'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10}
        arabic = {1: 'i', 2: 'ii', 3: 'iii', 4: 'iv', 5: 'v',
                  6: 'vi', 7: 'vii', 8: 'viii', 9: 'ix', 10: 'x'}

        def variants(n):
            n = n.lower()
            v = {n, n.upper()}
            if n.isdigit():
                num = int(n)
                if num in arabic:
                    v.add(arabic[num])
                    v.add(arabic[num].upper())
            elif n in roman:
                v.add(str(roman[n]))
            return v

        if not file_path.lower().endswith('.pdf'):
            return None

        doc = fitz.open(file_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        lines = full_text.split('\n')
        act_line = 0

        if acts:
            for i, line in enumerate(lines):
                ll = line.strip().lower()
                for v in variants(acts[0]):
                    if re.search(rf'\bact\s+{re.escape(v.lower())}\b', ll):
                        act_line = i
                        print(f"✅ ACT: {line.strip()}")
                        break

        if scenes:
            for i in range(act_line, len(lines)):
                ll = lines[i].strip().lower()
                for v in variants(scenes[0]):
                    if re.search(rf'\bscene\s+{re.escape(v.lower())}\b', ll):
                        print(f"✅ SCENE: {lines[i].strip()}")
                        return '\n'.join(lines[i:i+100])

        if chapters:
            for i, line in enumerate(lines):
                ll = line.strip().lower()
                for v in variants(chapters[0]):
                    if re.search(rf'\bchapter\s+{re.escape(v.lower())}\b', ll):
                        return '\n'.join(lines[i:i+100])

        if act_line > 0:
            return '\n'.join(lines[act_line:act_line+100])

        return None
    except Exception as e:
        print(f"❌ Section error: {e}")
        return None


def get_answer(question):
    global last_shown_sources, last_selected_source, conversation_history
    try:
        print(f"\n❓ Question: {question}")
        q = question.strip().lower()

        # ── 1. Greetings ──
        if q in ['hi', 'hello', 'hey', 'good morning', 'good evening',
                 'how are you', 'what are you', 'who are you']:
            return {
                "answer": "Hello! 👋 I am your **Offline AI Personal Assistant**.\n\nUpload documents and ask me anything!\n\nI work **100% offline**.",
                "sources": [], "is_image_request": False
            }

        # ── 2. Image check ──
        if any(w in q for w in ['image', 'images', 'figure', 'figures',
                                'picture', 'pictures', 'photo', 'photos', 'chart', 'charts',
                                'illustration', 'graphic', 'screenshot']):
            return {"answer": "🖼️ Here are the images I found:", "sources": [], "is_image_request": True}

        # ── 2.5 Image analysis check ──
        analysis_keywords = ['colour', 'color', 'analyse', 'analyze', 'analysis', 'describe',
                             'what colour', 'what color', 'what is in', 'whats in',
                             'tell me about the image', 'analyse the image', 'analyze the image',
                             'what does the image show', 'image analysis']
        is_analysis = any(k in q for k in analysis_keywords)
        if is_analysis:
            return {"answer": "🔍 Analysing image...", "sources": [], "is_image_request": False, "is_analysis": True}

        # ── 3. Number selection ──
        if q.strip() in [str(i) for i in range(1, 11)] and last_shown_sources:
            index = int(q.strip()) - 1
            if index < len(last_shown_sources):
                last_selected_source = last_shown_sources[index]
                return {
                    "answer": f"✅ Selected **{last_selected_source}**.\n\nNow ask me anything about this document!",
                    "sources": [last_selected_source], "is_image_request": False
                }

        # ── 4. Get all sources ──
        all_sources = get_all_sources()
        if not all_sources:
            return {
                "answer": "❌ No documents found. Please upload a document first!",
                "sources": [], "is_image_request": False
            }

        # ── 5. Check search all ──
        is_search_all = any(
            k in q for k in ['search all', 'all documents', 'all files', 'across all'])
        if is_search_all:
            last_selected_source = None

        # ── 6. Ask which document for generic section requests ──
        strict_keywords = [
            'abstract', 'introduction', 'conclusion', 'summary',
            'summarize', 'summarise', 'methodology', 'results',
            'discussion', 'references', 'overview', 'background'
        ]
        is_strict = any(k in q for k in strict_keywords)

        # Reset selected source if user asks for strict section again
        if is_strict and len(all_sources) > 1 and not is_search_all:
            last_selected_source = None
            mentioned = None
            for src in all_sources:
                src_name = src.split('.')[0].lower()
                if src.lower() in q or src_name in q:
                    mentioned = src
                    break
            if not mentioned:
                last_shown_sources = all_sources
                source_list = "\n".join(
                    [f"• **{i+1}.** {s}" for i, s in enumerate(all_sources)])
                return {
                    "answer": f"## Which document?\n\nI found **{len(all_sources)} documents**:\n\n{source_list}\n\nPlease type the **number** to select!\n\nOr type **'search all'** to search across all documents.",
                    "sources": all_sources,
                    "is_image_request": False
                }
            else:
                last_selected_source = mentioned

        # ── 7. ChromaDB semantic search ──
        question_embedding = model.encode([question]).tolist()[0]
        total = collection.count()
        n_results = min(8, total)

        where_filter = None
        if last_selected_source:
            where_filter = {"source": last_selected_source}

        if where_filter:
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=n_results,
                where=where_filter
            )
        else:
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=n_results
            )

        chunks = results['documents'][0]
        metadatas = results['metadatas'][0]

        if not chunks:
            return {"answer": "❌ No relevant content found.", "sources": [], "is_image_request": False}

        # ── 8. Find best source by keyword scoring ──
        stop_words = {'what', 'is', 'the', 'of', 'a', 'an', 'are', 'was', 'were',
                      'do', 'does', 'did', 'how', 'who', 'which', 'where', 'when',
                      'why', 'give', 'tell', 'me', 'my', 'show', 'find', 'get', 'in',
                      'it', 'its', 'for', 'and', 'or', 'but', 'with', 'from', 'to',
                      'i', 'you', 'we', 'they', 'this', 'that', 'these', 'those'}

        q_words = [w.lower() for w in question.split()
                   if len(w) > 1 and w.lower() not in stop_words]
        print(f"🔍 Search words: {q_words}")

        source_scores = defaultdict(float)
        for chunk, meta in zip(chunks, metadatas):
            src = meta.get('source', '')
            score = sum(1 for w in q_words if w in chunk.lower())
            source_scores[src] += score

        print(f"✅ Source scores: {dict(source_scores)}")

        if source_scores and max(source_scores.values()) > 0:
            best_source = max(source_scores, key=source_scores.get)
        else:
            source_count = defaultdict(int)
            for meta in metadatas:
                source_count[meta.get('source', '')] += 1
            best_source = max(source_count, key=source_count.get)

        print(f"✅ Best source: {best_source}")

        # ── 9. Get context ──
        file_path = get_file_path(best_source)

        section_text = None
        if file_path:
            section_text = find_section(file_path, question)

        if section_text:
            context = section_text
            print("✅ Using exact section")

        elif file_path and file_path.lower().endswith('.docx'):
            context = read_docx_full(file_path)
            print("✅ Using full DOCX with tables")

        elif file_path and file_path.lower().endswith('.pdf'):
            best_pages = list(set([m.get('page', 1) for m, c in zip(metadatas, chunks)
                                   if m.get('source') == best_source]))
            page_texts = []
            for page_num in sorted(best_pages)[:3]:
                text = get_page_text(file_path, page_num)
                if text:
                    page_texts.append(f"[Page {page_num}]\n{text}")
            context = "\n\n".join(
                page_texts) if page_texts else "\n\n".join(chunks)
            print(f"✅ Using PDF pages: {sorted(best_pages)[:3]}")

        else:
            context = "\n\n".join([c for c, m in zip(chunks, metadatas)
                                   if m.get('source') == best_source])

        # ── 10. Build prompt ──
        prompt = f"""You are a precise document assistant.

DOCUMENT: {best_source}

CONTENT:
{context}

QUESTION: {question}

STRICT RULES:
- Answer ONLY what was specifically asked — nothing more
- Do NOT return the entire document or unrelated sections
- If asked for a specific value (price, name, date, number) → return ONLY that value
- If asked for a section (abstract, conclusion) → return ONLY that specific section
- Keep the answer short and focused
- Use **bold** for key terms and values
- NEVER make up information not in the document
- NEVER say information is missing if it appears in the content above
- Give similar answer below ask if you need i can answer this

ANSWER:"""

        messages = [
            {'role': 'system', 'content': f'You are reading {best_source}. Answer ONLY what is asked. Be concise and precise. Never return unrelated content.'},
        ]
        for turn in conversation_history[-4:]:
            messages.append(turn)
        messages.append({'role': 'user', 'content': prompt})

        print("✅ Sending to Ollama...")
        response = ollama.chat(model='llama3.1:8b', messages=messages)
        answer = response['message']['content']
        print("✅ Answer received!")

        conversation_history.append({'role': 'user', 'content': question})
        conversation_history.append({'role': 'assistant', 'content': answer})
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]

        # Reset selected source after answering strict section
        if is_strict:
            last_selected_source = None
            print("✅ Reset selected source after strict section answer")

        return {"answer": answer, "sources": [best_source], "is_image_request": False}

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"answer": f"❌ Error: {str(e)}", "sources": [], "is_image_request": False}

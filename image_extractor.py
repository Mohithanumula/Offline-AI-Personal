import fitz
import os
import base64


def extract_images_from_pdf(file_path, file_name):
    try:
        doc = fitz.open(file_path)
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    if len(image_bytes) < 5000:
                        continue
                    img_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    images.append({
                        "page": page_num + 1,
                        "index": img_index + 1,
                        "ext": image_ext,
                        "base64": img_base64,
                        "source": file_name,
                        "label": ""
                    })
                except:
                    continue
        doc.close()
        return images
    except Exception as e:
        print(f"❌ Error extracting PDF images: {str(e)}")
        return []


def extract_images_from_docx_with_labels(file_path, file_name):
    try:
        import zipfile
        import docx as python_docx

        # Get text paragraphs in order
        doc = python_docx.Document(file_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        print(f"📝 Paragraphs in {file_name}: {paragraphs}")

        # Get images in order
        images = []
        img_index = 0
        with zipfile.ZipFile(file_path, 'r') as z:
            media_files = sorted(
                [n for n in z.namelist() if n.startswith('word/media/')])
            for name in media_files:
                ext = name.split('.')[-1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
                    try:
                        image_bytes = z.read(name)
                        if len(image_bytes) < 5000:
                            continue
                        img_base64 = base64.b64encode(
                            image_bytes).decode('utf-8')
                        label = paragraphs[img_index] if img_index < len(
                            paragraphs) else f"Image {img_index + 1}"
                        img_index += 1
                        images.append({
                            "page": 1,
                            "index": img_index,
                            "ext": ext,
                            "base64": img_base64,
                            "source": file_name,
                            "label": label
                        })
                        print(f"✅ Image {img_index} → Label: {label}")
                    except:
                        continue
        return images
    except Exception as e:
        print(f"❌ Error extracting DOCX images: {str(e)}")
        return []


def find_keyword_pages(file_path, keyword):
    try:
        doc = fitz.open(file_path)
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().lower()
            if keyword.lower() in text:
                pages.append(page_num + 1)
                print(f"✅ Found '{keyword}' on page {page_num + 1}")
        doc.close()
        return pages
    except:
        return []


def search_images_by_keyword(keyword, uploads_folder):
    try:
        if not os.path.exists(uploads_folder):
            return [], "Uploads folder not found"

        # Clean keyword
        stop_words = ['show', 'me', 'the', 'image', 'images', 'picture',
                      'photo', 'diagram', 'give', 'i', 'need', 'want',
                      'can', 'you', 'please', 'find', 'get', 'display',
                      'chart', 'graph', 'from', 'in', 'my', 'document',
                      'a', 'an', 'of', 'for', 'is', 'are', 'was', 'only',
                      'just', 'that', 'this', 'which', 'what', 'any']

        words = keyword.lower().split()
        search_terms = [w for w in words if w not in stop_words and len(w) > 2]
        print(f"🔍 Search terms: {search_terms}")

        if not search_terms:
            return [], "No search terms found"

        matched_images = []
        files = os.listdir(uploads_folder)

        for file in files:
            file_path = os.path.join(uploads_folder, file)
            parts = file.split('-', 1)
            clean_name = parts[1] if len(parts) > 1 else file

            if file.lower().endswith('.pdf'):
                # Find pages containing keyword
                matched_pages = set()
                for term in search_terms:
                    pages = find_keyword_pages(file_path, term)
                    matched_pages.update(pages)

                if matched_pages:
                    all_images = extract_images_from_pdf(file_path, clean_name)
                    for img in all_images:
                        if img['page'] in matched_pages:
                            matched_images.append(img)
                            print(f"✅ PDF image from page {img['page']}")

            elif file.lower().endswith('.docx'):
                # Extract images with labels
                images = extract_images_from_docx_with_labels(
                    file_path, clean_name)
                for img in images:
                    label = img.get('label', '').lower()
                    for term in search_terms:
                        if term in label:
                            matched_images.append(img)
                            print(f"✅ DOCX image matched: {img['label']}")
                            break

        if matched_images:
            print(f"✅ Total matched: {len(matched_images)}")
            return matched_images, "found"
        else:
            return [], f"No images found for: {', '.join(search_terms)}"

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return [], str(e)


def get_all_images(uploads_folder):
    all_images = []
    seen = set()
    try:
        if not os.path.exists(uploads_folder):
            return []
        for file in os.listdir(uploads_folder):
            file_path = os.path.join(uploads_folder, file)
            parts = file.split('-', 1)
            clean_name = parts[1] if len(parts) > 1 else file
            if file.lower().endswith('.pdf'):
                images = extract_images_from_pdf(file_path, clean_name)
                for img in images:
                    key = f"{clean_name}_{img['page']}_{img['index']}"
                    if key not in seen:
                        seen.add(key)
                        all_images.append(img)
            elif file.lower().endswith('.docx'):
                images = extract_images_from_docx_with_labels(
                    file_path, clean_name)
                for img in images:
                    key = f"{clean_name}_{img['index']}"
                    if key not in seen:
                        seen.add(key)
                        all_images.append(img)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    return all_images

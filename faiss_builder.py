import os
import re
import json
from typing import List, Dict
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings

# =============================================================
# EMBEDDING - DÙNG HUGGING FACE (OFFLINE)
# =============================================================
class HuggingFaceEmbeddings(Embeddings):
    def __init__(self, model_name: str = "anhtld/VN-Law-Embedding"):
        print(f"Đang tải model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("✅ Model đã tải xong!")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(
            texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True
        ).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

# =============================================================
# ĐỌC CHUNKS ĐÃ LƯU
# =============================================================
def load_chunks_from_preview(folder: str) -> List[Document]:
    documents = []
    folder_path = Path(folder)
    total_chunks = 0
    print(f"📂 Đang đọc các file chunk từ: {folder_path.resolve()}")

    for file_path in folder_path.glob("*_chunks.txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Cắt chuẩn theo dòng chứa >= 50 dấu "="
        chunks = re.split(r"\n={50,}\n", content)
        chunks = [c.strip() for c in chunks if c.strip()]
        print(f"📄 {file_path.name}: {len(chunks)} chunks")

        for chunk in chunks:
            lines = chunk.split("\n")
            metadata = {}
            page_content = []
            in_content = False

            for line in lines:
                if line.startswith("CONTENT:"):
                    in_content = True
                    continue
                if not in_content and ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip()
                elif in_content:
                    page_content.append(line)

            if not page_content:
                continue  # loại bỏ chunk rỗng

            doc = Document(
                page_content="\n".join(page_content).strip(),
                metadata=metadata
            )
            documents.append(doc)

        total_chunks += len(chunks)

    print(f"✅ Tổng cộng load {len(documents)} documents từ {total_chunks} chunk trong folder.")
    return documents

# =============================================================
# KIỂM TRA DATABASE CÓ TỒN TẠI
# =============================================================
def check_database_exists(path: str) -> bool:
    index_file = os.path.join(path, "index.faiss")
    pkl_file = os.path.join(path, "index.pkl")
    return os.path.exists(index_file) and os.path.exists(pkl_file)

# =============================================================
# MAIN - TẠO HOẶC CẬP NHẬT FAISS KÉP
# =============================================================
if __name__ == "__main__":
    CHUNKS_FOLDER = "chunk_preview_Luat_Bao_Ve_Moi_Truong_Trang_1"
    SAVE_PATH = "database/faiss_legal_index"
    META_SAVE_PATH = "database/faiss_metadata_index"
    MAPPING_FILE = "database/metadata_chunk_mapping.json"

    os.makedirs("database", exist_ok=True)

    # 1️⃣ Load chunks
    print("📂 Đang đọc các chunk đã lưu...")
    documents = load_chunks_from_preview(CHUNKS_FOLDER)
    print(f"✅ Đã load {len(documents)} chunks")

    # 2️⃣ Embedding
    print("\n🔢 Đang tạo embedding...")
    embeddings = HuggingFaceEmbeddings()

    # =========================================================
    # FAISS CHO NỘI DUNG
    # =========================================================
    print("\n🧠 Xử lý FAISS cho nội dung...")
    if check_database_exists(SAVE_PATH):
        print(f"📦 Database content đã tồn tại tại: {SAVE_PATH}/")
        vectorstore_content = FAISS.load_local(SAVE_PATH, embeddings, allow_dangerous_deserialization=True)
        vectorstore_content.add_documents(documents)
        print(f"✅ Đã thêm {len(documents)} documents vào database content")
    else:
        print("🆕 Tạo database content mới...")
        vectorstore_content = FAISS.from_documents(documents, embeddings)
        print(f"✅ Đã tạo database content với {len(documents)} documents")
    vectorstore_content.save_local(SAVE_PATH)
    print(f"✅ Đã lưu FAISS content tại: {SAVE_PATH}/")

    # =========================================================
    # FAISS CHO METADATA
    # =========================================================
    print("\n🧩 Xử lý FAISS cho metadata...")

    existing_mapping: Dict[str, str] = {}
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            existing_mapping = json.load(f)
        print(f"📖 Load mapping hiện có từ {MAPPING_FILE}")

    meta_docs = []
    meta_mapping: Dict[str, str] = {}

    for doc in documents:
        # --- Tách hai nhóm metadata ---
        # Nhóm 1: Điều, Khoản, Điểm, Mục, Chương
        structure_parts = []
        for k in ["Chương", "Điều", "Khoản", "Điểm", "Mục"]:
            if k in doc.metadata:
                structure_parts.append(f"{k}:{doc.metadata[k]}")
        structure_str = " ".join(structure_parts)

        # Nhóm 2: Tên văn bản
        title_str = f"Tên văn bản: {doc.metadata.get('Tên văn bản','')}".strip()

        # Ghép hai nhóm làm metadata FAISS
        meta_str = f"{title_str} {structure_str}".strip()

        meta_docs.append(Document(page_content=meta_str))
        meta_mapping[meta_str] = doc.page_content

    # Merge mapping cũ và mới
    existing_mapping.update(meta_mapping)

    # Tạo hoặc cập nhật FAISS metadata
    if check_database_exists(META_SAVE_PATH):
        print(f"📦 Database metadata đã tồn tại tại: {META_SAVE_PATH}/")
        vectorstore_meta = FAISS.load_local(META_SAVE_PATH, embeddings, allow_dangerous_deserialization=True)
        vectorstore_meta.add_documents(meta_docs)
        print(f"✅ Đã thêm {len(meta_docs)} metadata vào database")
    else:
        print("🆕 Tạo database metadata mới...")
        vectorstore_meta = FAISS.from_documents(meta_docs, embeddings)
        print(f"✅ Đã tạo database metadata với {len(meta_docs)} documents")
    vectorstore_meta.save_local(META_SAVE_PATH)
    print(f"✅ Đã lưu FAISS metadata tại: {META_SAVE_PATH}/")

    # =========================================================
    # Lưu mapping metadata → content
    # =========================================================
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_mapping, f, ensure_ascii=False, indent=2)
    print(f"✅ Mapping metadata → content đã lưu tại: {MAPPING_FILE}")
    print(f"📊 Tổng số mapping: {len(existing_mapping)} entries")

    print("\n🎯 HOÀN TẤT! Hệ thống FAISS kép đã sẵn sàng.")

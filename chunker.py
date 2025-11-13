import re
from typing import List, Dict, Any, Tuple
from pathlib import Path
from langchain_core.documents import Document

# =============================================================
# CHUNKER - FIXED: XỬ LÝ CẢ NỘI DUNG TRƯỚC CHƯƠNG + GHI CHƯƠNG VÀO METADATA
# =============================================================
class LegalDocumentChunker:
    def __init__(self):
        # FIXED: Thêm \s* sau (?:^|\n) để bắt được dấu cách đầu dòng
        self.chuong_pattern = re.compile(r"(?:^|\n)\s*(Chương\s+[IVXLC]+\.?\s*[^\n]*)", re.MULTILINE)
        self.muc_pattern = re.compile(r"(?:^|\n)\s*(Mục\s+[IVXLC\d]+\.?\s*[^\n]*)", re.MULTILINE)
        self.dieu_pattern = re.compile(r"(?:^|\n)\s*(Điều\s+\d+\.?\s*[^\n]*)", re.MULTILINE)
        self.khoan_pattern = re.compile(r"(?:^|\n)\s*(\d+)\.\s", re.MULTILINE)
        self.diem_pattern = re.compile(r"(?:^|\n)\s*([a-zđ])[)\.]?\s", re.MULTILINE)

    def chunk_legal_document(self, text: str, metadata: Dict[str, Any]) -> List[Document]:
        documents = []
        text = text.replace("\r", "").strip()
        text = re.sub(r"[ \t]+", " ", text)
        chuong_matches = list(self.chuong_pattern.finditer(text))
        
        if not chuong_matches:
            documents.extend(self._split_by_muc_or_dieu(text, "", metadata))
            return documents
        
        # === XỬ LÝ NỘI DUNG TRƯỚC CHƯƠNG ĐẦU TIÊN ===
        first_chuong_start = chuong_matches[0].start()
        if first_chuong_start > 0:
            pre_content = text[:first_chuong_start].strip()
            if pre_content:
                pre_docs = self._split_by_muc_or_dieu(pre_content, "", metadata)
                documents.extend(pre_docs)
        
        # === XỬ LÝ CÁC CHƯƠNG ===
        for i, match in enumerate(chuong_matches):
            chuong_title = match.group(1).strip()
            start_pos = match.end()
            end_pos = chuong_matches[i + 1].start() if i + 1 < len(chuong_matches) else len(text)
            chuong_content = text[start_pos:end_pos]
            docs = self._split_by_muc_or_dieu(chuong_content, chuong_title, metadata)
            documents.extend(docs)
        
        return documents

    def _split_by_muc_or_dieu(self, text: str, chuong: str, metadata: Dict[str, Any]) -> List[Document]:
        documents = []
        muc_matches = list(self.muc_pattern.finditer(text))
        
        if not muc_matches:
            return self._split_by_dieu(text, chuong, "", metadata)
        
        # === XỬ LÝ NỘI DUNG TRƯỚC MỤC ĐẦU TIÊN ===
        first_muc_start = muc_matches[0].start()
        if first_muc_start > 0:
            pre_content = text[:first_muc_start].strip()
            if pre_content:
                pre_docs = self._split_by_dieu(pre_content, chuong, "", metadata)
                documents.extend(pre_docs)
        
        # === XỬ LÝ CÁC MỤC ===
        for i, match in enumerate(muc_matches):
            muc_title = match.group(1).strip()
            start_pos = match.end()
            end_pos = muc_matches[i + 1].start() if i + 1 < len(muc_matches) else len(text)
            muc_content = text[start_pos:end_pos]
            dieu_docs = self._split_by_dieu(muc_content, chuong, muc_title, metadata)
            documents.extend(dieu_docs)
        
        return documents

    def _split_by_dieu(self, text: str, chuong: str, muc: str, metadata: Dict[str, Any]) -> List[Document]:
        documents = []
        dieu_matches = list(self.dieu_pattern.finditer(text))
        
        if not dieu_matches:
            if text.strip():
                meta = {**metadata, "Chương": chuong, "Mục": muc, "Điều": "", "Khoản": ""}
                return [Document(page_content=text.strip(), metadata=meta)]
            return []
        
        # === XỬ LÝ NỘI DUNG TRƯỚC ĐIỀU ĐẦU TIÊN ===
        first_dieu_start = dieu_matches[0].start()
        if first_dieu_start > 0:
            pre_content = text[:first_dieu_start].strip()
            if pre_content:
                meta = {**metadata, "Chương": chuong, "Mục": muc, "Điều": "", "Khoản": ""}
                documents.append(Document(page_content=pre_content, metadata=meta))
        
        # === XỬ LÝ CÁC ĐIỀU ===
        for i, match in enumerate(dieu_matches):
            dieu_title = match.group(1).strip()
            start_pos = match.end()
            end_pos = dieu_matches[i + 1].start() if i + 1 < len(dieu_matches) else len(text)
            dieu_content = text[start_pos:end_pos].strip()
            if dieu_content:
                dieu_docs = self._split_by_khoan(dieu_content, chuong, muc, dieu_title, metadata)
                documents.extend(dieu_docs)
        
        return documents

    def _split_by_khoan(
        self, content: str, chuong: str, muc: str, dieu: str, base_meta: Dict[str, Any]
    ) -> List[Document]:
        khoan_matches = list(self.khoan_pattern.finditer(content))
        documents = []

        if len(khoan_matches) == 0:
            meta = {**base_meta, "Chương": chuong, "Mục": muc, "Điều": dieu, "Khoản": ""}
            return [Document(page_content=content.strip(), metadata=meta)]

        total_khoan = len(khoan_matches)
        khoan_nums = [match.group(1) for match in khoan_matches]
        khoan_str = ", ".join(khoan_nums)

        # === ĐIỀU KIỆN MỚI: Nếu > 10 khoản → chia nhỏ ===
        if total_khoan > 10:
            le = total_khoan % 10
            # Nếu phần lẻ < 5 → gộp vào chunk cuối
            if le > 0 and le < 5:
                chunk_size = 10
                num_chunks = total_khoan // 10
                last_chunk_size = 10 + le
            else:
                # Nếu phần lẻ >= 5 hoặc chia hết → giữ nguyên chunk 10
                chunk_size = 10
                num_chunks = (total_khoan + 9) // 10  # làm tròn lên
                last_chunk_size = le if le >= 5 else 10
            
            # Tách thành các chunk
            for chunk_idx in range(num_chunks):
                start_idx = chunk_idx * 10
                if chunk_idx == num_chunks - 1:
                    # Chunk cuối
                    end_idx = total_khoan
                else:
                    end_idx = start_idx + 10
                
                # Lấy nội dung từ khoản start_idx đến end_idx-1
                chunk_start = khoan_matches[start_idx].start()
                chunk_end = khoan_matches[end_idx].start() if end_idx < total_khoan else len(content)
                chunk_content = content[chunk_start:chunk_end].strip()
                
                # Metadata cho chunk này
                chunk_khoan_nums = khoan_nums[start_idx:end_idx]
                chunk_khoan_str = ", ".join(chunk_khoan_nums)
                
                meta = {
                    **base_meta,
                    "Chương": chuong,
                    "Mục": muc,
                    "Điều": dieu,
                    "Khoản": chunk_khoan_str
                }
                documents.append(Document(page_content=chunk_content, metadata=meta))
            
            return documents

        # === LOGIC GỐC: ≤10 khoản + ≤1 khoản phức tạp → giữ nguyên toàn Điều ===
        phuc_tap_count = 0
        for i, match in enumerate(khoan_matches):
            start_pos = match.start()
            end_pos = khoan_matches[i + 1].start() if i + 1 < len(khoan_matches) else len(content)
            khoan_content = content[start_pos:end_pos].strip()
            num_diem = len(self.diem_pattern.findall(khoan_content))
            if num_diem > 2:
                phuc_tap_count += 1

        if phuc_tap_count <= 1:
            meta = {
                **base_meta,
                "Chương": chuong,
                "Mục": muc,
                "Điều": dieu,
                "Khoản": khoan_str
            }
            return [Document(page_content=content.strip(), metadata=meta)]

        # === ≥2 khoản phức tạp → TÁCH RIÊNG TỪNG KHOẢN ===
        for i, match in enumerate(khoan_matches):
            khoan_num = match.group(1)
            start_pos = match.start()
            end_pos = khoan_matches[i + 1].start() if i + 1 < len(khoan_matches) else len(content)
            khoan_content = content[start_pos:end_pos].strip()
            meta = {
                **base_meta,
                "Chương": chuong,
                "Mục": muc,
                "Điều": dieu,
                "Khoản": khoan_num
            }
            documents.append(Document(page_content=khoan_content, metadata=meta))

        return documents


# =============================================================
# UTILS
# =============================================================
def parse_metadata_file(metadata_path: str) -> Dict[str, Any]:
    metadata = {}
    with open(metadata_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for line in content.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip()
    return metadata

def scan_van_ban_folder(root_folder: str) -> List[Tuple[str, str]]:
    document_pairs = []
    root_path = Path(root_folder)
    for sub_folder in root_path.iterdir():
        if sub_folder.is_dir():
            content_file = sub_folder / "noi_dung.txt"
            metadata_file = sub_folder / "metadata.txt"
            if content_file.exists() and metadata_file.exists():
                document_pairs.append((str(content_file), str(metadata_file)))
    return document_pairs

def save_chunks_to_file(documents: List[Document], output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, doc in enumerate(documents, 1):
            f.write(f"\n{'='*80}\nCHUNK {i}\n{'='*80}\n")
            if "Tên văn bản" in doc.metadata:
                f.write(f"Tên văn bản: {doc.metadata['Tên văn bản']}\n")
            if doc.metadata.get("Chương"):
                f.write(f"Chương: {doc.metadata['Chương']}\n")
            if doc.metadata.get("Mục"):
                f.write(f"Mục: {doc.metadata['Mục']}\n")
            if doc.metadata.get("Điều"):
                f.write(f"Điều: {doc.metadata['Điều']}\n")
            if doc.metadata.get("Khoản"):
                f.write(f"Khoản: {doc.metadata['Khoản']}\n")
            f.write(f"\nCONTENT:\n{doc.page_content}\n")


# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    ROOT_FOLDER = "Luat_Bao_Ve_Moi_Truong_Trang_1"
    OUTPUT_FOLDER = "chunk_preview_Luat_Bao_Ve_Moi_Truong_Trang_1"

    chunker = LegalDocumentChunker()
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    print(f"Đang quét: {ROOT_FOLDER}")
    document_pairs = scan_van_ban_folder(ROOT_FOLDER)
    print(f"Tìm thấy {len(document_pairs)} văn bản\n")

    total_chunks = 0
    for idx, (content_path, metadata_path) in enumerate(document_pairs, 1):
        metadata = parse_metadata_file(metadata_path)
        ten_van_ban = metadata.get('Tên văn bản', 'Unknown')
        print(f"[{idx}/{len(document_pairs)}] {ten_van_ban[:60]}...")

        with open(content_path, 'r', encoding='utf-8') as f:
            content = f.read()

        documents = chunker.chunk_legal_document(content, metadata)
        total_chunks += len(documents)

        safe_name = re.sub(r'[^\w\s-]', '', ten_van_ban)[:80].replace(' ', '_')
        save_chunks_to_file(documents, f"{OUTPUT_FOLDER}/{safe_name}_chunks.txt")
        print(f"   {len(documents)} chunk(s)")

    print(f"\nHOÀN TẤT!")
    print(f"Tổng: {total_chunks} chunk")
    print(f"Xem tại: {OUTPUT_FOLDER}/")
import streamlit as st
import json
import re
import os
from google import genai
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi
import pickle
from typing import List, Dict

# =============================================================
# CẤU HÌNH
# =============================================================
API_KEY = "AIzaSyCpJvpVHycd1n0ezfRnecrYfVFaJMeKoRM"
SAVE_PATH = "database/faiss_legal_index"
META_SAVE_PATH = "database/faiss_metadata_index"
MAPPING_FILE = "database/metadata_chunk_mapping.json"
BM25_INDEX_FILE = "database/bm25_metadata_index.pkl"

# =============================================================
# KHỞI TẠO GEMINI CLIENT
# =============================================================
@st.cache_resource
def init_gemini_client():
    return genai.Client(api_key=API_KEY)

# =============================================================
# TẢI EMBEDDING MODEL
# =============================================================
@st.cache_resource
def load_embedding_model(model_name: str = "anhtld/VN-Law-Embedding"):
    model_kwargs = {"device": "cpu"}
    encode_kwargs = {"normalize_embeddings": True}
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    return embeddings

# =============================================================
# CHUẨN HÓA VÀ TRÍCH XUẤT THÔNG TIN TỪ METADATA (MỚI)
# =============================================================
def parse_metadata_structure(metadata: str) -> dict:
    """Trích xuất cấu trúc pháp luật từ metadata string"""
    result = {
        "ten_van_ban": "",
        "chuong": "",
        "muc": "",
        "dieu": "",
        "khoan": "",
        "raw": metadata
    }
    
    # Trích xuất tên văn bản
    if "Tên văn bản:" in metadata:
        match = re.search(r'Tên văn bản:\s*([^\n]+)', metadata)
        if match:
            result["ten_van_ban"] = match.group(1).strip()
    
    # Trích xuất chương
    if "Chương:" in metadata:
        match = re.search(r'Chương:\s*([^\n]+)', metadata)
        if match:
            result["chuong"] = match.group(1).strip()
    
    # Trích xuất mục
    if "Mục:" in metadata:
        match = re.search(r'Mục:\s*([^\n]+)', metadata)
        if match:
            result["muc"] = match.group(1).strip()
    
    # Trích xuất điều (QUAN TRỌNG!)
    if "Điều:" in metadata:
        match = re.search(r'Điều:\s*(Điều\s*\d+[^\n]*)', metadata)
        if match:
            result["dieu"] = match.group(1).strip()
    
    # Trích xuất khoản
    if "Khoản:" in metadata:
        match = re.search(r'Khoản:\s*([^\n]+)', metadata)
        if match:
            result["khoan"] = match.group(1).strip()
    
    return result

# =============================================================
# TOKENIZATION THÔNG MINH CHO BM25 (MỚI)
# =============================================================
def smart_tokenize_metadata(metadata: str) -> List[str]:
    """
    Tokenize metadata với xử lý đặc biệt cho cấu trúc pháp luật
    Ví dụ: "Điều 6" -> ['điều', '6', 'điều_6']
    """
    tokens = []
    
    # Parse cấu trúc
    structure = parse_metadata_structure(metadata)
    
    # 1. Thêm tokens từ tên văn bản
    if structure["ten_van_ban"]:
        van_ban_tokens = re.findall(r'\w+', structure["ten_van_ban"].lower())
        tokens.extend(van_ban_tokens)
    
    # 2. Xử lý Điều (QUAN TRỌNG!)
    if structure["dieu"]:
        dieu_text = structure["dieu"].lower()
        
        # Trích xuất số điều
        dieu_match = re.search(r'điều\s*(\d+)', dieu_text)
        if dieu_match:
            dieu_num = dieu_match.group(1)
            
            # Thêm cả từng token và bigram
            tokens.extend(['điều', dieu_num])
            tokens.append(f'điều_{dieu_num}')  # Bigram quan trọng!
            
            # Thêm title của điều nếu có
            title_match = re.search(r'điều\s*\d+[.\s]*(.+)', dieu_text)
            if title_match:
                title_tokens = re.findall(r'\w+', title_match.group(1).lower())
                tokens.extend(title_tokens)
    
    # 3. Xử lý Chương
    if structure["chuong"]:
        chuong_tokens = re.findall(r'\w+', structure["chuong"].lower())
        tokens.extend(chuong_tokens)
    
    # 4. Xử lý Mục
    if structure["muc"]:
        muc_tokens = re.findall(r'\w+', structure["muc"].lower())
        tokens.extend(muc_tokens)
    
    # 5. Xử lý Khoản
    if structure["khoan"]:
        khoan_tokens = re.findall(r'\w+', structure["khoan"].lower())
        tokens.extend(khoan_tokens)
    
    return tokens

# =============================================================
# XÂY DỰNG BM25 INDEX CẢI TIẾN (MỚI)
# =============================================================
def build_bm25_index(meta_mapping: dict):
    """Xây dựng BM25 index với tokenization thông minh"""
    metadata_list = list(meta_mapping.keys())
    
    # Tokenize với xử lý đặc biệt
    tokenized_metadata = [
        smart_tokenize_metadata(meta) 
        for meta in metadata_list
    ]
    
    # Tạo BM25 index với tham số tối ưu
    bm25 = BM25Okapi(tokenized_metadata, k1=1.5, b=0.75)
    
    return bm25, metadata_list

# =============================================================
# LƯU VÀ TẢI BM25 INDEX
# =============================================================
def save_bm25_index(bm25, metadata_list, filepath):
    """Lưu BM25 index và metadata list"""
    with open(filepath, 'wb') as f:
        pickle.dump({'bm25': bm25, 'metadata_list': metadata_list}, f)

def load_bm25_index(filepath):
    """Tải BM25 index và metadata list"""
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        return data['bm25'], data['metadata_list']
    return None, None

# =============================================================
# TẢI FAISS VÀ MAPPING
# =============================================================
@st.cache_resource
def load_vector_stores():
    embeddings = load_embedding_model()
    
    if not os.path.exists(SAVE_PATH):
        return None, None, None, embeddings, None, None
    
    vectorstore_content = FAISS.load_local(
        SAVE_PATH, 
        embeddings, 
        allow_dangerous_deserialization=True
    )
    vectorstore_meta = FAISS.load_local(
        META_SAVE_PATH, 
        embeddings, 
        allow_dangerous_deserialization=True
    )
    
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        meta_mapping = json.load(f)
    
    # Tải hoặc xây dựng BM25 index
    bm25, metadata_list = load_bm25_index(BM25_INDEX_FILE)
    
    if bm25 is None:
        st.info("🔨 Đang xây dựng BM25 index cải tiến lần đầu...")
        bm25, metadata_list = build_bm25_index(meta_mapping)
        save_bm25_index(bm25, metadata_list, BM25_INDEX_FILE)
        st.success("✅ BM25 index đã được xây dựng!")
    
    return vectorstore_content, vectorstore_meta, meta_mapping, embeddings, bm25, metadata_list

# =============================================================
# TÌM KIẾM BM25 CẢI TIẾN (MỚI)
# =============================================================
def search_bm25_metadata(query: str, bm25, metadata_list, meta_mapping, top_k=10) -> List[Dict]:
    """
    Tìm kiếm BM25 với xử lý đặc biệt cho queries có cấu trúc
    """
    # 1. Trích xuất cấu trúc từ query
    structure = extract_legal_structure(query)
    
    # 2. Tokenize query tương tự như metadata
    query_tokens = []
    
    # Xử lý Điều trong query
    if "dieu" in structure:
        dieu_num = structure["dieu"]
        query_tokens.extend(['điều', dieu_num, f'điều_{dieu_num}'])
    
    # Thêm các tokens khác từ query
    query_tokens.extend(re.findall(r'\w+', query.lower()))
    
    # 3. Tính BM25 scores
    scores = bm25.get_scores(query_tokens)
    
    # 4. Áp dụng BOOST cho exact match số điều
    if "dieu" in structure:
        dieu_num = structure["dieu"]
        dieu_pattern = rf'điều\s*{re.escape(dieu_num)}\b'
        
        for idx, metadata in enumerate(metadata_list):
            if re.search(dieu_pattern, metadata.lower(), re.IGNORECASE):
                scores[idx] *= 3.0  # BOOST x3 cho exact match!
    
    # 5. Áp dụng BOOST cho tên văn bản match
    if "luat" in structure:
        luat_name = structure["luat"].lower()
        for idx, metadata in enumerate(metadata_list):
            if luat_name in metadata.lower():
                scores[idx] *= 1.5  # BOOST x1.5 cho matching law name
    
    # 6. Lấy top K
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    results = []
    for idx in top_indices:
        if scores[idx] > 0:
            metadata = metadata_list[idx]
            content = meta_mapping.get(metadata, "")
            
            results.append({
                "metadata": metadata,
                "content": content,
                "source": "improved_bm25_search",
                "score": float(scores[idx])
            })
    
    return results

# =============================================================
# TRÍCH XUẤT THÔNG TIN CẤU TRÚC TỪ QUERY
# =============================================================
def extract_legal_structure(query: str) -> dict:
    """Trích xuất các thành phần cấu trúc pháp luật từ câu hỏi."""
    structure = {}
    
    dieu_pattern = r"[Đđ]i[eề]u\s*(\d+)"
    dieu_match = re.search(dieu_pattern, query, re.IGNORECASE)
    if dieu_match:
        structure["dieu"] = dieu_match.group(1)
    
    khoan_pattern = r"[Kk]ho[aả]n\s*(\d+)"
    khoan_match = re.search(khoan_pattern, query, re.IGNORECASE)
    if khoan_match:
        structure["khoan"] = khoan_match.group(1)
    
    diem_pattern = r"[Đđ]i[eể]m\s*([a-z]|[A-Z]|\d+)"
    diem_match = re.search(diem_pattern, query, re.IGNORECASE)
    if diem_match:
        structure["diem"] = diem_match.group(1).lower()
    
    muc_pattern = r"[Mm][uụ]c\s*(\d+)"
    muc_match = re.search(muc_pattern, query, re.IGNORECASE)
    if muc_match:
        structure["muc"] = muc_match.group(1)
    
    chuong_pattern = r"[Cc]h[ươ][ơư]ng\s*([IVXLCDM]+|\d+)"
    chuong_match = re.search(chuong_pattern, query, re.IGNORECASE)
    if chuong_match:
        structure["chuong"] = chuong_match.group(1)
    
    nghi_dinh_pattern = r"[Nn]gh[iị]\s*[đd][iị]nh\s*(\d+)"
    nghi_dinh_match = re.search(nghi_dinh_pattern, query, re.IGNORECASE)
    if nghi_dinh_match:
        structure["nghi_dinh"] = nghi_dinh_match.group(1)
    
    luat_pattern = r"[Ll]u[aậ]t\s+([^\d\s][^,.\n]*?)(?=\s*[,.\n]|$)"
    luat_match = re.search(luat_pattern, query, re.IGNORECASE)
    if luat_match:
        structure["luat"] = luat_match.group(1).strip()
    
    thong_tu_pattern = r"[Tt]h[ôơ]ng\s*t[ưư]\s*(\d+)"
    thong_tu_match = re.search(thong_tu_pattern, query, re.IGNORECASE)
    if thong_tu_match:
        structure["thong_tu"] = thong_tu_match.group(1)
    
    quyet_dinh_pattern = r"[Qq]uy[eế]t\s*[đd][iị]nh\s*(\d+)"
    quyet_dinh_match = re.search(quyet_dinh_pattern, query, re.IGNORECASE)
    if quyet_dinh_match:
        structure["quyet_dinh"] = quyet_dinh_match.group(1)
    
    return structure

# =============================================================
# ADAPTIVE ALPHA CHO HYBRID SEARCH (MỚI)
# =============================================================
def adaptive_alpha(query: str, structure: dict) -> float:
    """
    Tự động điều chỉnh alpha dựa trên độ cụ thể của query
    - Query có Điều + Luật cụ thể -> alpha cao (0.9) - ưu tiên BM25
    - Query chung chung -> alpha thấp (0.5) - cân bằng BM25 + Semantic
    """
    if "dieu" in structure:
        if "luat" in structure or "nghi_dinh" in structure:
            return 0.9  # Rất cụ thể
        return 0.8  # Cụ thể vừa
    elif "chuong" in structure or "muc" in structure:
        return 0.7
    else:
        return 0.5  # Không có cấu trúc rõ ràng

# =============================================================
# PHÁT HIỆN CÂU HỎI CÓ LIÊN QUAN ĐẾN PHÁP LUẬT
# =============================================================
def is_legal_question(query: str, client) -> bool:
    """Sử dụng Gemini để phân loại câu hỏi có liên quan đến pháp luật không"""
    try:
        classification_prompt = f"""Phân tích câu hỏi sau và trả lời ĐÚNG hoặc SAI:

Câu hỏi: "{query}"

Câu hỏi này có liên quan đến pháp luật Việt Nam không? (Bao gồm: luật, nghị định, thông tư, quy định pháp lý, thủ tục hành chính, quyền và nghĩa vụ công dân, vi phạm pháp luật, mức phạt, quy trình pháp lý...)

Chỉ trả lời một từ: ĐÚNG hoặc SAI"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=classification_prompt
        )
        
        result = response.text.strip().upper()
        return "ĐÚNG" in result or "TRUE" in result
        
    except Exception as e:
        st.warning(f"⚠️ Lỗi phân loại câu hỏi: {str(e)}")
        legal_keywords = [
            "luật", "nghị định", "thông tư", "quyết định", "điều", "khoản",
            "phạt", "vi phạm", "quy định", "pháp luật", "hợp đồng", "thủ tục",
            "quyền", "nghĩa vụ", "tòa án", "kiện", "trách nhiệm", "bồi thường"
        ]
        return any(keyword in query.lower() for keyword in legal_keywords)

# =============================================================
# LLM ĐÁNH GIÁ TÀI LIỆU CÓ ĐỦ THÔNG TIN KHÔNG
# =============================================================
def llm_evaluate_documents(client, query: str, documents: List[Dict]) -> dict:
    """
    Cho LLM đánh giá xem tài liệu có đủ thông tin để trả lời câu hỏi không
    """
    try:
        context = "\n\n".join([
            f"[Tài liệu {i+1}: {doc['metadata']}]\n{doc['content'][:5000]}" 
            for i, doc in enumerate(documents)
        ])
        
        evaluation_prompt = f"""Bạn là một luật sư chuyên nghiệp. Nhiệm vụ của bạn là đánh giá xem tài liệu pháp lý có **liên quan và hữu ích** để trả lời câu hỏi hay không.

CÂU HỎI: {query}

TÀI LIỆU PHÁP LÝ:
{context}

YÊU CẦU:

1. Đọc kỹ tài liệu và câu hỏi.Chú ý xem các yêu cầu thêm của người dùng như phân tích điều luật,..  
2. Đánh giá xem tài liệu có **liên quan hoặc chứa nội dung có thể giúp trả lời câu hỏi** hay không.  
   - Nếu tài liệu **có liên quan hoặc phần nào trả lời được**, coi như **đạt yêu cầu (true)**.  
   - Chỉ khi **tài liệu hoàn toàn không liên quan** đến câu hỏi thì mới coi là **false**.
   
3. Trả lời theo định dạng JSON sau (QUAN TRỌNG):

Nếu tài liệu CÓ LIÊN QUAN:
{{
  "sufficient": true,
  "answer": "<Sắp xếp và trình bày nội dung toàn bộ điều luật liên quan sao cho dễ nhìn, thêm các ký tự xuống dòng vào phần cuối các câu sao cho phù hợp>",
  "reason": ""
}}

Nếu tài liệu KHÔNG LIÊN QUAN:
{{
  "sufficient": false,
  "answer": "",
  "reason": "<giải thích ngắn gọn tại sao tài liệu không liên quan đến câu hỏi>"
}}

Ví dụ:

QUAN TRỌNG:
- Chỉ trả về JSON, không thêm bất kỳ text nào khác.  
- Không dùng markdown code block (```json).  
- In ra nội dung điều luật chính xác để người dùng xem, không bịa đặt .

"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=evaluation_prompt
        )
        
        response_text = response.text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        return result
        
    except json.JSONDecodeError as e:
        st.error(f"❌ Lỗi parse JSON: {str(e)}")
        return {
            "sufficient": False,
            "answer": "",
            "reason": "Lỗi phân tích phản hồi từ LLM"
        }
    except Exception as e:
        st.error(f"❌ Lỗi đánh giá tài liệu: {str(e)}")
        return {
            "sufficient": False,
            "answer": "",
            "reason": f"Lỗi hệ thống: {str(e)}"
        }


# =============================================================
# TRÍCH XUẤT NGUỒN TỪ GROUNDING METADATA
# =============================================================
def extract_web_sources(response) -> List[Dict[str, str]]:
    """Trích xuất các nguồn web từ grounding_metadata của Gemini response"""
    sources = []
    try:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata'):
                grounding_metadata = candidate.grounding_metadata
                
                if hasattr(grounding_metadata, 'grounding_chunks'):
                    for chunk in grounding_metadata.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append({
                                'title': chunk.web.title if hasattr(chunk.web, 'title') else 'Không có tiêu đề',
                                'url': chunk.web.uri if hasattr(chunk.web, 'uri') else ''
                            })
    except Exception as e:
        st.warning(f"⚠️ Không thể trích xuất nguồn: {str(e)}")
    
    return sources

# =============================================================
# TÌM KIẾM WEB BẰNG GEMINI
# =============================================================
def search_web_with_gemini(client, query: str) -> tuple:
    """Tìm kiếm thông tin trên web bằng Gemini với Google Search grounding"""
    try:
        search_prompt = f"""Bạn là chuyên gia pháp luật Việt Nam. Nhiệm vụ của bạn là trích xuất và cung cấp **toàn bộ nội dung pháp lý gốc** từ các văn bản (Luật, Nghị định, Thông tư...) có liên quan đến câu hỏi sau.

Câu hỏi: {query}

YÊU CẦU TRẢ LỜI:

1. **Trích dẫn đầy đủ nội dung pháp luật**:
   - Trả về nguyên văn nội dung của các điều, khoản, mục, chương trong Nghị định hoặc văn bản pháp luật có liên quan.
   - Nếu có nhiều điều liên quan, hãy cung cấp **toàn bộ nội dung các điều đó**.
   - Không rút gọn, không tóm tắt, không phân tích.

2 **QUAN TRỌNG**:
   - Không tự diễn giải, không giải thích, không thêm ý kiến cá nhân.
   - Chỉ sắp xếp lại, căn chỉnh xuống dòng sao cho dễ nhìn.
   - Chỉ dựa trên nội dung tài liệu được truy xuất.
   - Nếu không tìm thấy nội dung phù hợp, trả về thông báo:
     "Không tìm thấy nội dung nghị định hoặc văn bản pháp luật phù hợp với câu hỏi."
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=search_prompt,
            config={
                "tools": [{"google_search": {}}]
            }
        )
        
        web_sources = extract_web_sources(response)
        return response.text, web_sources
        
    except Exception as e:
        return f"❌ Lỗi tìm kiếm web: {str(e)}", []

# =============================================================
# TÌM KIẾM THEO NỘI DUNG (SEMANTIC SEARCH)
# =============================================================
def search_by_content(query, vectorstore_content, top_k=10):
    """Tìm kiếm semantic trên nội dung chunk"""
    try:
        results = vectorstore_content.similarity_search_with_score(query, k=top_k)
        return [{
            "metadata": doc.metadata.get("source", "Không xác định"),
            "content": doc.page_content,
            "source": "semantic_content_search",
            "score": float(score)
        } for doc, score in results]
    except Exception as e:
        st.warning(f"⚠️ Lỗi semantic search: {str(e)}")
        return []

# =============================================================
# HYBRID SEARCH: BM25 + SEMANTIC SEARCH (CẢI TIẾN)
# =============================================================
def hybrid_search(query, bm25, metadata_list, meta_mapping, vectorstore_content, 
                 alpha=None, top_k=10):
    """
    Kết hợp BM25 (metadata) và Semantic Search (content)
    Alpha được tự động điều chỉnh dựa trên cấu trúc query
    """
    # Tự động tính alpha nếu không được cung cấp
    if alpha is None:
        structure = extract_legal_structure(query)
        alpha = adaptive_alpha(query, structure)
        st.info(f"🎯 Auto Alpha: {alpha:.2f} (BM25: {alpha*100:.0f}%, Semantic: {(1-alpha)*100:.0f}%)")
    
    # 1. BM25 search trên metadata
    bm25_results = search_bm25_metadata(query, bm25, metadata_list, meta_mapping, top_k=top_k)
    
    # 2. Semantic search trên content
    semantic_results = search_by_content(query, vectorstore_content, top_k=top_k)
    
    # 3. Normalize scores về [0, 1]
    if bm25_results:
        max_bm25 = max(r['score'] for r in bm25_results)
        if max_bm25 > 0:
            for r in bm25_results:
                r['score_normalized'] = r['score'] / max_bm25
    
    if semantic_results:
        max_semantic = max(r['score'] for r in semantic_results)
        if max_semantic > 0:
            for r in semantic_results:
                r['score_normalized'] = r['score'] / max_semantic
    
    # 4. Kết hợp scores
    combined = {}
    
    for result in bm25_results:
        key = result['metadata']
        combined[key] = {
            **result,
            'final_score': alpha * result.get('score_normalized', 0)
        }
    
    for result in semantic_results:
        key = result['metadata']
        if key in combined:
            combined[key]['final_score'] += (1 - alpha) * result.get('score_normalized', 0)
        else:
            combined[key] = {
                **result,
                'final_score': (1 - alpha) * result.get('score_normalized', 0)
            }
    
    # 5. Sắp xếp theo final_score
    final_results = sorted(combined.values(), key=lambda x: x['final_score'], reverse=True)
    
    return final_results[:top_k]

# =============================================================
# TÌM KIẾM THÔNG MINH
# =============================================================
def smart_search_with_llm_eval(query, vectorstore_content, meta_mapping, bm25, 
                                metadata_list, client, top_k=10):
    """
    Tìm kiếm thông minh với adaptive alpha
    """
    
    # Bước 1: Kiểm tra có phải câu hỏi pháp luật không
    is_legal = is_legal_question(query, client)
    
    if not is_legal:
        return {
            "status": "non_legal",
            "results": [],
            "evaluation": None,
            "web_search_needed": False
        }
    
    # Bước 2: Chọn phương pháp tìm kiếm
    structure = extract_legal_structure(query)
    
    if structure:
        # Có cấu trúc → dùng BM25 hoặc Hybrid với alpha cao
        st.info(f"🔍 Phát hiện cấu trúc: {structure}")
        
        if "dieu" in structure:
            st.info("📌 Dùng Metadata Search (có Điều cụ thể)")
            results = search_bm25_metadata(query, bm25, metadata_list, meta_mapping, top_k=top_k)
        else:
            st.info("🔀 Dùng Hybrid Search")
            results = hybrid_search(query, bm25, metadata_list, meta_mapping, 
                                   vectorstore_content, alpha=None, top_k=top_k)
    else:
        # Không có cấu trúc → dùng Hybrid Search balanced
        st.info("🔍 Dùng Hybrid Search")
        results = hybrid_search(query, bm25, metadata_list, meta_mapping, 
                               vectorstore_content, alpha=None, top_k=top_k)
    
    # Nếu không tìm thấy gì
    if not results or len(results) == 0:
        st.warning("⚠️ Không tìm thấy tài liệu nào trong database")
        return {
            "status": "no_documents_found",
            "results": [],
            "evaluation": None,
            "web_search_needed": True
        }
    
    # Bước 3: LLM đánh giá tài liệu
    st.info("🤖 Đang đánh giá chất lượng tài liệu...")
    evaluation = llm_evaluate_documents(client, query, results)
    
    # Bước 4: Quyết định
    if evaluation["sufficient"]:
        return {
            "status": "sufficient",
            "results": results,
            "evaluation": evaluation,
            "web_search_needed": False
        }
    else:
        st.warning(f"⚠️ {evaluation['reason']}")
        return {
            "status": "insufficient",
            "results": results,
            "evaluation": evaluation,
            "web_search_needed": True
        }

# =============================================================
# CHAT VỚI GEMINI
# =============================================================
def chat_with_gemini(client, message):
    """Chat thông thường cho câu hỏi không liên quan pháp luật"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=message
        )
        return response.text
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

# =============================================================
# GIAO DIỆN STREAMLIT
# =============================================================
def main():
    st.set_page_config(
        page_title="Chatbot Luật Việt Nam",
        page_icon="⚖️",
        layout="wide"
    )
    
    st.title("⚖️ Chatbot Tư Vấn Luật Pháp Việt Nam")
    st.caption("Luật Việt Nam")
    
    # Khởi tạo
    client = init_gemini_client()
    vectorstore_content, vectorstore_meta, meta_mapping, embeddings, bm25, metadata_list = load_vector_stores()
    
    # Kiểm tra database
    if vectorstore_content is None or meta_mapping is None or bm25 is None:
        st.warning("⚠️ Chưa tải được database pháp luật. Bot sẽ hoạt động với web search.")
        legal_db_available = False
    else:
        st.success(f"✅ Database đã sẵn sàng! ({len(metadata_list)} metadata entries)")
        legal_db_available = True
    
    # Khởi tạo session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if "legal_results" in message and message["legal_results"]:
                with st.expander("📚 Tài liệu pháp lý từ Database"):
                    for i, result in enumerate(message["legal_results"], 1):
                        st.markdown(f"**{i}. {result['metadata']}**")
                        st.caption(f"🔍 Nguồn: {result['source']} | Score: {result.get('final_score', result.get('score', 0)):.3f}")
                        st.text(result['content'][:500] + "...")
                        st.divider()
            
            if "web_sources" in message and message["web_sources"]:
                with st.expander("🌐 Nguồn tham khảo từ Web"):
                    for i, source in enumerate(message["web_sources"], 1):
                        st.markdown(f"**{i}. [{source['title']}]({source['url']})**")
                        st.caption(f"🔗 {source['url']}")
                        st.divider()
    
    # Input
    if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Xử lý và trả lời
        with st.chat_message("assistant"):
            with st.spinner("Đang phân tích câu hỏi..."):
                
                if legal_db_available:
                    search_result = smart_search_with_llm_eval(
                        prompt, 
                        vectorstore_content,
                        meta_mapping,
                        bm25,
                        metadata_list,
                        client,
                        top_k=15
                    )
                    
                    if search_result["status"] == "non_legal":
                        response = chat_with_gemini(client, prompt)
                        st.markdown(response)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response
                        })
                    
                    elif search_result["status"] == "sufficient":
                        response = search_result["evaluation"]["answer"]
                        st.markdown(response)
                        
                        with st.expander("📚 Tài liệu pháp lý từ Database"):
                            for i, result in enumerate(search_result["results"], 1):
                                st.markdown(f"**{i}. {result['metadata']}**")
                                st.caption(f"🔍 {result['source']} | Score: {result.get('final_score', result.get('score', 0)):.3f}")
                                st.text(result['content'][:500] + "...")
                                st.divider()
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response,
                            "legal_results": search_result["results"]
                        })
                    
                    else:
                        st.info("🌐 Đang tìm kiếm thông tin bổ sung trên web...")
                        response_text, web_sources = search_web_with_gemini(client, prompt)
                        st.markdown(response_text)
                        
                        if web_sources:
                            with st.expander("🌐 Nguồn tham khảo từ Web", expanded=True):
                                for i, source in enumerate(web_sources, 1):
                                    st.markdown(f"**{i}. [{source['title']}]({source['url']})**")
                                    st.caption(f"🔗 {source['url']}")
                                    st.divider()
                        
                        if search_result["results"]:
                            with st.expander("📚 Tài liệu tham khảo từ Database (không đầy đủ)"):
                                for i, result in enumerate(search_result["results"], 1):
                                    st.markdown(f"**{i}. {result['metadata']}**")
                                    st.caption(f"🔍 {result['source']} | Score: {result.get('final_score', result.get('score', 0)):.3f}")
                                    st.text(result['content'][:500] + "...")
                                    st.divider()
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response_text,
                            "web_sources": web_sources,
                            "legal_results": search_result["results"]
                        })
                
                else:
                    # Không có database -> web search
                    is_legal = is_legal_question(prompt, client)
                    
                    if is_legal:
                        st.info("🌐 Đang tìm kiếm thông tin pháp luật trên web...")
                        response_text, web_sources = search_web_with_gemini(client, prompt)
                        st.markdown(response_text)
                        
                        if web_sources:
                            with st.expander("🌐 Nguồn tham khảo từ Web", expanded=True):
                                for i, source in enumerate(web_sources, 1):
                                    st.markdown(f"**{i}. [{source['title']}]({source['url']})**")
                                    st.caption(f"🔗 {source['url']}")
                                    st.divider()
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_text,
                            "web_sources": web_sources
                        })
                    else:
                        response = chat_with_gemini(client, prompt)
                        st.markdown(response)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response
                        })

if __name__ == "__main__":
    main()
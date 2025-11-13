import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# ⚙️ Nếu Tesseract chưa nằm trong PATH, chỉ định đường dẫn chính xác:
# pytesseract.pytesseract.tesseract_cmd = r"D:\SupportCode\tesseract.exe"

input_folder = r"TaiLieu_pdf"
output_folder = r"TaiLieu\ai_lieu_text"
os.makedirs(output_folder, exist_ok=True)

OCR_LANG = "vie"  # Chỉ OCR tiếng Việt

def extract_text_smart(pdf_path):
    """
    Trích xuất text thông minh:
    - đọc trực tiếp nếu có text
    - OCR nếu không
    Trả về: text đầy đủ, trạng thái từng trang, tổng số trang
    """
    text_all = []
    page_status = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            page_text = page.get_text("text").strip()
            if page_text:
                text_all.append(page_text)
                status = "Text"
            else:
                # Trang không có text → OCR
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(
                    img, lang=OCR_LANG, config="--psm 6 --oem 1"
                )
                text_all.append(f"[OCR - Trang {i+1}]\n{ocr_text.strip()}")
                status = "OCR"
            page_status.append(status)
    return "\n\n".join(text_all), page_status, len(doc)

def process_pdf(file_name):
    """Xử lý từng file PDF"""
    pdf_path = os.path.join(input_folder, file_name)
    base_name = os.path.splitext(file_name)[0]
    pdf_output_folder = os.path.join(output_folder, base_name)

    # Tạo thư mục con trước khi lưu file
    os.makedirs(pdf_output_folder, exist_ok=True)

    text, page_status, total_pages = extract_text_smart(pdf_path)

    # Lưu noi_dung.txt
    noi_dung_path = os.path.join(pdf_output_folder, "noi_dung.txt")
    with open(noi_dung_path, "w", encoding="utf-8") as f:
        f.write(text)

    # Lưu metadata.txt
    metadata_path = os.path.join(pdf_output_folder, "metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"Tên file gốc: {file_name}\n")
        f.write(f"Tổng số trang: {total_pages}\n")
        f.write("Trạng thái từng trang:\n")
        for i, status in enumerate(page_status, 1):
            f.write(f"  Trang {i}: {status}\n")

    # Trả log về tiến trình chính
    logs = [f"{file_name} - Trang {i+1}/{total_pages}: {status}" 
            for i, status in enumerate(page_status)]
    return file_name, logs

def main():
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    total_files = len(pdf_files)
    print(f"\nTổng số file PDF: {total_files}")

    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_pdf, f): f for f in pdf_files}

        for future in tqdm(as_completed(futures), total=total_files, desc="Xử lý file PDF"):
            try:
                file_name, logs = future.result()
                print(f"\n✅ Hoàn tất: {file_name}")
                for line in logs:
                    print(line)
            except Exception as e:
                print(f"Lỗi file {futures[future]}: {e}")

    print("\n🎯 Hoàn tất tất cả file PDF. Kết quả lưu trong thư mục 'ai_lieu_text'.")

if __name__ == "__main__":
    main()

import fitz  # PyMuPDF

pdf_path = r"TaiLieu_pdf\05-2nd.signed.pdf"
with fitz.open(pdf_path) as doc:
    for i, page in enumerate(doc):
        text = page.get_text("text")
        print(f"Trang {i+1}:", "Có text ✅" if text.strip() else "Không có text ⚠️")

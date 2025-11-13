from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import re

class PhapLuatScraper:
    def __init__(self, base_folder=r"D:\DemoJob\van_ban_nghi_dinh2"):
        self.base_folder = base_folder
        # Tạo thư mục gốc nếu chưa có
        if not os.path.exists(self.base_folder):
            os.makedirs(self.base_folder)
        
        # Cấu hình Chrome
        self.chrome_options = Options()
        # self.chrome_options.add_argument('--headless')  # nếu muốn chạy ngầm
        
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
    
    def sanitize_filename(self, name):
        """Làm sạch tên file/folder, loại bỏ ký tự đặc biệt và khoảng trắng lỗi"""
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = name.rstrip(' .,\u00A0')  # xóa khoảng trắng, dấu chấm, phẩy, non-breaking space cuối
        if len(name) > 200:
            name = name[:200]
        return name

    def remove_appendix(self, content):
        appendix_patterns = [
            r'PHỤ\s+LỤC\s*\n?\s*\(\s*[Kk]èm\s+theo',
            r'Phụ\s+lục\s*\n?\s*\(\s*[Kk]èm\s+theo',
            r'PHỤ\s+LỤC\s*\(\s*[Kk]èm\s+theo',
            r'Phụ\s+lục\s*\(\s*[Kk]èm\s+theo',
        ]
        min_position = len(content)
        found_pattern = None
        for pattern in appendix_patterns:
            matches = re.search(pattern, content, re.IGNORECASE)
            if matches:
                position = matches.start()
                if position < min_position:
                    min_position = position
                    found_pattern = pattern
        if found_pattern and min_position < len(content):
            content_before = content[:min_position].strip()
            removed_length = len(content) - min_position
            print(f"✂ Đã loại bỏ phần phụ lục cuối (cắt {removed_length} ký tự từ vị trí {min_position})")
            return content_before
        print("ℹ Không tìm thấy phụ lục dạng '(Kèm theo...)' - giữ nguyên nội dung")
        return content

    def search_nghi_dinh(self):
        print("Đang truy cập trang web...")
        self.driver.get("https://phapluat.gov.vn/van-ban-moi")
        time.sleep(3)
        print("Đang tìm kiếm 'nghị định'...")
        search_box = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
        )
        
        search_box.clear()
        search_box.send_keys("nghị định")
        search_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        search_btn.click()
        time.sleep(3)

    def get_document_links(self):
        print("Đang lấy danh sách văn bản...")
        links = []
        try:
            doc_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/vbpl/') and contains(@href, '?tab=2')]")
            print(f"Tìm thấy {len(doc_elements)} link văn bản")
            for elem in doc_elements:
                try:
                    href = elem.get_attribute('href')
                    title = elem.text.strip()
                    url = href.replace('?tab=2', '')
                    if url and title:
                        if not any(l['url'] == url for l in links):
                            links.append({'url': url, 'title': title})
                except:
                    continue
        except Exception as e:
            print(f"Lỗi khi lấy danh sách: {str(e)}")
        print(f"Tổng cộng tìm thấy {len(links)} văn bản duy nhất")
        return links

    def crawl_document_content(self, doc_url, doc_title):
        print(f"\n--- Đang xử lý: {doc_title[:80]}...")
        try:
            self.driver.get(doc_url)
            time.sleep(3)
            print("Đang crawl nội dung...")
            content_text = ""
            try:
                content_panel = self.driver.find_element(By.CSS_SELECTOR, "div.ant-tabs-tabpane-active")
                content_text = content_panel.text.strip()
            except:
                print("⚠ Không tìm thấy tab panel active")
            if len(content_text) < 100:
                print("⚠ Nội dung quá ngắn, thử lấy từ các nguồn khác...")
                content_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.rpv-core__text-layer, div.container, div[role='tabpanel']")
                for elem in content_elements:
                    text = elem.text.strip()
                    if len(text) > len(content_text):
                        content_text = text
            original_length = len(content_text)
            content_text = self.remove_appendix(content_text)
            if original_length > len(content_text):
                print(f"📊 Đã giảm từ {original_length} xuống {len(content_text)} ký tự")
            if content_text and len(content_text) > 50:
                folder_name = self.sanitize_filename(doc_title)[:100]
                folder_name = folder_name.strip()  # đảm bảo không còn ký tự thừa
                doc_folder = os.path.join(self.base_folder, folder_name)
                os.makedirs(doc_folder, exist_ok=True)
                content_file = os.path.join(doc_folder, "noi_dung.txt")
                with open(content_file, 'w', encoding='utf-8') as f:
                    f.write(f"TÊN VĂN BẢN: {doc_title}\n")
                    f.write(f"URL: {doc_url}\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(content_text)
                print(f"✓ Đã lưu {len(content_text)} ký tự vào: {folder_name[:50]}...")
                metadata_file = os.path.join(doc_folder, "metadata.txt")
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    f.write(f"Tên văn bản: {doc_title}\n")
                    f.write(f"URL: {doc_url}\n")
                    f.write(f"Thời gian crawl: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Số ký tự: {len(content_text)}\n")
                    f.write(f"Đã loại bỏ phụ lục: {'Có' if original_length > len(content_text) else 'Không'}\n")
                return True
            else:
                print("⚠ Không lấy được nội dung văn bản")
        except Exception as e:
            print(f"✗ Lỗi khi crawl: {str(e)}")
        return False

    def process_page(self, page_number=1):
        print(f"\n{'='*80}\nBẮT ĐẦU XỬ LÝ TRANG {page_number}\n{'='*80}\n")
        self.search_nghi_dinh()
        if page_number > 1:
            try:
                page_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[text()='{page_number}']")))
                page_link.click()
                time.sleep(3)
            except:
                print(f"⚠ Không thể chuyển đến trang {page_number}")
                return
        doc_links = self.get_document_links()
        success_count = 0
        for i, doc in enumerate(doc_links, 1):
            print(f"\n[{i}/{len(doc_links)}] ", end="")
            if self.crawl_document_content(doc['url'], doc['title']):
                success_count += 1
            print("Đang quay lại trang tìm kiếm...")
            self.driver.back()
            time.sleep(2)
            print("Trang đã load lại, đang tìm kiếm lại 'nghị định'...")
            self.search_nghi_dinh()
            if page_number > 1:
                try:
                    page_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[text()='{page_number}']")))
                    page_link.click()
                    time.sleep(3)
                except Exception as e:
                    print(f"⚠ Không thể chuyển lại đến trang {page_number}: {str(e)}")
        print(f"\n{'='*80}\nHOÀN THÀNH TRANG {page_number}: Đã crawl {success_count}/{len(doc_links)} văn bản\n{'='*80}\n")

    def close(self):
        print("\nĐang đóng trình duyệt...")
        self.driver.quit()
        print("Hoàn thành!")

if __name__ == "__main__":
    scraper = PhapLuatScraper()
    try:
        page_num = int(input("Nhập số trang cần crawl (ví dụ: 1, 2, 3...): "))
        scraper.process_page(page_num)
    except KeyboardInterrupt:
        print("\n\nĐã dừng bởi người dùng")
    except Exception as e:
        print(f"\n\nLỗi: {str(e)}")
    finally:
        scraper.close()

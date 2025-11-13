from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import re

class PhapLuatScraper:
    def __init__(self, base_folder=r"D:\DemoJob", page_number=1):
        # Tạo tên thư mục với số trang
        self.page_number = page_number
        folder_name = f"Luat_Bao_Ve_Moi_Truong_Trang_{page_number}"
        self.base_folder = os.path.join(base_folder, folder_name)
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=ngh%E1%BB%8B%20%C4%91%E1%BB%8Bnh"
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=Lu%E1%BA%ADt%20b%E1%BA%A3o%20v%E1%BB%87%20m%C3%B4i%20tr%C6%B0%E1%BB%9Dng%20"
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=Ngh%E1%BB%8B%20%C4%91%E1%BB%8Bnh%20s%E1%BB%91%2008%2F2022%2FN%C4%90-CP"
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=Ngh%E1%BB%8B%20%C4%91%E1%BB%8Bnh%2005%2F2025%2FN%C4%90-CP"
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=Th%C3%B4ng%20t%C6%B0%2002%2F2022%2FTT-BTNMT"
        # self.search_url = "https://phapluat.gov.vn/tim-kiem?q=Th%C3%B4ng%20t%C6%B0%2007%2F2025%2FTT-BTNMT"
        self.search_url = "https://phapluat.gov.vn/tim-kiem?q=LU%E1%BA%ACT%20B%E1%BA%A2O%20V%E1%BB%86%20M%C3%94I%20TR%C6%AF%E1%BB%9CNG"
        
        if not os.path.exists(self.base_folder):
            os.makedirs(self.base_folder)
            print(f"✓ Đã tạo thư mục: {self.base_folder}")
        
        self.chrome_options = Options()
        # self.chrome_options.add_argument('--headless')
        
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
    
    def sanitize_filename(self, name):
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = name.rstrip(' .,\u00A0')
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

    def goto_search_page_and_click_page(self, page_number):
        """Vào trang tìm kiếm và CLICK vào nút phân trang"""
        print(f"\n{'='*80}")
        print(f"Đang truy cập trang tìm kiếm...")
        self.driver.get(self.search_url)
        
        print("⏳ Đang đợi trang load hoàn toàn...")
        time.sleep(5)
        
        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'space-y-3')]"))
            )
            print("✓ Kết quả tìm kiếm đã xuất hiện")
        except:
            print("⚠ Timeout khi đợi kết quả tìm kiếm")
        
        print(f"📍 URL hiện tại: {self.driver.current_url}")
        
        if page_number > 1:
            try:
                print(f"⏳ Đang đợi nút phân trang xuất hiện...")
                
                try:
                    pagination_container = self.wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//div[contains(@class, 'flex') and contains(@class, 'items-center') and contains(@class, 'justify-center')]")
                        )
                    )
                    print("✓ Container phân trang đã xuất hiện")
                    time.sleep(2)
                except:
                    print("⚠ Không tìm thấy container phân trang")
                    return False
                
                print(f"🔍 Đang tìm nút trang {page_number}...")
                
                page_button = None
                max_retries = 3
                
                for attempt in range(max_retries):
                    try:
                        page_button = self.wait.until(
                            EC.element_to_be_clickable(
                                (By.XPATH, f"//button[contains(@class, 'px-3') and contains(@class, 'py-2') and normalize-space(text())='{page_number}']")
                            )
                        )
                        print(f"✓ Tìm thấy nút trang {page_number} (lần thử {attempt + 1})")
                        break
                    except:
                        if attempt < max_retries - 1:
                            print(f"⏳ Thử lại lần {attempt + 2}...")
                            time.sleep(2)
                        else:
                            print(f"⚠ Không tìm thấy nút trang {page_number} sau {max_retries} lần thử")
                            return False
                
                if page_button:
                    print(f"🖱 Đang click vào nút trang {page_number}...")
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", page_button)
                    time.sleep(1)
                    
                    self.driver.execute_script("arguments[0].click();", page_button)
                    
                    print("⏳ Đang đợi trang mới load...")
                    time.sleep(5)
                    
                    try:
                        self.wait.until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'space-y-3')]"))
                        )
                        print("✓ Kết quả trang mới đã xuất hiện")
                    except:
                        print("⚠ Timeout khi đợi kết quả trang mới")
                    
                    print(f"✓ Đã click vào trang {page_number}")
                    print(f"📍 URL sau khi click: {self.driver.current_url}")
                    return True
                    
            except Exception as e:
                print(f"❌ Lỗi khi chuyển trang: {str(e)}")
                return False
        
        print(f"✓ Đã ở trang {page_number}")
        return True

    def get_document_links(self):
        """Lấy danh sách link văn bản"""
        print("\n" + "="*80)
        print("Đang lấy danh sách văn bản...")
        
        time.sleep(3)
        
        links = []
        try:
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'space-y-3')]"))
                )
            except:
                print("⚠ Không tìm thấy container văn bản")
                return links
            
            doc_cards = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'space-y-3')]/div[contains(@class, 'block') and contains(@class, 'rounded-lg')]"
            )
            
            print(f"Tìm thấy {len(doc_cards)} card văn bản")
            
            for idx, card in enumerate(doc_cards, 1):
                try:
                    main_link = card.find_element(
                        By.XPATH,
                        ".//a[@class='block' and contains(@href, '/legal-documents/')]"
                    )
                    
                    href = main_link.get_attribute('href')
                    
                    try:
                        title_elem = main_link.find_element(By.TAG_NAME, 'h3')
                        title = title_elem.text.strip()
                    except:
                        title = main_link.text.strip()
                    
                    title = re.sub(r'\s+', ' ', title)
                    
                    if href and title:
                        full_url = href if href.startswith('http') else f"https://phapluat.gov.vn{href}"
                        
                        if not any(l['url'] == full_url for l in links):
                            links.append({'url': full_url, 'title': title})
                            print(f"  [{idx:02d}] ✓ {title[:70]}...")
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"❌ Lỗi khi lấy danh sách: {str(e)}")
        
        print(f"\n{'='*80}")
        print(f"Tổng cộng: {len(links)} văn bản duy nhất")
        print(f"{'='*80}\n")
        return links

    def crawl_document_content(self, doc_url, doc_title):
        """Crawl nội dung văn bản"""
        print(f"\n--- Đang xử lý: {doc_title[:80]}...")
        try:
            self.driver.get(doc_url)
            time.sleep(3)
            print("Đang crawl nội dung...")
            
            content_text = ""
            possible_selectors = [
                "div[role='tabpanel']",
                "div.rpv-core__text-layer",
                "div.document-content",
                "div.content-panel",
                "div.ant-tabs-tabpane-active"
            ]
            
            for selector in possible_selectors:
                try:
                    content_panel = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = content_panel.text.strip()
                    if len(text) > len(content_text):
                        content_text = text
                except:
                    continue
            
            if len(content_text) < 100:
                print("⚠ Nội dung quá ngắn, thử lấy từ toàn bộ body...")
                try:
                    body = self.driver.find_element(By.TAG_NAME, 'body')
                    content_text = body.text.strip()
                except:
                    pass
            
            original_length = len(content_text)
            content_text = self.remove_appendix(content_text)
            
            if original_length > len(content_text):
                print(f"📊 Đã giảm từ {original_length} xuống {len(content_text)} ký tự")
            
            if content_text and len(content_text) > 50:
                folder_name = self.sanitize_filename(doc_title)[:100]
                folder_name = folder_name.strip()
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

    def process_page(self):
        """Xử lý crawl trang đã được chỉ định khi khởi tạo"""
        print(f"\n{'='*80}")
        print(f"BẮT ĐẦU XỬ LÝ TRANG {self.page_number}")
        print(f"Thư mục lưu: {self.base_folder}")
        print(f"{'='*80}\n")
        
        if not self.goto_search_page_and_click_page(self.page_number):
            print("❌ Không thể chuyển đến trang, dừng lại")
            return
        
        doc_links = self.get_document_links()
        
        if not doc_links:
            print("⚠ Không tìm thấy văn bản nào")
            return
        
        success_count = 0
        
        for i, doc in enumerate(doc_links, 1):
            print(f"\n{'='*80}")
            print(f"[{i}/{len(doc_links)}] ", end="")
            
            if self.crawl_document_content(doc['url'], doc['title']):
                success_count += 1
            
            print(f"\n🔙 Đang quay lại trang {self.page_number}...")
            if not self.goto_search_page_and_click_page(self.page_number):
                print(f"⚠ Không thể quay lại trang {self.page_number}, tiếp tục với văn bản tiếp theo...")
        
        print(f"\n{'='*80}")
        print(f"HOÀN THÀNH TRANG {self.page_number}")
        print(f"Đã crawl thành công: {success_count}/{len(doc_links)} văn bản")
        print(f"{'='*80}\n")

    def close(self):
        print("\nĐang đóng trình duyệt...")
        self.driver.quit()
        print("Hoàn thành!")

if __name__ == "__main__":
    try:
        page_num = int(input("Nhập số trang cần crawl (ví dụ: 1, 2, 3...): "))
        scraper = PhapLuatScraper(page_number=page_num)
        scraper.process_page()
    except KeyboardInterrupt:
        print("\n\nĐã dừng bởi người dùng")
    except Exception as e:
        print(f"\n\nLỗi: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if 'scraper' in locals():
            scraper.close()
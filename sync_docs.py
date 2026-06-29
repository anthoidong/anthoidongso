import os
import hashlib
import glob
import google.generativeai as genai
from supabase import create_client, Client

# 1. Lấy thông tin bảo mật từ môi trường (GitHub Actions sẽ cung cấp)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") # Sử dụng khóa service_role

# Khởi tạo kết nối
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_file_hash(content):
    """Tạo mã băm MD5 để kiểm tra xem file có thay đổi không"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_embedding(text):
    """Gọi Gemini API để biến văn bản thành Vector"""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text
    )
    return result['embedding']

def chunk_text(text, max_chars=1000):
    """Cắt văn bản thành các đoạn nhỏ (chunk) dựa trên dấu xuống dòng"""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""
        current_chunk += p + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def main():
    print("Bắt đầu quá trình đồng bộ hóa...")
    
    # Lấy danh sách tất cả các file .md trong thư mục hiện tại và thư mục con
    md_files = glob.glob("**/*.md", recursive=True)
    
    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if not content.strip():
            continue
            
        current_hash = get_file_hash(content)
        
        # Kiểm tra xem file này đã có trên Supabase chưa và hash có khớp không
        # Lấy 1 bản ghi bất kỳ của file này để check hash
        response = supabase.table('documents').select('file_hash').eq('file_path', file_path).limit(1).execute()
        
        # Nếu đã có data và hash không đổi -> Bỏ qua để tiết kiệm API
        if len(response.data) > 0 and response.data[0]['file_hash'] == current_hash:
            print(f"Bỏ qua (Không có thay đổi): {file_path}")
            continue
            
        print(f"Đang xử lý và cập nhật: {file_path}")
        
        # Cắt nhỏ file
        chunks = chunk_text(content)
        
        for i, chunk_content in enumerate(chunks):
            # Tạo ID duy nhất cho từng chunk (vd: huong_dan.md_chunk_0)
            chunk_id = f"{file_path}_chunk_{i}"
            
            try:
                # Lấy vector từ Gemini
                vector = get_embedding(chunk_content)
                
                # Chuẩn bị dữ liệu để Upsert
                data = {
                    "id": chunk_id,
                    "file_path": file_path,
                    "content": chunk_content,
                    "file_hash": current_hash,
                    "embedding": vector
                }
                
                # Ghi đè hoặc thêm mới vào Supabase
                supabase.table('documents').upsert(data).execute()
                print(f"   + Đã lưu chunk {i}")
            except Exception as e:
                print(f"   ! Lỗi khi xử lý chunk {i} của file {file_path}: {e}")

    print("Hoàn tất đồng bộ!")

if __name__ == "__main__":
    main()

import os
import hashlib
import glob
from supabase import create_client, Client

# Kết nối Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_file_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def chunk_text(text, max_chars=1000):
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
    print("Bắt đầu đồng bộ văn bản lên Supabase...")
    md_files = glob.glob("**/*.md", recursive=True)
    
    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if not content.strip():
            continue
            
        current_hash = get_file_hash(content)
        response = supabase.table('documents').select('file_hash').eq('file_path', file_path).limit(1).execute()
        
        if len(response.data) > 0 and response.data[0]['file_hash'] == current_hash:
            print(f"Bỏ qua (Không đổi): {file_path}")
            continue
            
        print(f"Đang đẩy dữ liệu: {file_path}")
        chunks = chunk_text(content)
        
        for i, chunk_content in enumerate(chunks):
            chunk_id = f"{file_path}_chunk_{i}"
            data = {
                "id": chunk_id,
                "file_path": file_path,
                "content": chunk_content,
                "file_hash": current_hash,
                "embedding": None # Tài khoản doanh nghiệp chặn tạo vector -> Ta để trống cột này
            }
            supabase.table('documents').upsert(data).execute()
            print(f"   + Đã lưu chunk {i}")

    print("Hoàn tất đồng bộ!")

if __name__ == "__main__":
    main()

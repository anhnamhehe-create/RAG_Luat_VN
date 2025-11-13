from langchain_community.vectorstores import FAISS
from faiss import read_index
import os

index_path = "database2/faiss_legal_index/index.faiss"
print("Kích thước index hiện tại:", read_index(index_path).ntotal)

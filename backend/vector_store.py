import os
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer

INDEX_PATH = os.path.join(os.path.dirname(__file__), 'faiss_index.bin')
METADATA_PATH = os.path.join(os.path.dirname(__file__), 'faiss_metadata.pkl')

print("Loading embedding model...")
# Using a fast and small model suitable for CPU
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_dim = model.get_sentence_embedding_dimension()

def get_embedding(text: str) -> np.ndarray:
    return model.encode([text])[0]

class VectorStore:
    def __init__(self):
        self.index = None
        self.metadata = []
        self._load()

    def _load(self):
        if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            with open(METADATA_PATH, 'rb') as f:
                self.metadata = pickle.load(f)
            print(f"Loaded existing vector index with {len(self.metadata)} chunks.")
        else:
            self.index = faiss.IndexFlatIP(embedding_dim) # Cosine similarity friendly if normalized
            self.metadata = []
            print("Initialized new vector index.")

    def add_chunks(self, chunks_with_url: list):
        if not chunks_with_url:
            return
        
        texts = [c['text'] for c in chunks_with_url]
        embeddings = model.encode(texts)
        # Normalize for Inner Product to act like Cosine Similarity
        faiss.normalize_L2(embeddings)
        
        self.index.add(embeddings)
        self.metadata.extend(chunks_with_url)
        self.save()
        print(f"Added {len(chunks_with_url)} chunks to index.")

    def search(self, query: str, top_k: int = 5):
        if self.index is None or self.index.ntotal == 0:
            return []
            
        query_emb = model.encode([query])
        faiss.normalize_L2(query_emb)
        
        D, I = self.index.search(query_emb, top_k)
        
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx != -1:
                results.append({
                    'score': float(dist),
                    'text': self.metadata[idx]['text'],
                    'url': self.metadata[idx]['url']
                })
        return results

    def save(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(METADATA_PATH, 'wb') as f:
            pickle.dump(self.metadata, f)

    def clear(self):
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.metadata = []
        self.save()

# Singleton instance
vector_store = VectorStore()

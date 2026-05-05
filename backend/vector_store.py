import os
import pickle
import numpy as np
from google import genai
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), 'vector_db.pkl')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class VectorStore:
    def __init__(self):
        self.embeddings = None
        self.metadata = []
        self.client = None
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        self._load()

    def _load(self):
        if os.path.exists(DB_PATH):
            try:
                with open(DB_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.embeddings = data.get('embeddings')
                    self.metadata = data.get('metadata', [])
                print(f"Loaded existing vector db with {len(self.metadata)} chunks.")
            except Exception as e:
                print(f"Error loading DB: {e}. Starting fresh.")
                self.embeddings = None
                self.metadata = []
        else:
            self.embeddings = None
            self.metadata = []
            print("Initialized new vector db.")

    def _get_gemini_embeddings(self, texts: list[str]) -> np.ndarray:
        if not self.client:
            print("[VectorStore] No Gemini API key, cannot generate embeddings.")
            return np.zeros((len(texts), 768), dtype=np.float32)
        
        results = []
        for text in texts:
            try:
                resp = self.client.models.embed_content(
                    model='text-embedding-004',
                    contents=text
                )
                results.append(resp.embeddings[0].values)
            except Exception as e:
                print(f"[VectorStore] Embedding error: {e}")
                results.append([0.0]*768)
                
        return np.array(results, dtype=np.float32)

    def add_chunks(self, chunks_with_url: list):
        if not chunks_with_url:
            return
        
        texts = [c['text'] for c in chunks_with_url]
        new_embs = self._get_gemini_embeddings(texts)
        
        # Normalize
        norms = np.linalg.norm(new_embs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        new_embs = new_embs / norms
        
        if self.embeddings is None:
            self.embeddings = new_embs
        else:
            self.embeddings = np.vstack([self.embeddings, new_embs])
            
        self.metadata.extend(chunks_with_url)
        self.save()
        print(f"Added {len(chunks_with_url)} chunks to vector db.")

    def search(self, query: str, top_k: int = 5):
        if self.embeddings is None or len(self.embeddings) == 0:
            return []
            
        query_emb = self._get_gemini_embeddings([query])
        
        norm = np.linalg.norm(query_emb)
        if norm > 0:
            query_emb = query_emb / norm
            
        # Cosine similarity using dot product since vectors are normalized
        similarities = np.dot(self.embeddings, query_emb[0])
        
        # Get top_k indices
        k = min(top_k, len(self.metadata))
        top_indices = np.argsort(similarities)[-k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                'score': float(similarities[idx]),
                'text': self.metadata[idx]['text'],
                'url': self.metadata[idx]['url']
            })
        return results

    def save(self):
        with open(DB_PATH, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'metadata': self.metadata
            }, f)

    def clear(self):
        self.embeddings = None
        self.metadata = []
        self.save()

# Singleton instance
vector_store = VectorStore()

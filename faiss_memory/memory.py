import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import os
import pickle

class LongTermMemory:
    def __init__(self, persist_directory: str = "./memory_faiss"):
        """
        Inicializa a memória de longo prazo baseada em FAISS
        
        Args:
            persist_directory: Diretório onde os dados serão persistidos
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = self.embedding_model.get_sentence_embedding_dimension()

        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.metadatas = []
        self.ids = []

        self.index_file = os.path.join(self.persist_directory, "index.faiss")
        self.meta_file = os.path.join(self.persist_directory, "metadata.pkl")

        self._load_memory()

    def _generate_embedding(self, text: str) -> List[float]:
        embedding = self.embedding_model.encode(text)
        return embedding.tolist()

    def store_conversation(self, user_input: str, assistant_response: str, 
                           context: Optional[str] = None, metadata: Optional[Dict] = None):
        entry_id = str(uuid.uuid4())
        combined_text = f"Usuário: {user_input}\nAssistente: {assistant_response}"
        if context:
            combined_text = f"Contexto: {context}\n{combined_text}"

        embedding = np.array(self._generate_embedding(combined_text), dtype=np.float32)
        entry_metadata = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "assistant_response": assistant_response,
            "context": context or "",
            **(metadata or {})
        }

        self.index.add(np.expand_dims(embedding, axis=0))
        self.documents.append(combined_text)
        self.metadatas.append(entry_metadata)
        self.ids.append(entry_id)

        self._save_memory()
        return entry_id

    def retrieve_relevant_memory(self, query: str, n_results: int = 5, threshold: float = 0.0) -> List[Dict[str, Any]]:
        if not self.documents or not query.strip():
            return []

        query_embedding = np.array(self._generate_embedding(query), dtype=np.float32).reshape(1, -1)
        distances, indices = self.index.search(query_embedding, n_results)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            similarity = 1 - distances[0][i]
            if similarity >= threshold:
                results.append({
                    "similarity": similarity,
                    "document": self.documents[idx],
                    "metadata": self.metadatas[idx],
                    "id": self.ids[idx]
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    def get_conversation_context(self, query: str, max_context_length: int = 2000) -> str:
        memories = self.retrieve_relevant_memory(query, n_results=15, threshold=0.0)

        if not memories:
            return ""

        context_parts = []
        current_length = 0

        for memory in memories:
            memory_text = f"Conversa anterior:\n{memory['document']}\n"
            if current_length + len(memory_text) > max_context_length:
                break
            context_parts.append(memory_text)
            current_length += len(memory_text)

        return "\n".join(context_parts)

    def clear_memory(self):
        self.index.reset()
        self.documents.clear()
        self.metadatas.clear()
        self.ids.clear()
        self._save_memory()

    def get_memory_stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self.documents),
            "persist_directory": self.persist_directory
        }

    def _save_memory(self):
        faiss.write_index(self.index, self.index_file)
        with open(self.meta_file, 'wb') as f:
            pickle.dump({
                "documents": self.documents,
                "metadatas": self.metadatas,
                "ids": self.ids
            }, f)

    def _load_memory(self):
        if os.path.exists(self.index_file) and os.path.exists(self.meta_file):
            self.index = faiss.read_index(self.index_file)
            with open(self.meta_file, 'rb') as f:
                data = pickle.load(f)
                self.documents = data.get("documents", [])
                self.metadatas = data.get("metadatas", [])
                self.ids = data.get("ids", [])


long_term_memory = LongTermMemory() 
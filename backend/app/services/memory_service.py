import json
import logging
import os
from typing import Any

import numpy as np
from app.models import OrchestratorReport

logger = logging.getLogger(__name__)

class MemoryService:
    """Vector database for historical incidents using NumPy and Google Gemini Embeddings."""
    
    def __init__(self, api_key: str | None = None, db_path: str = "memory_db.json") -> None:
        self.api_key = api_key
        self.db_path = db_path
        self.embeddings: list[list[float]] = []
        self.records: list[dict[str, Any]] = []
        self._genai = None

        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._genai = genai
                logger.info("MemoryService: Gemini Embeddings API configured.")
            except Exception as exc:
                logger.warning("MemoryService: Failed to init Gemini Embeddings: %s", exc)

        self._load_db()

    def _load_db(self) -> None:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    data = json.load(f)
                    self.records = data.get("records", [])
                    self.embeddings = data.get("embeddings", [])
                logger.info("MemoryService: Loaded %d historical incidents.", len(self.records))
            except Exception as e:
                logger.error("Failed to load memory DB: %s", e)

    def _save_db(self) -> None:
        try:
            with open(self.db_path, "w") as f:
                json.dump({"records": self.records, "embeddings": self.embeddings}, f)
        except Exception as e:
            logger.error("Failed to save memory DB: %s", e)

    def _get_embedding(self, text: str) -> list[float] | None:
        if not self._genai:
            return None
        try:
            # Generate embedding using models/gemini-embedding-001
            result = self._genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document",
            )
            return result['embedding']
        except Exception as e:
            logger.error("Embedding generation failed: %s", e)
            return None

    def add_incident(self, report: OrchestratorReport) -> None:
        """Embed and store a synthesized report in the vector DB."""
        if not self._genai:
            return

        # Avoid duplicates
        if any(r['incident_id'] == report.incident_id for r in self.records):
            return

        text = f"Incident: {report.summary}. Root Cause: {report.root_cause_pod}. Explanation: {report.explanation}. Recommendations: {', '.join(r.action for r in report.recommendations)}"
        emb = self._get_embedding(text)
        if emb:
            self.records.append({
                "incident_id": report.incident_id,
                "text": text,
                "timestamp": report.generated_at.isoformat()
            })
            self.embeddings.append(emb)
            self._save_db()
            logger.info("MemoryService: Added incident %s to memory.", report.incident_id)

    def search_similar(self, query: str, top_k: int = 2) -> list[str]:
        """Perform cosine similarity search to find past similar incidents."""
        if not self._genai or not self.embeddings:
            return []

        query_emb = self._get_embedding(query)
        if not query_emb:
            return []

        # Cosine similarity using NumPy
        A = np.array(query_emb)
        B = np.array(self.embeddings)
        
        A_norm = np.linalg.norm(A)
        B_norm = np.linalg.norm(B, axis=1)
        
        if A_norm == 0 or np.any(B_norm == 0):
            return []

        similarities = np.dot(B, A) / (B_norm * A_norm)
        
        # Get top_k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            # Only include if similarity > 0.65 to ensure relevance
            if similarities[idx] > 0.65:
                results.append(self.records[idx]['text'])
                
        return results

import asyncio
import aiohttp
import json
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import os
from urllib.parse import quote
import random

from googleapiclient.discovery import build
import requests
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import chromadb
from chromadb.config import Settings

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    source: str
    relevance_score: float
    timestamp: datetime
    search_engine: str

@dataclass
class MedicalDocument:
    id: str
    content: str
    source_type: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, calls_per_minute: int = 30):  # Higher limit for local Ollama
        self.calls_per_minute = calls_per_minute
        self.call_times = []
        
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove calls older than 1 minute
        self.call_times = [t for t in self.call_times if now - t < 60]
        
        if len(self.call_times) >= self.calls_per_minute:
            oldest_call = self.call_times[0]
            wait_time = 60 - (now - oldest_call)
            if wait_time > 0:
                logger.debug(f"Rate limit reached. Waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time + 0.5)
        
        self.call_times.append(time.time())

class MedicalBERTEmbedder:
    """Medical BERT for semantic understanding of medical text"""
    
    def __init__(self, model_name: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"):
        self.model_name = model_name
        logger.info(f"Loading Medical BERT model: {model_name}")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.eval()
            
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
            
            logger.info(f"Medical BERT loaded on {self.device}")
        except Exception as e:
            logger.error(f"Error loading Medical BERT: {e}")
            # Fallback to simpler model
            self._load_fallback_model()
    
    def _load_fallback_model(self):
        """Load a smaller fallback model"""
        try:
            logger.info("Trying fallback model: sentence-transformers/all-MiniLM-L6-v2")
            from sentence_transformers import SentenceTransformer
            self.fallback_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.use_fallback = True
        except Exception as e:
            logger.error(f"Error loading fallback model: {e}")
            self.use_fallback = False
    
    def embed_text(self, text: str, max_length: int = 512) -> np.ndarray:
        try:
            if hasattr(self, 'use_fallback') and self.use_fallback:
                # Use sentence transformer fallback
                return self.fallback_model.encode(text)
            
            inputs = self.tokenizer(
                text,
                max_length=max_length,
                truncation=True,
                padding="max_length",
                return_tensors="pt"
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                last_hidden_state = outputs.last_hidden_state
                attention_mask = inputs['attention_mask']
                
                mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
                sum_embeddings = torch.sum(last_hidden_state * mask_expanded, 1)
                sum_mask = torch.clamp(mask_expanded.sum(1), min=1e-9)
                
                mean_embeddings = sum_embeddings / sum_mask
                embedding = mean_embeddings.cpu().numpy()[0]
                embedding = embedding / np.linalg.norm(embedding)
                
                return embedding
                
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            # Return random embedding as last resort
            return np.random.randn(768)

class MedicalVectorStore:
    """Vector store for medical documents using ChromaDB"""
    
    def __init__(self, persist_directory: str = "medical_vector_store"):
        self.persist_directory = persist_directory
        self.embedder = MedicalBERTEmbedder()
        
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            self.collection = self.client.get_or_create_collection(
                name="medical_documents",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"Medical Vector Store initialized at {persist_directory}")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            # Fallback to in-memory storage
            self._init_in_memory_store()
    
    def _init_in_memory_store(self):
        """Initialize in-memory storage as fallback"""
        self.documents = []
        self.embeddings = []
        logger.info("Using in-memory vector store (ChromaDB fallback)")
    
    def add_documents(self, documents: List[MedicalDocument]):
        if not documents:
            return
        
        try:
            if hasattr(self, 'collection'):
                # ChromaDB mode
                ids, embeddings, metadatas, docs_text = [], [], [], []
                
                for doc in documents:
                    embedding = doc.embedding if doc.embedding else self.embedder.embed_text(doc.content)
                    
                    metadata = {
                        "source_type": doc.source_type,
                        "content_length": len(doc.content),
                        **doc.metadata
                    }
                    
                    ids.append(doc.id)
                    embeddings.append(embedding.tolist())
                    metadatas.append(metadata)
                    docs_text.append(doc.content)
                
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=docs_text
                )
            else:
                # In-memory mode
                for doc in documents:
                    embedding = doc.embedding if doc.embedding else self.embedder.embed_text(doc.content)
                    self.documents.append({
                        'id': doc.id,
                        'content': doc.content,
                        'metadata': {**doc.metadata, 'source_type': doc.source_type},
                        'embedding': embedding
                    })
            
            logger.info(f"Added {len(documents)} documents to vector store")
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
    
    async def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            query_embedding = self.embedder.embed_text(query)
            
            if hasattr(self, 'collection'):
                # ChromaDB search
                results = self.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"]
                )
                
                formatted_results = []
                if results['documents']:
                    for i in range(len(results['documents'][0])):
                        formatted_results.append({
                            'content': results['documents'][0][i],
                            'metadata': results['metadatas'][0][i],
                            'similarity_score': 1 - results['distances'][0][i],
                            'id': results['ids'][0][i]
                        })
                
                return formatted_results
            else:
                # In-memory search
                similarities = []
                for doc in self.documents:
                    similarity = np.dot(query_embedding, doc['embedding']) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(doc['embedding'])
                    )
                    similarities.append((similarity, doc))
                
                # Sort by similarity
                similarities.sort(key=lambda x: x[0], reverse=True)
                
                formatted_results = []
                for similarity, doc in similarities[:top_k]:
                    formatted_results.append({
                        'content': doc['content'],
                        'metadata': doc['metadata'],
                        'similarity_score': float(similarity),
                        'id': doc['id']
                    })
                
                return formatted_results
                
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            if hasattr(self, 'collection'):
                count = self.collection.count()
            else:
                count = len(self.documents)
            
            return {
                "total_documents": count,
                "persist_directory": self.persist_directory,
                "embedding_model": self.embedder.model_name
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"total_documents": 0, "error": str(e)}

class GoogleCustomSearchEngine:
    """Google Custom Search Engine with better error handling"""
    
    def __init__(self, api_key: str, search_engine_id: str):
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        
        self.TRUSTED_MEDICAL_DOMAINS = [
            "mayoclinic.org",
            "nih.gov",
            "medlineplus.gov",
            "who.int",
            "cdc.gov",
            "webmd.com",
            "health.harvard.edu",
            "clevelandclinic.org",
            "medicalnewstoday.com"
        ]
        
        try:
            self.service = build("customsearch", "v1", developerKey=api_key)
            logger.info("Google Custom Search Engine initialized")
        except Exception as e:
            logger.error(f"Could not initialize Google CSE: {e}")
            self.service = None
    
    async def search_medical(self, query: str, num_results: int = 5) -> List[SearchResult]:
        if not self.service:
            logger.warning("Google CSE not available, returning empty results")
            return []
        
        search_results = []
        
        try:
            # Try domain-restricted search first
            domains_to_try = self.TRUSTED_MEDICAL_DOMAINS[:3]
            successful_search = False
            
            for domain in domains_to_try:
                if successful_search and len(search_results) >= num_results:
                    break
                    
                try:
                    search_query = f"{query} site:{domain}"
                    
                    def execute_search():
                        return self.service.cse().list(
                            q=search_query,
                            cx=self.search_engine_id,
                            num=min(3, num_results),
                            dateRestrict="y2"
                        ).execute()
                    
                    search_response = await asyncio.to_thread(execute_search)
                    
                    if "items" in search_response:
                        for item in search_response["items"]:
                            url = item.get("link", "")
                            if any(domain in url for domain in self.TRUSTED_MEDICAL_DOMAINS):
                                content = await self._fetch_page_content(url)
                                
                                if content and len(content) > 100:
                                    search_results.append(SearchResult(
                                        title=item.get("title", "Medical Information"),
                                        url=url,
                                        content=content[:1500],
                                        source=self._extract_domain(url),
                                        relevance_score=self._calculate_relevance_score(item, query),
                                        timestamp=datetime.now(),
                                        search_engine="Google_CSE"
                                    ))
                                    
                                    if len(search_results) >= num_results:
                                        successful_search = True
                                        break
                    
                    # Be polite to API
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error searching domain {domain}: {e}")
                    continue
            
            logger.info(f"Found {len(search_results)} medical search results")
            
        except Exception as e:
            logger.error(f"Error in Google Custom Search: {e}")
        
        return search_results
    
    async def _fetch_page_content(self, url: str) -> str:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            timeout = aiohttp.ClientTimeout(total=8)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        content = self._simple_extract_content(html)
                        return content[:2000]
                    
        except Exception as e:
            logger.debug(f"Could not fetch {url}: {e}")
        
        return ""
    
    def _simple_extract_content(self, html: str) -> str:
        """Simple content extraction"""
        try:
            import re
            html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
            html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
            
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            
            sentences = re.findall(r'[^.!?]*[.!?]', text)
            content = ' '.join(sentences[:20])
            
            return content.strip()
        except:
            return ""
    
    def _extract_domain(self, url: str) -> str:
        import re
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else ""
    
    def _calculate_relevance_score(self, search_item: Dict, query: str) -> float:
        score = 0.5
        
        query_lower = query.lower()
        title = search_item.get("title", "").lower()
        snippet = search_item.get("snippet", "").lower()
        
        if query_lower in title:
            score += 0.3
        if any(word in title for word in query_lower.split()[:3]):
            score += 0.1
        
        return min(score, 1.0)

class OllamaGenerator:
    """Ollama LLM generator for medical responses"""
    
    def __init__(self, model_name: str = "gemma:2b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.rate_limiter = RateLimiter(calls_per_minute=30)  # Higher for local
        self.available = False
        
        # Test connection to Ollama
        self._test_connection()
    
    def _test_connection(self):
        """Test if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                if self.model_name in model_names:
                    self.available = True
                    logger.info(f"Ollama connected. Using model: {self.model_name}")
                else:
                    logger.warning(f"Model {self.model_name} not found. Available models: {model_names}")
                    # Try to find a similar model
                    fallback_model = self._find_fallback_model(model_names)
                    if fallback_model:
                        self.model_name = fallback_model
                        self.available = True
                        logger.info(f"Using fallback model: {fallback_model}")
                    else:
                        logger.error("No suitable Ollama model found")
            else:
                logger.error(f"Ollama API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Cannot connect to Ollama: {e}. Make sure Ollama is running.")
    
    def _find_fallback_model(self, available_models: List[str]) -> Optional[str]:
        """Find a suitable fallback model"""
        # Prefer medical or general models
        preferred_order = [
            "medllama2", "llama2", "mistral", "mixtral", "codellama",
            "gemma", "llama3", "phi"
        ]
        
        for preferred in preferred_order:
            for model in available_models:
                if preferred in model.lower():
                    return model
        
        # Return any model if none preferred found
        return available_models[0] if available_models else None
    
    async def generate(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """Generate response using Ollama"""
        if not self.available:
            logger.warning("Ollama not available, using fallback response")
            return self._fallback_response(prompt)
        
        await self.rate_limiter.wait_if_needed()
        
        try:
            data = {
                "model": self.model_name,
                "prompt": prompt[:4000],  # Limit prompt size for local model
                "stream": False,
                "options": {
                    "num_predict": min(max_tokens, 2000),
                    "temperature": temperature,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                },
                "system": """You are a medical AI assistant providing accurate, evidence-based medical information. 
                Always include appropriate medical disclaimers. Cite sources when available.
                Be concise but comprehensive in your responses."""
            }
            
            timeout = aiohttp.ClientTimeout(total=60)  # Longer timeout for local model
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{self.base_url}/api/generate", json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_text = result.get("response", "").strip()
                        
                        # Clean up response
                        if response_text:
                            # Remove any trailing incomplete sentences
                            response_text = response_text.split('. ')[:-1]
                            response_text = '. '.join(response_text) + '.' if response_text else response_text
                        
                        return response_text or "No response generated."
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama API error {response.status}: {error_text}")
                        return self._fallback_response(prompt)
                        
        except asyncio.TimeoutError:
            logger.error("Ollama request timed out")
            return "Request timed out. Please try again with a simpler query."
        except Exception as e:
            logger.error(f"Error generating with Ollama: {e}")
            return self._fallback_response(prompt)
    
    def _fallback_response(self, prompt: str) -> str:
        """Generate a simple fallback response"""
        prompt_lower = prompt.lower()
        
        if any(term in prompt_lower for term in ['diabetes', 'blood sugar']):
            return """For diabetes management: Monitor blood glucose regularly, follow prescribed medication regimen, maintain a balanced diet with controlled carbohydrates, engage in regular physical activity, and attend regular medical check-ups. 

Important: Always consult with your healthcare provider for personalized diabetes management.

Medical disclaimer: This information is for educational purposes only and not a substitute for professional medical advice."""
        
        elif 'chest pain' in prompt_lower:
            return """Chest pain requires immediate medical evaluation. Possible causes include:

1. Cardiac: Angina, myocardial infarction, pericarditis
2. Pulmonary: Pulmonary embolism, pneumonia, pneumothorax
3. Gastrointestinal: GERD, esophageal spasm
4. Musculoskeletal: Costochondritis, muscle strain

URGENT: If chest pain is severe, crushing, radiating to arm/jaw, or accompanied by shortness of breath, nausea, or sweating, seek emergency medical attention immediately.

Medical disclaimer: This is general information. Chest pain requires professional medical evaluation."""
        
        elif any(term in prompt_lower for term in ['hypertension', 'high blood pressure']):
            return """Hypertension management typically involves:

1. Lifestyle modifications: DASH diet, reduced sodium intake, regular exercise, weight management, stress reduction, limited alcohol
2. Medications: ACE inhibitors, ARBs, beta-blockers, calcium channel blockers, diuretics based on individual patient factors
3. Regular monitoring of blood pressure

Target blood pressure is typically <130/80 mmHg for most adults, but individual targets may vary.

Medical disclaimer: Treatment should be guided by a healthcare professional based on individual assessment."""
        
        else:
            return """Based on available medical information, I recommend consulting with a healthcare professional for personalized medical advice.

For general health maintenance:
• Regular check-ups with your primary care provider
• Balanced nutrition and regular physical activity
• Adequate sleep and stress management
• Avoidance of tobacco and excessive alcohol

Medical disclaimer: This information is for educational purposes only and not medical advice. Always consult with a qualified healthcare provider for diagnosis and treatment."""

class MedicalSearchAgent:
    """Main Medical Search Agent using Ollama and Google Custom Search"""
    
    def __init__(self, google_api_key: str, google_cse_id: str, 
                 ollama_model: str = "gemma:2b", ollama_base_url: str = "http://localhost:11434"):
        
        # Initialize Ollama generator
        self.llm_generator = OllamaGenerator(
            model_name=ollama_model,
            base_url=ollama_base_url
        )
        
        # Initialize Google Custom Search
        self.google_searcher = GoogleCustomSearchEngine(google_api_key, google_cse_id)
        
        # Initialize Vector Store
        try:
            self.vector_store = MedicalVectorStore()
            self._load_medical_knowledge_base()
        except Exception as e:
            logger.error(f"Could not initialize vector store: {e}")
            self.vector_store = None
        
        logger.info("Medical Search Agent (Ollama + Google CSE) initialized")
    
    def _load_medical_knowledge_base(self):
        """Load comprehensive medical knowledge into vector store"""
        medical_docs = [
            MedicalDocument(
                id="diabetes_type2",
                content="""Type 2 Diabetes Mellitus: Chronic condition characterized by insulin resistance and relative insulin deficiency.
                
Clinical Features:
- Symptoms: Polyuria, polydipsia, polyphagia, fatigue, blurred vision
- Risk Factors: Obesity, family history, physical inactivity, age >45, hypertension
- Diagnostic Criteria: Fasting glucose ≥126 mg/dL, HbA1c ≥6.5%, random glucose ≥200 mg/dL with symptoms

Management:
1. Lifestyle: Medical nutrition therapy, regular exercise, weight loss
2. Medications: Metformin (first-line), SGLT2 inhibitors, GLP-1 RAs, DPP-4 inhibitors, insulin
3. Monitoring: HbA1c every 3-6 months, annual screening for complications

Complications: Retinopathy, nephropathy, neuropathy, cardiovascular disease, foot ulcers""",
                source_type="clinical_guidelines",
                metadata={"condition": "diabetes", "type": "type2", "year": 2023, "source": "ADA"}
            ),
            MedicalDocument(
                id="chest_pain_ddx",
                content="""Chest Pain Differential Diagnosis:

CARDIAC:
- Acute Coronary Syndrome (STEMI/NSTEMI): Crushing substernal pain, radiation to left arm/jaw
- Angina: Exertional chest pain relieved by rest/nitroglycerin
- Pericarditis: Sharp, pleuritic pain improved by sitting forward
- Aortic Dissection: Tearing pain radiating to back

PULMONARY:
- Pulmonary Embolism: Pleuritic pain with dyspnea, tachycardia
- Pneumonia: Fever, cough, pleuritic pain
- Pneumothorax: Acute onset with dyspnea

GASTROINTESTINAL:
- GERD: Burning retrosternal pain, acid regurgitation
- Esophageal Spasm: Squeezing chest pain
- Peptic Ulcer Disease: Epigastric pain

MUSCULOSKELETAL:
- Costochondritis: Reproducible chest wall tenderness
- Muscle Strain: Pain with movement

OTHER:
- Herpes Zoster: Dermatomal vesicular rash
- Panic Attack: Hyperventilation, palpitations

RED FLAGS: 
- Severe crushing pain
- Radiation to arm/jaw
- Associated dyspnea, diaphoresis, nausea
- Syncope or hypotension""",
                source_type="clinical_guidelines",
                metadata={"symptom": "chest_pain", "urgency": "high", "year": 2023}
            ),
            MedicalDocument(
                id="hypertension_management",
                content="""Hypertension Management Guidelines:

Classification:
- Normal: <120/<80 mmHg
- Elevated: 120-129/<80 mmHg
- Stage 1: 130-139/80-89 mmHg
- Stage 2: ≥140/≥90 mmHg

Lifestyle Modifications:
- DASH diet: Rich in fruits, vegetables, low-fat dairy
- Sodium restriction: <2.3 g/day (ideally <1.5 g/day)
- Weight loss: 5-10% of body weight
- Regular aerobic exercise: ≥150 min/week moderate intensity
- Moderate alcohol: ≤1 drink/day women, ≤2 drinks/day men
- Smoking cessation

Pharmacological Therapy:
First-line agents based on compelling indications:
- Thiazide diuretics: Chlorthalidone, HCTZ
- ACE inhibitors: Lisinopril, enalapril
- ARBs: Losartan, valsartan
- CCBs: Amlodipine, diltiazem
- Beta-blockers: Metoprolol, carvedilol

Treatment Goals:
- General: <130/80 mmHg
- Elderly: <130/80 mmHg if tolerated
- Diabetes/CKD: <130/80 mmHg

Monitoring: Home BP monitoring recommended""",
                source_type="clinical_guidelines",
                metadata={"condition": "hypertension", "guideline": "ACC/AHA", "year": 2022}
            ),
            MedicalDocument(
                id="medication_interactions",
                content="""Common Medication Interactions:

1. Warfarin interactions:
   - Potentiators: Antibiotics (Bactrim), antifungals (fluconazole), NSAIDs
   - Inhibitors: Vitamin K, barbiturates

2. Statin interactions:
   - Avoid with: Macrolide antibiotics, azole antifungals, cyclosporine
   - Increased risk of myopathy/rhabdomyolysis

3. Diabetes medications:
   - Sulfonylureas + beta-blockers: Masked hypoglycemia symptoms
   - Metformin + contrast dye: Risk of lactic acidosis

4. Antihypertensive interactions:
   - ACEi/ARBs + NSAIDs: Reduced antihypertensive effect, renal impairment
   - Beta-blockers + verapamil/diltiazem: Bradycardia, heart block

5. Psychotropic interactions:
   - SSRIs + MAOIs: Serotonin syndrome
   - Benzodiazepines + opioids: Respiratory depression""",
                source_type="pharmacology",
                metadata={"topic": "medication_interactions", "year": 2023}
            )
        ]
        
        if self.vector_store:
            self.vector_store.add_documents(medical_docs)
            logger.info(f"Loaded {len(medical_docs)} medical knowledge documents")
    
    async def search(self, query: str, diagnostic_context: Optional[Dict] = None) -> Dict[str, Any]:
        """Main search method"""
        logger.info(f"Medical search for: {query}")
        
        try:
            # Enrich query with diagnostic context
            enriched_query = self._enrich_query(query, diagnostic_context)
            
            # Execute searches in parallel
            search_tasks = []
            
            # Google search
            if self.google_searcher:
                search_tasks.append(
                    self.google_searcher.search_medical(enriched_query, num_results=3)
                )
            else:
                search_tasks.append(asyncio.sleep(0))
            
            # Semantic search
            if self.vector_store:
                search_tasks.append(
                    self.vector_store.semantic_search(enriched_query, top_k=3)
                )
            else:
                search_tasks.append(asyncio.sleep(0))
            
            # Execute with timeout
            try:
                google_results, semantic_results = await asyncio.wait_for(
                    asyncio.gather(*search_tasks, return_exceptions=True),
                    timeout=20
                )
                
                # Handle exceptions
                if isinstance(google_results, Exception):
                    logger.error(f"Google search failed: {google_results}")
                    google_results = []
                if isinstance(semantic_results, Exception):
                    logger.error(f"Semantic search failed: {semantic_results}")
                    semantic_results = []
                    
            except asyncio.TimeoutError:
                logger.warning("Search timeout")
                google_results, semantic_results = [], []
            
            # Generate response using Ollama
            response = await self._generate_medical_response(
                query, google_results, semantic_results, diagnostic_context
            )
            
            return self._format_result(query, response, google_results, semantic_results)
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return self._format_error_result(query, str(e))
    
    def _enrich_query(self, query: str, context: Optional[Dict]) -> str:
        """Enrich query with diagnostic context"""
        if not context:
            return query
        
        enriched = [query]
        
        # Add demographic information
        if context.get("patient_age"):
            age = context["patient_age"]
            enriched.append(f"age {age}")
            
            # Add age-specific context
            if age > 60:
                enriched.append("elderly")
            elif age < 18:
                enriched.append("pediatric")
        
        if context.get("patient_gender"):
            enriched.append(context["patient_gender"])
        
        # Add symptoms
        if context.get("symptoms"):
            symptoms = context["symptoms"]
            if isinstance(symptoms, list):
                enriched.extend(symptoms[:3])
        
        # Add medical history
        if context.get("medical_history"):
            enriched.append(context["medical_history"])
        
        # Add medications if available
        if context.get("medications"):
            medications = context["medications"]
            if isinstance(medications, list):
                enriched.append("medications")
                enriched.extend(medications[:2])
        
        return " ".join(enriched)
    
    async def _generate_medical_response(self, query: str, google_results: List, 
                                       semantic_results: List, context: Optional[Dict]) -> str:
        """Generate medical response using Ollama"""
        
        # Prepare context
        search_context = self._prepare_search_context(google_results, semantic_results)
        
        # Create comprehensive prompt
        prompt = self._create_medical_prompt(query, search_context, context)
        
        # Generate response
        response = await self.llm_generator.generate(prompt, max_tokens=800, temperature=0.2)
        
        return response
    
    def _prepare_search_context(self, google_results: List, semantic_results: List) -> str:
        """Prepare search context for LLM"""
        context_parts = []
        
        # Add real-time search results
        if google_results and len(google_results) > 0:
            context_parts.append("=== CURRENT MEDICAL INFORMATION FROM TRUSTED SOURCES ===")
            for i, result in enumerate(google_results[:3], 1):
                context_parts.append(f"\n[Source {i}: {result.source}]")
                context_parts.append(f"Title: {result.title}")
                context_parts.append(f"Content: {result.content[:400]}...")
        
        # Add medical knowledge base
        if semantic_results and len(semantic_results) > 0:
            context_parts.append("\n=== MEDICAL KNOWLEDGE BASE ===")
            for i, result in enumerate(semantic_results[:3], 1):
                source_info = result.get('metadata', {}).get('source', 'Medical Reference')
                context_parts.append(f"\n[Knowledge: {source_info}]")
                context_parts.append(f"{result['content'][:300]}...")
                context_parts.append(f"(Relevance: {result['similarity_score']:.2f})")
        
        return "\n".join(context_parts) if context_parts else "No specific search results found."
    
    def _create_medical_prompt(self, query: str, context: str, diag_context: Optional[Dict]) -> str:
        """Create medical prompt for Ollama"""
        
        patient_info = ""
        if diag_context:
            patient_info = "\nPatient Information:"
            if diag_context.get("patient_age"):
                patient_info += f"\n- Age: {diag_context['patient_age']}"
            if diag_context.get("patient_gender"):
                patient_info += f"\n- Gender: {diag_context['patient_gender']}"
            if diag_context.get("symptoms"):
                symptoms = diag_context["symptoms"]
                if isinstance(symptoms, list):
                    patient_info += f"\n- Symptoms: {', '.join(symptoms[:5])}"
            if diag_context.get("medical_history"):
                patient_info += f"\n- Medical History: {diag_context['medical_history']}"
        
        prompt = f"""ROLE: You are a medical AI assistant providing evidence-based medical information for diagnostic support.

QUERY: {query}
{patient_info}

SEARCH RESULTS:
{context[:2000]}

RESPONSE GUIDELINES:
1. Provide accurate, evidence-based information
2. Structure response with clear headings if helpful
3. Include key findings from search results
4. Note the reliability of sources (real-time vs. established knowledge)
5. Highlight any urgent concerns or red flags
6. Include appropriate medical disclaimers
7. Suggest next steps if appropriate
8. Keep response concise but comprehensive (500-800 words)

RESPONSE FORMAT:
- Start with a brief summary
- Present key information in organized sections
- End with medical disclaimer

BEGIN RESPONSE:"""
        
        return prompt
    
    def _format_result(self, query: str, response: str, 
                      google_results: List, semantic_results: List) -> Dict[str, Any]:
        """Format final result"""
        return {
            "query": query,
            "diagnostic_response": response,
            "search_results": {
                "google_cse_results": len(google_results) if isinstance(google_results, list) else 0,
                "semantic_results": len(semantic_results) if isinstance(semantic_results, list) else 0
            },
            "sources": self._extract_sources(google_results, semantic_results),
            "timestamp": datetime.now().isoformat(),
            "llm_model": self.llm_generator.model_name,
            "agent_type": "MedicalSearchAgent_Ollama",
            "status": "success"
        }
    
    def _extract_sources(self, google_results: List, semantic_results: List) -> List[str]:
        """Extract unique sources"""
        sources = set()
        
        if google_results:
            for result in google_results:
                if hasattr(result, 'source'):
                    sources.add(f"Web: {result.source}")
        
        if semantic_results:
            for result in semantic_results:
                metadata = result.get('metadata', {})
                if 'source' in metadata:
                    sources.add(f"Guideline: {metadata['source']}")
                elif 'condition' in metadata:
                    sources.add(f"Knowledge: {metadata['condition']}")
        
        return list(sources)[:10]
    
    def _format_error_result(self, query: str, error: str) -> Dict[str, Any]:
        """Format error result"""
        return {
            "query": query,
            "diagnostic_response": self.llm_generator._fallback_response(query),
            "error": error,
            "search_results": {"google_cse_results": 0, "semantic_results": 0},
            "timestamp": datetime.now().isoformat(),
            "agent_type": "MedicalSearchAgent_Ollama",
            "status": "error_with_fallback"
        }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information"""
        info = {
            "agent_name": "MedicalSearchAgent_Ollama",
            "llm_model": self.llm_generator.model_name,
            "llm_available": self.llm_generator.available,
            "search_engine": "Google CSE" if self.google_searcher and self.google_searcher.service else "Not available",
            "vector_store": "Available" if self.vector_store else "Not available",
            "medical_knowledge_docs": 4  # Our loaded documents
        }
        
        if self.vector_store:
            info["vector_store_stats"] = self.vector_store.get_collection_stats()
        
        return info

# Quick test function
async def test_ollama_connection():
    """Test if Ollama is running and models are available"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"\nOllama is running. Available models:")
            for model in models:
                print(f"  - {model.get('name')}")
            
            # Check for Gemma
            gemma_models = [m for m in models if 'gemma' in m.get('name', '').lower()]
            if gemma_models:
                print(f"\nGemma models available: {[m['name'] for m in gemma_models]}")
                print(f"\nRecommended: 'gemma:2b' (lightweight) or 'gemma:7b' (more capable)")
            else:
                print("\nNo Gemma models found. You can pull one with:")
                print("  ollama pull gemma:2b")
                print("  ollama pull gemma:7b")
            
            return True
        else:
            print(f"Ollama API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"Cannot connect to Ollama: {e}")
        print("\nMake sure Ollama is installed and running:")
        print("1. Install from https://ollama.com/")
        print("2. Start Ollama: 'ollama serve' (or run the Ollama app)")
        print("3. Pull a model: 'ollama pull gemma:2b'")
        return False

# Example usage
async def main():
    """Main function to test the agent"""
    
    # Load environment variables
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("Error: Google API key or CSE ID not found in environment variables")
        print("Please set GOOGLE_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID in .env file")
        return
    
    # Test Ollama connection
    print("\n" + "="*80)
    print("MEDICAL SEARCH AGENT - OLLAMA + GOOGLE CSE")
    print("="*80)
    
    ollama_running = await asyncio.to_thread(test_ollama_connection)
    if not ollama_running:
        print("\n⚠️  Ollama not running. The agent will use fallback responses.")
        print("   Start Ollama first for better medical responses.")
    
    # Initialize agent
    try:
        # Try Gemma 2B first, fallback to llama2 if not available
        ollama_model = "gemma:2b"
        
        search_agent = MedicalSearchAgent(
            google_api_key=GOOGLE_API_KEY,
            google_cse_id=GOOGLE_CSE_ID,
            ollama_model=ollama_model,
            ollama_base_url="http://localhost:11434"
        )
        
        # Test with diagnostic context
        diagnostic_context = {
            "patient_age": 45,
            "patient_gender": "male",
            "symptoms": ["chest pain", "shortness of breath", "fatigue"],
            "medical_history": "type 2 diabetes, hypertension",
            "medications": ["metformin", "lisinopril"]
        }
        
        query = "differential diagnosis for chest pain in diabetic patient with hypertension"
        
        print(f"\n{'='*80}")
        print("RUNNING MEDICAL SEARCH...")
        print(f"{'='*80}")
        print(f"Query: {query}")
        print(f"Model: {ollama_model}")
        
        # Perform search
        result = await search_agent.search(query, diagnostic_context)
        
        # Display results
        print(f"\n{'='*80}")
        print("DIAGNOSTIC RESPONSE:")
        print(f"{'='*80}")
        print(f"\n{result.get('diagnostic_response', 'No response')}")
        
        print(f"\n{'='*80}")
        print("SEARCH METRICS:")
        print(f"{'='*80}")
        print(f"Google CSE Results: {result.get('search_results', {}).get('google_cse_results', 0)}")
        print(f"Semantic Results: {result.get('search_results', {}).get('semantic_results', 0)}")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Sources: {', '.join(result.get('sources', []))}")
        
        # Save results
        with open('medical_search_ollama_output.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nOutput saved to: medical_search_ollama_output.json")
        
        # Display agent info
        agent_info = search_agent.get_agent_info()
        print(f"\n{'='*80}")
        print("AGENT CONFIGURATION:")
        print(f"{'='*80}")
        for key, value in agent_info.items():
            if key != "vector_store_stats":
                print(f"{key}: {value}")
        
    except Exception as e:
        logger.error(f"Failed to run agent: {e}")
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Check Google API keys in .env file")
        print("2. Ensure Ollama is running: 'ollama serve'")
        print("3. Pull Gemma model: 'ollama pull gemma:2b'")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
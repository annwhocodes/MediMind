import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from llm_wrapper import GroqGenerativeModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import PyPDF2
from pathlib import Path
import pickle
import requests
from googleapiclient.discovery import build
import re

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

@dataclass
class RAGResult:
    content: str
    source_file: str
    page_number: int
    relevance_score: float

class MedicalWebSearcher:
    """Handles web searching from trusted medical websites"""
    
    ALLOWED_SITES = [
        "medlineplus.gov", "mayoclinic.org", "fda.gov", "drugs.com",
        "webmd.com", "who.int", "ema.europa.eu", "nih.gov"
    ]
    
    def __init__(self, gemini_api_key: str, google_cse_id: str = None, google_api_key: str = None):
        self.gemini_api_key = gemini_api_key
        self.google_cse_id = google_cse_id
        self.google_api_key = google_api_key
        self.model = GroqGenerativeModel(api_key=gemini_api_key)
        self.session = None
        
        # Initialize Google Custom Search if credentials provided
        self.google_service = None
        if google_api_key and google_cse_id:
            try:
                self.google_service = build("customsearch", "v1", developerKey=google_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google Custom Search: {e}")
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'MediMind-AI-Bot/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_medical_sites(self, query: str, max_results: int = 8) -> List[SearchResult]:
        """Search across trusted medical websites using multiple methods"""
        results = []
        
        # Method 1: Try Google Custom Search if available
        if self.google_service and self.google_cse_id:
            try:
                google_results = await self._google_custom_search(query, max_results)
                results.extend(google_results)
            except Exception as e:
                logger.error(f"Google Custom Search error: {e}")
        
        # Method 2: Direct medical knowledge base search (fallback)
        if len(results) < max_results // 2:
            knowledge_results = await self._search_medical_knowledge_base(query)
            results.extend(knowledge_results)
        
        # Method 3: Try direct site searches for specific sites
        if len(results) < max_results:
            for site in self.ALLOWED_SITES[:3]:  # Try top 3 sites
                try:
                    site_results = await self._enhanced_site_search(query, site)
                    results.extend(site_results)
                    if len(results) >= max_results:
                        break
                except Exception as e:
                    logger.error(f"Error searching {site}: {e}")
                    continue
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:max_results]
    
    async def _google_custom_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Use Google Custom Search API to search medical sites"""
        results = []
    
        try:
            # Create site-restricted query
            site_query = f"{query} site:mayoclinic.org OR site:medlineplus.gov OR site:webmd.com OR site:nih.gov"
        
            # Execute search - Fix: Execute the request properly
            def execute_search():
                try:
                    request = self.google_service.cse().list(
                        q=site_query,
                        cx=self.google_cse_id,
                        num=max_results
                    )
                    return request.execute()
                except Exception as e:
                    logger.error(f"Google API execution error: {e}")
                    return {'items': []}
        
            search_result = await asyncio.to_thread(execute_search)
        
            items = search_result.get('items', [])
        
            for item in items:
                url = item.get('link', '')
                title = item.get('title', 'Medical Information')
                snippet = item.get('snippet', '')
            
            # Extract site from URL
                site = self._extract_site_from_url(url)
                if site in self.ALLOWED_SITES:
                    # Fetch full content
                    content = await self._fetch_page_content(url)
                    if content:
                        relevance_score = self._calculate_relevance(content + " " + snippet, query)
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            content=content[:2000],
                            source=site,
                            relevance_score=relevance_score,
                            timestamp=datetime.now()
                        ))
        
        except Exception as e:
            logger.error(f"Google Custom Search error: {e}")
    
        return results
    
    def _extract_site_from_url(self, url: str) -> str:
        """Extract site domain from URL"""
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    async def _search_medical_knowledge_base(self, query: str) -> List[SearchResult]:
        """Search using curated medical knowledge base (fallback method)"""
        # This is a comprehensive medical knowledge base for common queries
        medical_knowledge = {
            "diabetes": {
                "type 2 diabetes": {
                    "symptoms": "Increased thirst, frequent urination, increased hunger, unintended weight loss, fatigue, blurred vision, slow-healing sores, frequent infections",
                    "treatment": "Lifestyle changes (diet, exercise), medications (metformin, insulin), blood sugar monitoring, regular medical checkups",
                    "causes": "Insulin resistance, genetics, obesity, physical inactivity, age",
                    "prevention": "Healthy diet, regular exercise, weight management, avoiding tobacco"
                }
            },
            "hypertension": {
                "high blood pressure": {
                    "symptoms": "Often no symptoms (silent killer), but may include headaches, shortness of breath, nosebleeds",
                    "treatment": "Lifestyle changes, ACE inhibitors, beta-blockers, diuretics, calcium channel blockers",
                    "causes": "Age, genetics, obesity, high sodium intake, lack of exercise, stress",
                    "prevention": "Healthy diet (low sodium), regular exercise, weight management, stress reduction"
                }
            },
            "stroke": {
                "cerebrovascular accident": {
                    "symptoms": "FAST signs - Face drooping, Arm weakness, Speech difficulty, Time to call emergency",
                    "treatment": "Emergency medical care, clot-busting drugs, rehabilitation therapy",
                    "causes": "Blood clots, bleeding in brain, high blood pressure, atrial fibrillation",
                    "prevention": "Control blood pressure, manage diabetes, quit smoking, exercise regularly"
                }
            },
            "migraine": {
                "headache": {
                    "symptoms": "Severe headache, nausea, vomiting, sensitivity to light and sound, visual disturbances",
                    "treatment": "Pain relievers, triptans, preventive medications, lifestyle modifications",
                    "causes": "Genetics, hormonal changes, stress, certain foods, environmental factors",
                    "prevention": "Identify triggers, regular sleep, stress management, dietary changes"
                }
            }
        }
        
        results = []
        query_lower = query.lower()
        
        for condition, details in medical_knowledge.items():
            if condition in query_lower:
                for subtype, info in details.items():
                    if any(keyword in query_lower for keyword in [subtype, condition, "symptoms", "treatment", "causes", "prevention"]):
                        content = f"""
                        Medical Information about {subtype.title()}:
                        
                        Symptoms: {info['symptoms']}
                        
                        Treatment: {info['treatment']}
                        
                        Causes: {info['causes']}
                        
                        Prevention: {info['prevention']}
                        """
                        
                        results.append(SearchResult(
                            title=f"{subtype.title()} - Comprehensive Medical Information",
                            url=f"https://medlineplus.gov/search/{condition}",
                            content=content,
                            source="Medical Knowledge Base",
                            relevance_score=0.9,
                            timestamp=datetime.now()
                        ))
        
        return results
    
    async def _enhanced_site_search(self, query: str, site: str) -> List[SearchResult]:
        """Enhanced site-specific search with better URL patterns"""
        results = []
        
        # Site-specific search URLs that actually work
        search_urls = {
            "mayoclinic.org": f"https://www.mayoclinic.org/search/search-results?q={quote(query)}",
            "medlineplus.gov": f"https://medlineplus.gov/search/?query={quote(query)}",
            "webmd.com": f"https://www.webmd.com/search/search_results/default.aspx?query={quote(query)}",
            "nih.gov": f"https://search.nih.gov/search?utf8=%E2%9C%93&affiliate=nih&query={quote(query)}",
        }
        
        if site not in search_urls:
            return results
        
        try:
            async with self.session.get(search_urls[site], timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Site-specific parsing logic
                    if site == "mayoclinic.org":
                        links = soup.find_all('a', {'class': 'search-result-title'})[:3]
                    elif site == "medlineplus.gov":
                        links = soup.find_all('a', href=True)[:5]
                        links = [l for l in links if 'medlineplus.gov' in l.get('href', '')]
                    else:
                        links = soup.find_all('a', href=True)[:3]
                    
                    for link in links:
                        href = link.get('href', '')
                        if href and not href.startswith('http'):
                            href = f"https://{site}{href}"
                        
                        if href and site in href:
                            title = link.get_text(strip=True) or f"Medical Information from {site}"
                            content = await self._fetch_page_content(href)
                            
                            if content and len(content) > 100:
                                relevance_score = self._calculate_relevance(content, query)
                                results.append(SearchResult(
                                    title=title[:200],
                                    url=href,
                                    content=content[:1500],
                                    source=site,
                                    relevance_score=relevance_score,
                                    timestamp=datetime.now()
                                ))
                                
        except Exception as e:
            logger.error(f"Enhanced site search error for {site}: {e}")
        
        return results
    
    def _build_search_url(self, query: str, site: str) -> str:
        """Build search URL for different medical sites"""
        encoded_query = quote(query)
        
        search_patterns = {
            "medlineplus.gov": f"https://medlineplus.gov/search/?query={encoded_query}",
            "mayoclinic.org": f"https://www.mayoclinic.org/search/search-results?q={encoded_query}",
            "webmd.com": f"https://www.webmd.com/search/search_results/default.aspx?query={encoded_query}",
            "who.int": f"https://www.who.int/search?query={encoded_query}",
            "nih.gov": f"https://www.nih.gov/search/{encoded_query}",
            "fda.gov": f"https://www.fda.gov/search/?s={encoded_query}",
            "drugs.com": f"https://www.drugs.com/search.php?searchterm={encoded_query}",
            "ema.europa.eu": f"https://www.ema.europa.eu/en/search?search_term={encoded_query}"
        }
        
        return search_patterns.get(site, f"https://www.google.com/search?q=site:{site} {encoded_query}")
    
    async def _parse_search_results(self, html: str, site: str, query: str) -> List[SearchResult]:
        """Parse search results from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        try:
            # Generic approach for parsing search results
            # This would need to be customized for each site's HTML structure
            links = soup.find_all('a', href=True)[:5]  # Top 5 results per site
            
            for link in links:
                if self._is_valid_result_link(link, site):
                    url = urljoin(f"https://{site}", link['href'])
                    title = link.get_text(strip=True) or "Medical Information"
                    
                    # Fetch content from the page
                    content = await self._fetch_page_content(url)
                    if content:
                        relevance_score = self._calculate_relevance(content, query)
                        results.append(SearchResult(
                            title=title[:200],
                            url=url,
                            content=content[:2000],  # Limit content length
                            source=site,
                            relevance_score=relevance_score,
                            timestamp=datetime.now()
                        ))
                        
        except Exception as e:
            logger.error(f"Error parsing results from {site}: {e}")
        
        return results
    
    def _is_valid_result_link(self, link, site: str) -> bool:
        """Check if link is a valid medical content link"""
        href = link.get('href', '')
        text = link.get_text(strip=True).lower()
        
        # Skip navigation, search, and non-content links
        skip_patterns = ['search', 'login', 'contact', 'about', 'privacy', 'terms']
        return not any(pattern in href.lower() or pattern in text for pattern in skip_patterns)
    
    async def _fetch_page_content(self, url: str) -> str:
        """Fetch and extract text content from a webpage with better error handling"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with self.session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove unwanted elements
                    for element in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
                        element.decompose()
                    
                    # Look for main content in common containers
                    content_selectors = [
                        'main', 'article', '.content', '.main-content', 
                        '.article-content', '.post-content', '#content',
                        '.entry-content', '.page-content'
                    ]
                    
                    content = ""
                    for selector in content_selectors:
                        main_content = soup.select_one(selector)
                        if main_content:
                            content = main_content.get_text(separator=' ', strip=True)
                            break
                    
                    # Fallback to body content
                    if not content or len(content) < 100:
                        body = soup.find('body')
                        if body:
                            content = body.get_text(separator=' ', strip=True)
                    
                    # Clean up content
                    content = re.sub(r'\s+', ' ', content)  # Remove extra whitespace
                    content = re.sub(r'\n+', '\n', content)  # Remove extra newlines
                    
                    return content[:3000]  # Limit content length
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
        
        return ""
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """Calculate relevance score based on query terms in content with better scoring"""
        if not content or not query:
            return 0.0
            
        content_lower = content.lower()
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        score = 0.0
        content_length = len(content_lower)
        
        # Exact phrase matching gets highest score
        if query_lower in content_lower:
            score += 0.5
        
        # Individual term matching
        for term in query_terms:
            if len(term) > 2:  # Skip very short terms
                count = content_lower.count(term)
                if count > 0:
                    # Term frequency score
                    tf_score = min(count * 0.1, 0.3)
                    score += tf_score
                    
                    # Position bonus (terms appearing early get higher score)
                    first_occurrence = content_lower.find(term)
                    if first_occurrence < content_length * 0.3:  # First 30% of content
                        score += 0.1
        
        # Normalize score
        return min(score, 1.0)
    
    async def generate_response(self, query: str, search_results: List[SearchResult]) -> str:
        """Generate AI response using Gemini with search results"""
        context = self._format_search_context(search_results)
        
        prompt = f"""
        As a medical AI assistant, provide a comprehensive and accurate response to the following medical question using the provided search results from trusted medical sources.

        Question: {query}

        Search Results from Trusted Medical Sources:
        {context}

        Instructions:
        1. Provide accurate, evidence-based medical information
        2. Cite the sources you use in your response
        3. Include relevant disclaimers about consulting healthcare professionals
        4. Structure your response clearly with proper headings if needed
        5. Be comprehensive but concise
        6. If the search results don't contain sufficient information, state this clearly

        Response:
        """
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again later."
    
    def _format_search_context(self, results: List[SearchResult]) -> str:
        """Format search results for AI context"""
        context = ""
        for i, result in enumerate(results, 1):
            context += f"""
            Source {i}: {result.source}
            Title: {result.title}
            URL: {result.url}
            Content: {result.content[:1000]}...
            
            """
        return context

class MedicalRAGSystem:
    """RAG system for medical papers using FAISS vector storage"""
    
    def __init__(self, gemini_api_key: str, vector_store_path: str = "medical_vectors.faiss"):
        self.gemini_api_key = gemini_api_key
        self.model = GroqGenerativeModel(api_key=gemini_api_key)
        
        # Initialize sentence transformer for embeddings
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Vector store paths
        self.vector_store_path = vector_store_path
        self.metadata_path = vector_store_path.replace('.faiss', '_metadata.pkl')
        
        # Load or initialize vector store
        self.index = None
        self.documents = []
        self.metadata = []
        self._load_or_create_vector_store()
    
    def _load_or_create_vector_store(self):
        """Load existing vector store or create new one"""
        if os.path.exists(self.vector_store_path) and os.path.exists(self.metadata_path):
            self._load_vector_store()
        else:
            self._create_empty_vector_store()
    
    def _load_vector_store(self):
        """Load existing FAISS index and metadata"""
        try:
            self.index = faiss.read_index(self.vector_store_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
            logger.info(f"Loaded vector store with {len(self.metadata)} documents")
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            self._create_empty_vector_store()
    
    def _create_empty_vector_store(self):
        """Create new empty FAISS index"""
        dimension = 384  # all-MiniLM-L6-v2 embedding dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for similarity
        self.metadata = []
        logger.info("Created new empty vector store")
    
    def add_pdf_documents(self, pdf_directory: str):
        """Add PDF documents to the vector store"""
        pdf_files = Path(pdf_directory).glob("*.pdf")
        
        for pdf_file in pdf_files:
            try:
                self._process_pdf(pdf_file)
            except Exception as e:
                logger.error(f"Error processing {pdf_file}: {e}")
        
        self._save_vector_store()
    
    def _process_pdf(self, pdf_path: Path):
        """Extract text from PDF and add to vector store"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if len(text.strip()) > 100:  # Only process pages with substantial text
                        # Split into chunks for better retrieval
                        chunks = self._split_text_into_chunks(text)
                        
                        for chunk_idx, chunk in enumerate(chunks):
                            # Generate embedding
                            embedding = self.encoder.encode([chunk])
                            
                            # Add to FAISS index
                            self.index.add(embedding.astype('float32'))
                            
                            # Add metadata
                            self.metadata.append({
                                'source_file': pdf_path.name,
                                'page_number': page_num + 1,
                                'chunk_index': chunk_idx,
                                'content': chunk,
                                'doc_id': f"{pdf_path.stem}_p{page_num+1}_c{chunk_idx}"
                            })
                
                logger.info(f"Processed {pdf_path.name}: {len(pdf_reader.pages)} pages")
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
    
    def _split_text_into_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk.strip()) > 50:  # Only add substantial chunks
                chunks.append(chunk)
        
        return chunks
    
    def _save_vector_store(self):
        """Save FAISS index and metadata"""
        try:
            faiss.write_index(self.index, self.vector_store_path)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            logger.info(f"Saved vector store with {len(self.metadata)} documents")
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
    
    async def search_similar_documents(self, query: str, top_k: int = 5) -> List[RAGResult]:
        """Search for similar documents using vector similarity"""
        if not self.metadata:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.encoder.encode([query]).astype('float32')
            
            # Search FAISS index
            scores, indices = self.index.search(query_embedding, min(top_k, len(self.metadata)))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.metadata):
                    doc = self.metadata[idx]
                    results.append(RAGResult(
                        content=doc['content'],
                        source_file=doc['source_file'],
                        page_number=doc['page_number'],
                        relevance_score=float(score)
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    async def generate_rag_response(self, query: str, rag_results: List[RAGResult]) -> str:
        """Generate response using RAG results"""
        context = self._format_rag_context(rag_results)
        
        prompt = f"""
        As a medical AI assistant, provide a comprehensive response to the following medical question using the provided research paper excerpts and medical literature.

        Question: {query}

        Relevant Medical Literature and Research:
        {context}

        Instructions:
        1. Base your response on the provided medical literature
        2. Cite the specific sources and page numbers when possible
        3. Provide evidence-based medical information
        4. Include appropriate medical disclaimers
        5. If the literature doesn't contain sufficient information, state this clearly
        6. Structure your response with clear headings if needed

        Response:
        """
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again later."
    
    def _format_rag_context(self, results: List[RAGResult]) -> str:
        """Format RAG results for AI context"""
        context = ""
        for i, result in enumerate(results, 1):
            context += f"""
            Document {i}: {result.source_file} (Page {result.page_number})
            Relevance Score: {result.relevance_score:.3f}
            Content: {result.content}
            
            """
        return context

class MedicalSearchAgent:
    """Main search agent that combines web search and RAG"""
    
    def __init__(self, gemini_api_key: str, pdf_directory: str = "medical_papers", 
                 google_api_key: str = None, google_cse_id: str = None):
        self.rag_system = MedicalRAGSystem(gemini_api_key)
        self.gemini_api_key = gemini_api_key
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id
        
        # Initialize RAG system with PDFs if directory exists
        if os.path.exists(pdf_directory):
            self.rag_system.add_pdf_documents(pdf_directory)
    
    async def search_and_respond(self, query: str) -> Dict[str, Any]:
        """Main search function that combines web search and RAG"""
        # Perform both searches concurrently
        async with MedicalWebSearcher(
            self.gemini_api_key, 
            self.google_cse_id, 
            self.google_api_key
        ) as web_searcher:
            web_task = asyncio.create_task(web_searcher.search_medical_sites(query))
            rag_task = asyncio.create_task(self.rag_system.search_similar_documents(query))
            
            web_results, rag_results = await asyncio.gather(web_task, rag_task, return_exceptions=True)
            
            # Handle exceptions
            if isinstance(web_results, Exception):
                logger.error(f"Web search error: {web_results}")
                web_results = []
            
            if isinstance(rag_results, Exception):
                logger.error(f"RAG search error: {rag_results}")
                rag_results = []
            
            # Generate responses
            responses = {}
            
            if web_results:
                web_response = await web_searcher.generate_response(query, web_results)
                responses['web_response'] = web_response
            
            if rag_results:
                rag_response = await self.rag_system.generate_rag_response(query, rag_results)
                responses['rag_response'] = rag_response
            
            # Combine responses
            final_response = await self._combine_responses(query, responses, web_results, rag_results)
            
            return {
                'query': query,
                'final_response': final_response,
                'web_results': [self._serialize_search_result(r) for r in web_results] if web_results else [],
                'rag_results': [self._serialize_rag_result(r) for r in rag_results] if rag_results else [],
                'timestamp': datetime.now().isoformat()
            }
    
    async def _combine_responses(self, query: str, responses: Dict[str, str], 
                               web_results: List[SearchResult], rag_results: List[RAGResult]) -> str:
        """Combine web and RAG responses into a final answer"""
        if not responses:
            return "I apologize, but I couldn't find relevant information to answer your question. Please try rephrasing your query or consult with a healthcare professional."
        
        # If we have both responses, combine them intelligently
        if len(responses) > 1:
            model = GroqGenerativeModel(api_key=self.gemini_api_key)
            
            combine_prompt = f"""
            You have two sources of medical information for the question: "{query}"
            
            Web Sources Response:
            {responses.get('web_response', 'No web information available')}
            
            Medical Literature Response:
            {responses.get('rag_response', 'No literature information available')}
            
            Please combine these responses into a single, comprehensive, and well-structured answer that:
            1. Synthesizes information from both sources
            2. Maintains medical accuracy
            3. Cites sources appropriately
            4. Includes necessary medical disclaimers
            5. Provides a clear, helpful response to the original question
            
            Combined Response:
            """
            
            try:
                response = await asyncio.to_thread(model.generate_content, combine_prompt)
                return response.text
            except Exception as e:
                logger.error(f"Error combining responses: {e}")
                # Fallback to first available response
                return list(responses.values())[0]
        else:
            return list(responses.values())[0]
    
    def _serialize_search_result(self, result: SearchResult) -> Dict[str, Any]:
        """Convert SearchResult to dictionary"""
        return {
            'title': result.title,
            'url': result.url,
            'content': result.content[:500],  # Limit for JSON response
            'source': result.source,
            'relevance_score': result.relevance_score,
            'timestamp': result.timestamp.isoformat()
        }
    
    def _serialize_rag_result(self, result: RAGResult) -> Dict[str, Any]:
        """Convert RAGResult to dictionary"""
        return {
            'content': result.content[:500],  # Limit for JSON response
            'source_file': result.source_file,
            'page_number': result.page_number,
            'relevance_score': result.relevance_score
        }

# Example usage and testing
async def main():
    """Example usage of the Medical Search Agent"""
    # Initialize with your Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    agent = MedicalSearchAgent(GEMINI_API_KEY)
    
    # Test query
    query = "What are the symptoms and treatment options for type 2 diabetes?"
    
    result = await agent.search_and_respond(query)
    
    # Save results to JSON file
    with open('medical_search_results.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print("Search completed. Results saved to medical_search_results.json")
    print("\nFinal Response:")
    print(result['final_response'])

if __name__ == "__main__":
    asyncio.run(main())
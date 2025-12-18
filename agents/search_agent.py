import os
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from dataclasses import dataclass
import random

# Imports for LLM and Google Search
try:
    from groq import Groq, AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from googleapiclient.discovery import build

# Imports for RAG (ChromaDB)
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedicalSearchAgent:
    """
    Medical Search Agent using Groq (LLM), Google Custom Search, and ChromaDB (RAG).
    Generates structured diagnostic reports based on patient data.
    """
    
    def __init__(self, google_api_key: str, google_cse_id: str, groq_api_key: str = None):
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        
        # Initialize Groq Client
        self.groq_client = None
        if GROQ_AVAILABLE and self.groq_api_key:
            try:
                self.groq_client = AsyncGroq(api_key=self.groq_api_key)
                logger.info("✅ Groq Client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Groq Client: {e}")
        else:
            logger.warning("⚠️ Groq Client not available (Missing Key or Library)")

        # Initialize Google Search Service
        self.google_service = None
        if self.google_api_key and self.google_cse_id:
            try:
                self.google_service = build("customsearch", "v1", developerKey=self.google_api_key)
                logger.info("✅ Google Custom Search Service initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Google Search: {e}")

        # Initialize ChromaDB (RAG)
        self.chroma_client = None
        self.collection = None
        if CHROMA_AVAILABLE:
            try:
                db_path = os.path.join(os.path.dirname(__file__), "medical_vector_store")
                self.chroma_client = chromadb.PersistentClient(path=db_path)
                # Try to get existing collection or create/get generic one
                try:
                    self.collection = self.chroma_client.get_collection("medical_knowledge")
                    logger.info("✅ ChromaDB 'medical_knowledge' collection loaded")
                except:
                    logger.info("ℹ️ ChromaDB collection not found")
            except Exception as e:
                logger.warning(f"⚠️ ChromaDB initialization failed: {e}")

    async def search(self, query: str, diagnostic_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main search and generation method.
        Orchestrates: Google Search -> Chroma Retrieval -> Groq Generation.
        """
        logger.info(f"🔎 processing search query: {query}")
        
        # 1. Perform Google Search (Web Retrieval)
        google_results = await self._perform_google_search(query)
        
        # 2. Perform RAG Retrieval (Vector DB)
        rag_context = self._retrieve_rag_context(query)
        
        # 3. Generate Diagnostic Report using Groq
        # Pass diagnostic_context as the context argument
        diagnostic_response = await self._generate_groq_response(query, diagnostic_context, google_results, rag_context)

        # 4. Format Output
        return {
            "query": query,
            "diagnostic_response": diagnostic_response,
            "search_results": {
                "google_results": google_results,
                "rag_context": rag_context
            },
            "sources": self._extract_sources(google_results)
        }

    async def _perform_google_search(self, query: str) -> List[Dict[str, str]]:
        """Perform Google Custom Search"""
        if not self.google_service:
            return []
            
        try:
            # Run in executor to avoid blocking async loop
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None, 
                lambda: self.google_service.cse().list(q=query, cx=self.google_cse_id, num=5).execute()
            )
            
            results = []
            if 'items' in res:
                for item in res['items']:
                    results.append({
                        'title': item.get('title'),
                        'link': item.get('link'),
                        'snippet': item.get('snippet')
                    })
            return results
        except Exception as e:
            logger.error(f"Google search error: {e}")
            return []

    def _retrieve_rag_context(self, query: str) -> str:
        """Retrieve relevant context from ChromaDB"""
        if not self.collection:
            return ""
            
        try:
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=3
            )
            
            if results and results['documents']:
                # Flatten documents list
                docs = [doc for sublist in results['documents'] for doc in sublist]
                return "\n\n".join(docs)
            return ""
        except Exception as e:
            logger.warning(f"RAG retrieval error: {e}")
            return ""

    async def _generate_groq_response(self, query: str, context: Optional[Dict], 
                                    google_results: List[Dict], rag_context: str) -> str:
        """Generate formatted response using Groq LLM"""
        if not self.groq_client:
            return self._generate_fallback_response(query)

        # Construct Prompt
        # Construct Prompt
        system_prompt = """
You are MedimindAI, an advanced medical diagnostic assistant designed to emulate top-tier clinical reasoning and provide helpful medical information.

CORE INSTRUCTIONS:
1. IDENTIFY QUERY TYPE:
   - **DIAGNOSTIC CASE:** User provides specific patient symptoms, history, vitals, or asks "What do I have?".
   - **GENERAL INQUIRY:** User asks about a drug, condition, treatment, prevention, or general medical concept (e.g., "What is Tylenol?", "How to treat flu?").

2. INTEGRATE EVIDENCE: Cross-reference input with "Medical Knowledge (RAG)" and "Web Search Results".

3. FORMULATE RESPONSE:

   **FOR DIAGNOSTIC CASES ONLY (Use this Strict Format):**
   
   PRIMARY DIAGNOSIS: [Diagnosis Name]
   CONFIDENCE: [Percentage]%
   
   DIFFERENTIAL DIAGNOSES:
   [Diagnosis 1] ([Probability]%) - [Reasoning]
   
   KEY FINDINGS:
   - [Finding 1]
   
   MEDICATIONS:
   [Medication Name] - [Dosage/Instruction]
   
   RECOMMENDATIONS:
   - [Rec 1]
   
   FOLLOW-UP: [Timeline]
   
   Sources:
   [List sources]

   **FOR GENERAL INQUIRIES (Use this Markdown Format):**
   
   ## [Direct Answer to Question]
   
   [Provide a clear, comprehensive 2-3 paragraph explanation answering the user's specific question. Be educational and compassionate.]
   
   ### Key Facts
   - [Fact 1]
   - [Fact 2]
   
   ### Recommendations / Usage
   [Relevant advice, e.g., standard dosage, when to see a doctor, prevention tips]
   
   ### Medical Context
   [Synthesize RAG and Search results here]
   
   **Sources:**
   [List relevant sources from context]

4. TONE: Professional, objective, and empathetic. Always clarify you are an AI assistant.
"""

        # Prepare context sections
        symptoms = ", ".join(context.get("symptoms", [])) if context else "Not specified"
        history = context.get("medical_history", "None") if context else "None"
        age = context.get("patient_age", "Unknown")
        gender = context.get("patient_gender", "Unknown")
        
        # Extract previous conversation history
        conversation_context = ""
        chat_history = context.get("conversation_history", []) if context else []
        if chat_history:
            # Take last 3 exchanges to maintain context without overloading
            recent_history = chat_history[-6:] 
            history_text = "\n".join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in recent_history])
            conversation_context = f"\n### PREVIOUS CONVERSATION\n{history_text}\n"

        # Extract report data if available
        report_findings = context.get("report_findings", [])
        report_text = context.get("uploaded_report_full_text", "")
        lab_values = context.get("lab_values", {})
        
        report_section = ""
        if report_findings or report_text or lab_values:
            report_section = "\n### UPLOADED MEDICAL REPORT DATA\n"
            if report_findings:
                cleaned_findings = [f for f in report_findings if len(f) < 200]
                report_section += f"- **Extracted Findings:** {'; '.join(cleaned_findings)}\n"
            if lab_values:
                report_section += f"- **Lab Values:** {json.dumps(lab_values, indent=2)}\n"
            if report_text:
                # Truncate report text to avoid context preservation issues if too large
                report_section += f"- **Full Report Text (Snippet):**\n  > {report_text[:3000]}...\n"
        
        # Format Google Results with bolding for emphasis in prompt (LLM reads text)
        google_text = "\n".join([f"- [SOURCE: {r['title']}]({r['link']}): {r['snippet']}" for r in google_results])
        
        user_prompt = f"""
### PATIENT PROFILE
- **Age/Gender:** {age} / {gender}
- **Presenting Symptoms:** {symptoms}
- **Medical History:** {history}
- **Clinical Query:** {query}

{conversation_context}

{report_section}

### MEDICAL EVIDENCE (RAG - Internal Knowledge Base)
{rag_context}

### LATEST CLINICAL LITERATURE (Web Search Results)
The following are real-time search results from top medical websites. Use these to validate findings:
{google_text}

### DIAGNOSTIC TASK
Based *strictly* on the above patient profile, conversation context, uploaded report data, and medical evidence:
1. Answer the user's query directly and compassionately.
2. Synthesize the RAG context and Web Search results to support your answer.
3. If this is a follow-up question, use the previous conversation context.
4. Provide actionable recommendations.
"""

        try:
            completion = await self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Updated to supported model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3, # Low temperature for medical accuracy
                max_tokens=1024
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq generation error: {e}")
            return self._generate_fallback_response(query, error=str(e))

    def _generate_fallback_response(self, query: str, error: str = "") -> str:
        """Fallback response if Groq fails"""
        return f"""
PRIMARY DIAGNOSIS: Analysis Incomplete (Service Unavailable)
CONFIDENCE: 0%

KEY FINDINGS:
- System was unable to generate a full report using the AI model.
- Error: {error}

RECOMMENDATIONS:
- Please try again later.
- Consult a physician directly.

Sources:
• System Error
"""

    def _extract_sources(self, google_results: List[Dict]) -> List[Dict[str, str]]:
        """Extract sources for frontend display"""
        sources = []
        for res in google_results[:3]:
            sources.append({
                "name": res.get("title", "Web Source"),
                "type": "web",
                "url": res.get("link", "")
            })
        return sources

    def get_agent_info(self) -> Dict[str, Any]:
        """Info for AgentManager"""
        return {
            "agent_name": "Medical Search Agent (Groq)",
            "model": "llama3-70b-8192",
            "capabilities": ["Web Search", "RAG", "Medical Diagnosis"],
            "groq_enabled": bool(self.groq_client)
        }
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
import asyncio
import json
import os
import tempfile
import logging
from pathlib import Path
import uvicorn
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager


# Import your diagnostic agent and search agent
from diagnostic_agent import MedicalDiagnosticAgent, DiagnosticInput, DiagnosticResult
from search_agent import MedicalSearchAgent  # Import your search agent
from hospital_operations_agent import HospitalOperationsAgent
from hospital_operations_data_model import (
    HospitalOperationsData, 
    DashboardStats, 
    PriorityDistribution, 
    DepartmentStats, 
    AgeDistribution
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize agents (global variables)
diagnostic_agent = None
search_agent = None
hospital_operations_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agents on startup"""
    global diagnostic_agent, search_agent, hospital_operations_agent
    
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        google_key = os.getenv("GOOGLE_API_KEY")
        google_cse_id = os.getenv("GOOGLE_CSE_ID")
        
        if not groq_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        # Initialize diagnostic agent
        diagnostic_agent = MedicalDiagnosticAgent(
            gemini_api_key=groq_key,
            google_api_key=google_key,
            google_cse_id=google_cse_id
        )
        
        # Initialize search agent
        search_agent = MedicalSearchAgent(
            gemini_api_key=groq_key,
            google_api_key=google_key,
            google_cse_id=google_cse_id,
            pdf_directory="medical_papers"  # Directory for medical papers
        )
        
        # Initialize hospital operations agent
        hospital_operations_agent = HospitalOperationsAgent()
        
        logger.info("Medical Diagnostic Agent, Search Agent, and Hospital Operations Agent initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        raise
    
    yield  # This is where the app runs
    
    # Cleanup code would go here if needed
    logger.info("Application shutting down")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="MediMind AI API",
    description="AI-powered medical diagnostic, search assistant, and hospital operations API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware with more permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173"  
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class DiagnosticRequest(BaseModel):
    symptoms: List[str] = []
    medical_history: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None
    vital_signs: Optional[Dict[str, float]] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Medical question or query")

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    source: str
    relevance_score: float
    timestamp: str

class RAGResult(BaseModel):
    content: str
    source_file: str
    page_number: int
    relevance_score: float

class SearchResponse(BaseModel):
    query: str
    final_response: str
    web_results: List[SearchResult] = []
    rag_results: List[RAGResult] = []
    timestamp: str

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|ai)$")
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None

class SourceInfo(BaseModel):
    """Model for source information"""
    title: str
    url: Optional[str] = None
    source: Optional[str] = None

class DiagnosticResponse(BaseModel):
    primary_diagnosis: str
    confidence_score: float
    differential_diagnoses: List[Dict[str, Any]]
    severity: str
    findings: List[str]
    recommendations: List[str]
    follow_up_questions: List[str]
    first_aid_steps: List[str]
    medications: List[Dict[str, str]]
    emergency_indicators: List[str]
    follow_up: Optional[str] = None
    sources: Optional[List[Union[str, SourceInfo]]] = None

# Hospital Operations Models
class HospitalOperationsRequest(BaseModel):
    """Request model for hospital operations analysis"""
    pass

class HospitalOperationsResponse(BaseModel):
    """Response model for hospital operations data"""
    dashboard_stats: DashboardStats
    priority_distribution: List[PriorityDistribution]
    department_stats: List[DepartmentStats]
    age_distribution: List[AgeDistribution]
    total_patients_processed: int
    message: str

class HealthResponse(BaseModel):
    status: str
    message: str
    diagnostic_agent_initialized: bool
    search_agent_initialized: bool
    hospital_operations_agent_initialized: bool

# Helper functions (keeping existing ones)
def process_sources(sources: Optional[List[Any]]) -> Optional[List[str]]:
    """Convert sources to list of strings for the response"""
    if not sources:
        return None
    
    processed_sources = []
    for source in sources:
        if isinstance(source, str):
            processed_sources.append(source)
        elif isinstance(source, dict):
            if 'title' in source and 'url' in source:
                processed_sources.append(f"{source['title']} - {source['url']}")
            elif 'title' in source:
                processed_sources.append(source['title'])
            elif 'url' in source:
                processed_sources.append(source['url'])
            else:
                processed_sources.append(str(source))
        else:
            processed_sources.append(str(source))
    
    return processed_sources

async def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file to temporary location and return path"""
    try:
        suffix = Path(file.filename).suffix if file.filename else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"Saved uploaded file: {file.filename} -> {temp_file_path}")
        return temp_file_path
        
    except Exception as e:
        logger.error(f"Error saving uploaded file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )

def cleanup_temp_files(file_paths: List[str]):
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

def _aggregate_hospital_results(existing_results: Dict[str, Any], new_results: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate hospital operations results from multiple files"""
    
    # Aggregate dashboard stats
    existing_stats = existing_results["dashboard_stats"]
    new_stats = new_results["dashboard_stats"]
    
    aggregated_stats = {
        "total_patients": existing_stats["total_patients"] + new_stats["total_patients"],
        "inpatients": existing_stats["inpatients"] + new_stats["inpatients"],
        "outpatients": existing_stats["outpatients"] + new_stats["outpatients"],
        "critical_patients": existing_stats["critical_patients"] + new_stats["critical_patients"],
        "unattended_patients": existing_stats["unattended_patients"] + new_stats["unattended_patients"],
        "total_beds": max(existing_stats["total_beds"], new_stats["total_beds"]),  # Use max beds
        "occupied_beds": existing_stats["inpatients"] + new_stats["inpatients"],  # Same as inpatients
        "available_beds": max(existing_stats["total_beds"], new_stats["total_beds"]) - (existing_stats["inpatients"] + new_stats["inpatients"])
    }
    
    # Aggregate priority distribution
    priority_map = {}
    for item in existing_results["priority_distribution"] + new_results["priority_distribution"]:
        priority_map[item["name"]] = priority_map.get(item["name"], 0) + item["value"]
    
    aggregated_priority = [{"name": name, "value": value} for name, value in priority_map.items()]
    
    # Aggregate department stats
    dept_map = {}
    for item in existing_results["department_stats"] + new_results["department_stats"]:
        dept_map[item["name"]] = dept_map.get(item["name"], 0) + item["value"]
    
    aggregated_departments = [{"name": name, "value": value} for name, value in dept_map.items()]
    
    # Aggregate age distribution
    age_map = {}
    for item in existing_results["age_distribution"] + new_results["age_distribution"]:
        age_map[item["age_range"]] = age_map.get(item["age_range"], 0) + item["count"]
    
    aggregated_age = [{"age_range": age_range, "count": count} for age_range, count in age_map.items()]
    
    return {
        "dashboard_stats": aggregated_stats,
        "priority_distribution": aggregated_priority,
        "department_stats": aggregated_departments,
        "age_distribution": aggregated_age,
        "total_patients_processed": existing_results["total_patients_processed"] + new_results["total_patients_processed"]
    }

# API Endpoints

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return HealthResponse(
        status="healthy",
        message="MediMind AI API is running",
        diagnostic_agent_initialized=diagnostic_agent is not None,
        search_agent_initialized=search_agent is not None,
        hospital_operations_agent_initialized=hospital_operations_agent is not None
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="MediMind AI API is running",
        diagnostic_agent_initialized=diagnostic_agent is not None,
        search_agent_initialized=search_agent is not None,
        hospital_operations_agent_initialized=hospital_operations_agent is not None
    )

# Handle OPTIONS requests explicitly for health endpoints
@app.options("/")
async def options_root():
    """Handle OPTIONS request for root endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/health")
async def options_health():
    """Handle OPTIONS request for health endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Medical Search Endpoints

@app.post("/search", response_model=SearchResponse)
async def search_medical_information(request: SearchRequest):
    """
    Search for medical information using web search and RAG
    """
    if search_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search agent not initialized"
        )
    
    try:
        logger.info(f"Processing search query: {request.query}")
        
        # Use the search agent to get comprehensive results
        result = await search_agent.search_and_respond(request.query)
        
        # Convert search results to response format
        web_results = []
        for web_result in result.get('web_results', []):
            web_results.append(SearchResult(
                title=web_result.get('title', ''),
                url=web_result.get('url', ''),
                content=web_result.get('content', ''),
                source=web_result.get('source', ''),
                relevance_score=web_result.get('relevance_score', 0.0),
                timestamp=web_result.get('timestamp', '')
            ))
        
        rag_results = []
        for rag_result in result.get('rag_results', []):
            rag_results.append(RAGResult(
                content=rag_result.get('content', ''),
                source_file=rag_result.get('source_file', ''),
                page_number=rag_result.get('page_number', 0),
                relevance_score=rag_result.get('relevance_score', 0.0)
            ))
        
        response = SearchResponse(
            query=result['query'],
            final_response=result['final_response'],
            web_results=web_results,
            rag_results=rag_results,
            timestamp=result['timestamp']
        )
        
        logger.info(f"Search completed successfully for query: {request.query}")
        return response
        
    except Exception as e:
        logger.error(f"Error during medical search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during search: {str(e)}"
        )

@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    Chat endpoint that provides conversational medical assistance
    """
    if search_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search agent not initialized"
        )
    
    try:
        logger.info(f"Processing chat message: {request.message}")
        
        # Use search agent for comprehensive response
        result = await search_agent.search_and_respond(request.message)
        
        # Extract sources for citation
        sources = []
        for web_result in result.get('web_results', []):
            if web_result.get('url'):
                sources.append(f"{web_result.get('source', 'Unknown')} - {web_result.get('url')}")
        
        for rag_result in result.get('rag_results', []):
            if rag_result.get('source_file'):
                sources.append(f"{rag_result.get('source_file')} (Page {rag_result.get('page_number', 'N/A')})")
        
        response = ChatResponse(
            response=result['final_response'],
            sources=sources if sources else None
        )
        
        logger.info(f"Chat response generated successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error during chat processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during chat processing: {str(e)}"
        )

# Hospital Operations Endpoints

@app.post("/hospital-operations/analyze", response_model=HospitalOperationsResponse)
async def analyze_hospital_operations(
    files: List[UploadFile] = File(...)
):
    """
    Analyze hospital operations data from uploaded files (CSV, Excel, PDF)
    Returns structured data for dashboard visualizations
    """
    if hospital_operations_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hospital operations agent not initialized"
        )
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file must be uploaded"
        )
    
    temp_file_paths = []
    all_results = {
        "dashboard_stats": {
            "total_patients": 0,
            "inpatients": 0,
            "outpatients": 0,
            "critical_patients": 0,
            "unattended_patients": 0,
            "total_beds": 200,
            "occupied_beds": 0,
            "available_beds": 200
        },
        "priority_distribution": [],
        "department_stats": [],
        "age_distribution": [],
        "total_patients_processed": 0
    }
    
    try:
        # Process each uploaded file
        for file in files:
            if not file.filename:
                continue
                
            # Validate file type
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in ['.csv', '.xlsx', '.xls', '.pdf']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {file_extension}. Supported types: CSV, Excel, PDF"
                )
            
            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
                temp_file_paths.append(temp_file_path)
            
            logger.info(f"Processing hospital operations file: {file.filename}")
            
            # Process the file using the hospital operations agent
            file_results = await hospital_operations_agent.process_file(temp_file_path, content)
            
            # Aggregate results from all files
            all_results = _aggregate_hospital_results(all_results, file_results)
        
        # Convert aggregated results to response format
        response = HospitalOperationsResponse(
            dashboard_stats=DashboardStats(**all_results["dashboard_stats"]),
            priority_distribution=[
                PriorityDistribution(**item) for item in all_results["priority_distribution"]
            ],
            department_stats=[
                DepartmentStats(**item) for item in all_results["department_stats"]
            ],
            age_distribution=[
                AgeDistribution(**item) for item in all_results["age_distribution"]
            ],
            total_patients_processed=all_results["total_patients_processed"],
            message=f"Successfully processed {len(files)} file(s) with {all_results['total_patients_processed']} patients"
        )
        
        logger.info(f"Hospital operations analysis completed. Processed {all_results['total_patients_processed']} patients from {len(files)} files")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during hospital operations analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )
    finally:
        # Clean up temporary files
        for temp_path in temp_file_paths:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")

@app.get("/hospital-operations/sample-data", response_model=HospitalOperationsResponse)
async def get_sample_hospital_data():
    """
    Get sample hospital operations data for testing the frontend
    """
    try:
        # Generate sample data that matches your frontend expectations
        sample_data = {
            "dashboard_stats": {
                "total_patients": 150,
                "inpatients": 105,
                "outpatients": 45,
                "critical_patients": 8,
                "unattended_patients": 12,
                "total_beds": 200,
                "occupied_beds": 105,
                "available_beds": 95
            },
            "priority_distribution": [
                {"name": "Normal", "value": 120},
                {"name": "Urgent", "value": 22},
                {"name": "Critical", "value": 8}
            ],
            "department_stats": [
                {"name": "Cardiology", "value": 25},
                {"name": "Internal Medicine", "value": 35},
                {"name": "Surgery", "value": 20},
                {"name": "Pulmonology", "value": 15},
                {"name": "Emergency", "value": 30},
                {"name": "General", "value": 25}
            ],
            "age_distribution": [
                {"age_range": "0-18", "count": 15},
                {"age_range": "19-35", "count": 35},
                {"age_range": "36-50", "count": 45},
                {"age_range": "51-65", "count": 35},
                {"age_range": "65+", "count": 20}
            ],
            "total_patients_processed": 150
        }
        
        response = HospitalOperationsResponse(
            dashboard_stats=DashboardStats(**sample_data["dashboard_stats"]),
            priority_distribution=[
                PriorityDistribution(**item) for item in sample_data["priority_distribution"]
            ],
            department_stats=[
                DepartmentStats(**item) for item in sample_data["department_stats"]
            ],
            age_distribution=[
                AgeDistribution(**item) for item in sample_data["age_distribution"]
            ],
            total_patients_processed=sample_data["total_patients_processed"],
            message="Sample hospital operations data for testing"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating sample data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred generating sample data: {str(e)}"
        )

# OPTIONS handlers for hospital operations endpoints
@app.options("/hospital-operations/analyze")
async def options_hospital_operations_analyze():
    """Handle OPTIONS request for hospital operations analyze endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/hospital-operations/sample-data")
async def options_hospital_operations_sample():
    """Handle OPTIONS request for hospital operations sample data endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Diagnostic endpoints (keeping them unchanged)

@app.post("/analyze", response_model=DiagnosticResponse)
async def analyze_diagnostics(
    files: List[UploadFile] = File(default=[]),
    symptoms: str = Form(default="[]"),
    medical_history: str = Form(default=""),
    age: Optional[int] = Form(default=None),
    gender: Optional[str] = Form(default=None),
    vital_signs: str = Form(default="{}")
):
    """
    Analyze medical reports and symptoms to provide diagnostic insights
    """
    if diagnostic_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagnostic agent not initialized"
        )
    
    temp_file_paths = []
    
    try:
        # Parse JSON strings from form data
        try:
            symptoms_list = json.loads(symptoms) if symptoms else []
            vital_signs_dict = json.loads(vital_signs) if vital_signs else {}
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format: {str(e)}"
            )
        
        # Validate input
        if not files and not symptoms_list and not medical_history.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide at least one of: medical reports, symptoms, or medical history"
            )
        
        # Save uploaded files temporarily
        uploaded_report_paths = []
        for file in files:
            if file.filename:
                temp_path = await save_uploaded_file(file)
                temp_file_paths.append(temp_path)
                uploaded_report_paths.append(temp_path)
        
        # Create diagnostic input
        diagnostic_input = DiagnosticInput(
            symptoms=symptoms_list,
            medical_history=medical_history,
            uploaded_reports=uploaded_report_paths,
            age=age,
            gender=gender,
            vital_signs=vital_signs_dict if vital_signs_dict else None
        )
        
        logger.info(f"Processing diagnostic request with {len(uploaded_report_paths)} files, "
                   f"{len(symptoms_list)} symptoms, and medical history: {bool(medical_history.strip())}")
        
        # Run diagnosis
        result = await diagnostic_agent.diagnose(diagnostic_input)
        
        # Process sources to ensure they're strings
        processed_sources = process_sources(result.sources)
        
        # Convert result to response format
        response = DiagnosticResponse(
            primary_diagnosis=result.primary_diagnosis,
            confidence_score=result.confidence_score,
            differential_diagnoses=result.differential_diagnoses,
            severity=result.severity,
            findings=result.findings,
            recommendations=result.recommendations,
            follow_up_questions=result.follow_up_questions,
            first_aid_steps=result.first_aid_steps,
            medications=result.medications,
            emergency_indicators=result.emergency_indicators,
            follow_up=result.follow_up,
            sources=processed_sources
        )
        
        logger.info(f"Diagnostic analysis completed successfully. Primary diagnosis: {result.primary_diagnosis}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during diagnostic analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )
    finally:
        cleanup_temp_files(temp_file_paths)

@app.post("/analyze-symptoms", response_model=DiagnosticResponse)
async def analyze_symptoms_only(request: DiagnosticRequest):
    """
    Analyze symptoms without file uploads (for quick symptom checking)
    """
    if diagnostic_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagnostic agent not initialized"
        )
    
    try:
        # Validate input
        if not request.symptoms and not request.medical_history.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide symptoms or medical history"
            )
        
        # Create diagnostic input
        diagnostic_input = DiagnosticInput(
            symptoms=request.symptoms,
            medical_history=request.medical_history,
            uploaded_reports=[],
            age=request.age,
            gender=request.gender,
            vital_signs=request.vital_signs
        )
        
        logger.info(f"Processing symptom-only analysis with {len(request.symptoms)} symptoms")
        
        # Run diagnosis
        result = await diagnostic_agent.diagnose(diagnostic_input)
        
        # Process sources to ensure they're strings
        processed_sources = process_sources(result.sources)
        
        # Convert result to response format
        response = DiagnosticResponse(
            primary_diagnosis=result.primary_diagnosis,
            confidence_score=result.confidence_score,
            differential_diagnoses=result.differential_diagnoses,
            severity=result.severity,
            findings=result.findings,
            recommendations=result.recommendations,
            follow_up_questions=result.follow_up_questions,
            first_aid_steps=result.first_aid_steps,
            medications=result.medications,
            emergency_indicators=result.emergency_indicators,
            follow_up=result.follow_up,
            sources=processed_sources
        )
        
        logger.info(f"Symptom analysis completed successfully. Primary diagnosis: {result.primary_diagnosis}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during symptom analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )

@app.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported file formats"""
    return {
        "supported_formats": [
            {
                "extension": ".pdf",
                "description": "PDF documents",
                "mime_types": ["application/pdf"]
            },
            {
                "extension": ".txt",
                "description": "Text files",
                "mime_types": ["text/plain"]
            },
            {
                "extension": ".doc",
                "description": "Microsoft Word documents",
                "mime_types": ["application/msword"]
            },
            {
                "extension": ".docx",
                "description": "Microsoft Word documents (newer format)",
                "mime_types": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
            },
            {
                "extension": ".jpg/.jpeg",
                "description": "JPEG images",
                "mime_types": ["image/jpeg"]
            },
            {
                "extension": ".png",
                "description": "PNG images",
                "mime_types": ["image/png"]
            },
            {
                "extension": ".csv",
                "description": "CSV files",
                "mime_types": ["text/csv"]
            },
            {
                "extension": ".xlsx/.xls",
                "description": "Excel files",
                "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]
            }
        ],
        "max_file_size": "10MB",
        "max_files_per_request": 10
    }

# OPTIONS handlers for diagnostic endpoints
@app.options("/analyze")
async def options_analyze():
    """Handle OPTIONS request for analyze endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/analyze-symptoms")
async def options_analyze_symptoms():
    """Handle OPTIONS request for analyze-symptoms endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/search")
async def options_search():
    """Handle OPTIONS request for search endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/chat")
async def options_chat():
    """Handle OPTIONS request for chat endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/supported-formats")
async def options_supported_formats():
    """Handle OPTIONS request for supported-formats endpoint"""
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with proper CORS headers"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions with proper CORS headers"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Additional utility endpoints
@app.get("/api/status")
async def get_api_status():
    """Get detailed API status information"""
    return {
        "status": "operational",
        "version": "1.0.0",
        "services": {
            "diagnostic_agent": {
                "status": "active" if diagnostic_agent is not None else "inactive",
                "description": "Medical diagnostic analysis service"
            },
            "search_agent": {
                "status": "active" if search_agent is not None else "inactive",
                "description": "Medical information search service"
            },
            "hospital_operations_agent": {
                "status": "active" if hospital_operations_agent is not None else "inactive",
                "description": "Hospital operations data analysis service"
            }
        },
        "endpoints": {
            "diagnostic": ["/analyze", "/analyze-symptoms"],
            "search": ["/search", "/chat"],
            "hospital_operations": ["/hospital-operations/analyze", "/hospital-operations/sample-data"],
            "utility": ["/health", "/supported-formats", "/api/status"]
        }
    }

@app.get("/api/metrics")
async def get_api_metrics():
    """Get basic API metrics (placeholder for monitoring)"""
    return {
        "uptime": "Available since server start",
        "total_requests": "Not tracked in this version",
        "active_connections": "Not tracked in this version",
        "memory_usage": "Not tracked in this version",
        "note": "Detailed metrics require additional monitoring setup"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
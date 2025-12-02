import sys
import os
from pathlib import Path

current_dir = Path(__file__).parent  
project_root = current_dir.parent  
parent_root = project_root.parent  

sys.path.insert(0, str(parent_root))  
sys.path.insert(0, str(project_root))  

agents_path = project_root / 'agents'
if agents_path.exists():
    sys.path.insert(0, str(agents_path))
    print(f"Added agents directory to path: {agents_path}")
    print(f"Agents directory contents: {list(agents_path.iterdir())}")

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
import asyncio
import json
import tempfile
import logging
from pathlib import Path
import uvicorn
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from datetime import datetime

# Configure logging EARLY
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import agents with better error handling
agent_manager = None
diagnostic_agent = None
search_agent = None
hospital_operations_agent = None

# Store import errors for debugging
import_errors = {}

# Try importing data models first (no dependencies)
try:
    from hospital_operations_data_model import (
        HospitalOperationsData, 
        DashboardStats, 
        PriorityDistribution, 
        DepartmentStats, 
        AgeDistribution
    )
    logger.info("✓ Successfully imported hospital operations data models")
except ImportError as e:
    logger.error(f"✗ Failed to import hospital operations data models: {e}")
    import_errors['hospital_operations_data_model'] = str(e)
    
    # Define placeholder classes
    class DashboardStats(BaseModel):
        total_patients: int = 0
        inpatients: int = 0
        outpatients: int = 0
        critical_patients: int = 0
        unattended_patients: int = 0
        total_beds: int = 0
        occupied_beds: int = 0
        available_beds: int = 0
    
    class PriorityDistribution(BaseModel):
        name: str = ""
        value: int = 0
    
    class DepartmentStats(BaseModel):
        name: str = ""
        value: int = 0
    
    class AgeDistribution(BaseModel):
        age_range: str = ""
        count: int = 0

# Try importing search agent (minimal dependencies)
try:
    from search_agent import MedicalSearchAgent
    logger.info("✓ Successfully imported from search_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from search_agent: {e}")
    import_errors['search_agent'] = str(e)
    MedicalSearchAgent = None

# Try importing diagnostic agent
try:
    from diagnosis_agent import MedicalDiagnosticAgent, DiagnosticInput, DiagnosticResult
    logger.info("✓ Successfully imported from diagnosis_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from diagnosis_agent: {e}")
    import_errors['diagnosis_agent'] = str(e)
    MedicalDiagnosticAgent = None
    
    # Define placeholder classes
    class DiagnosticInput(BaseModel):
        pass
    
    class DiagnosticResult(BaseModel):
        pass

# Try importing hospital operations agent
try:
    from hospital_operations_agent import HospitalOperationsAgent
    logger.info("✓ Successfully imported from hospital_operations_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from hospital_operations_agent: {e}")
    import_errors['hospital_operations_agent'] = str(e)
    HospitalOperationsAgent = None

# Try importing manager agent LAST (depends on others)
try:
    from manager_agent import AgentManager, UserQuery
    logger.info("✓ Successfully imported from manager_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from manager_agent: {e}")
    import_errors['manager_agent'] = str(e)
    AgentManager = None
    
    # Define placeholder class
    class UserQuery(BaseModel):
        query_type: str
        content: str
        user_context: Dict[str, Any] = {}
        files: List[str] = []

# Define Pydantic models
class SourceInfo(BaseModel):
    """Model for source information"""
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all agents on startup using the Manager Agent"""
    global agent_manager, diagnostic_agent, search_agent, hospital_operations_agent
    
    # Log all import errors at startup
    if import_errors:
        logger.warning("=" * 80)
        logger.warning("IMPORT ERRORS DETECTED:")
        for module, error in import_errors.items():
            logger.warning(f"  {module}: {error}")
        logger.warning("=" * 80)
    
    try:
        google_key = os.getenv("GOOGLE_API_KEY")
        google_cse_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
        
        if not google_key or not google_cse_id:
            logger.warning("⚠ GOOGLE_API_KEY or GOOGLE_CUSTOM_SEARCH_ENGINE_ID not found in environment")
            logger.warning("⚠ Search functionality will be limited")
            google_key = google_key or "dummy_key"
            google_cse_id = google_cse_id or "dummy_cse_id"
        
        if AgentManager is not None:
            logger.info("Initializing Agent Manager and all sub-agents...")
            
            try:
                # Initialize Agent Manager (which initializes all sub-agents)
                agent_manager = AgentManager(
                    google_api_key=google_key,
                    google_cse_id=google_cse_id
                )
                
                # Get references to individual agents from manager
                diagnostic_agent = agent_manager.diagnostic_agent
                search_agent = agent_manager.search_agent
                hospital_operations_agent = agent_manager.hospital_agent
                
                # Test each agent
                manager_info = agent_manager.get_manager_info()
                logger.info(f"✅ Agent Manager initialized: {manager_info['manager_name']}")
                logger.info(f"✅ Available agents: {list(manager_info['agents_available'].keys())}")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize Agent Manager: {e}")
                logger.exception("Full traceback:")
                agent_manager = None
        else:
            logger.warning("⚠ AgentManager class not available - running in fallback mode")
            
            # Try to initialize individual agents if available
            if MedicalSearchAgent is not None:
                try:
                    search_agent = MedicalSearchAgent(google_key, google_cse_id)
                    logger.info("✅ Initialized MedicalSearchAgent individually")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize MedicalSearchAgent: {e}")
            
            if MedicalDiagnosticAgent is not None:
                try:
                    diagnostic_agent = MedicalDiagnosticAgent()
                    logger.info("✅ Initialized MedicalDiagnosticAgent individually")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize MedicalDiagnosticAgent: {e}")
            
            if HospitalOperationsAgent is not None:
                try:
                    hospital_operations_agent = HospitalOperationsAgent()
                    logger.info("✅ Initialized HospitalOperationsAgent individually")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize HospitalOperationsAgent: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error during agent initialization: {e}")
        logger.exception("Full traceback:")
    
    # Log final status
    logger.info("=" * 80)
    logger.info("INITIALIZATION COMPLETE:")
    logger.info(f"  Agent Manager: {'✅ Active' if agent_manager else '❌ Inactive'}")
    logger.info(f"  Diagnostic Agent: {'✅ Active' if diagnostic_agent else '❌ Inactive'}")
    logger.info(f"  Search Agent: {'✅ Active' if search_agent else '❌ Inactive'}")
    logger.info(f"  Hospital Operations Agent: {'✅ Active' if hospital_operations_agent else '❌ Inactive'}")
    logger.info("=" * 80)
    
    yield  # This is where the app runs
    
    # Cleanup code would go here if needed
    logger.info("Application shutting down")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="MediMind AI API",
    description="AI-powered medical diagnostic, search assistant, hospital operations with intelligent agent orchestration",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Pydantic models for request/response

# Unified Query Models
class UnifiedQueryRequest(BaseModel):
    """Unified request model for agent manager"""
    query: str = Field(..., min_length=1, max_length=2000, description="User query or request")
    query_type: str = Field("general", description="Type of query: diagnosis, search, operations, general")
    age: Optional[int] = Field(None, ge=0, le=120, description="Patient age")
    gender: Optional[str] = Field(None, description="Patient gender")
    medical_history: Optional[str] = Field("", description="Medical history")
    symptoms: Optional[List[str]] = Field([], description="List of symptoms")
    vital_signs: Optional[Dict[str, float]] = Field({}, description="Vital signs")

class AgentResponseModel(BaseModel):
    """Standardized agent response model"""
    agent_type: str
    response: Dict[str, Any]
    confidence: float
    timestamp: str
    sources: Optional[List[Union[str, SourceInfo]]] = None
    recommendations: Optional[List[str]] = None
    query_processed: Optional[str] = None

# Legacy models (for backward compatibility)
class DiagnosticRequest(BaseModel):
    symptoms: List[str] = []
    medical_history: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None
    vital_signs: Optional[Dict[str, float]] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Medical question or query")

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
    manager_initialized: bool
    diagnostic_agent_initialized: bool
    search_agent_initialized: bool
    hospital_operations_agent_initialized: bool
    import_errors: Optional[Dict[str, str]] = None
    timestamp: str

class AgentInfoResponse(BaseModel):
    """Response model for agent information"""
    manager_name: str
    description: str
    agents_available: Dict[str, str]
    capabilities: List[str]
    agent_status: Dict[str, bool]

# Helper functions
async def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file to temporary location and return path"""
    try:
        suffix = Path(file.filename).suffix if file.filename else ".tmp"
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
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

# API Endpoints

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return HealthResponse(
        status="healthy" if agent_manager is not None else "degraded",
        message="MediMind AI API is running" if agent_manager is not None else "API running in fallback mode",
        manager_initialized=agent_manager is not None,
        diagnostic_agent_initialized=diagnostic_agent is not None,
        search_agent_initialized=search_agent is not None,
        hospital_operations_agent_initialized=hospital_operations_agent is not None,
        import_errors=import_errors if import_errors else None,
        timestamp=datetime.now().isoformat()
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with detailed import error information"""
    return HealthResponse(
        status="healthy" if agent_manager is not None else "degraded",
        message="MediMind AI API is running" if agent_manager is not None else "Agent Manager not initialized - check import_errors",
        manager_initialized=agent_manager is not None,
        diagnostic_agent_initialized=diagnostic_agent is not None,
        search_agent_initialized=search_agent is not None,
        hospital_operations_agent_initialized=hospital_operations_agent is not None,
        import_errors=import_errors if import_errors else None,
        timestamp=datetime.now().isoformat()
    )

# Continue with rest of endpoints...
# (The rest of your endpoints remain the same)

@app.post("/agent/query", response_model=AgentResponseModel)
async def unified_agent_query(
    query: str = Form(..., description="User query or request"),
    query_type: str = Form("general", description="Type of query: diagnosis, search, operations, general"),
    age: Optional[int] = Form(None),
    gender: Optional[str] = Form(None),
    medical_history: Optional[str] = Form(""),
    symptoms: str = Form("[]"),
    vital_signs: str = Form("{}"),
    files: List[UploadFile] = File(default=[])
):
    """Unified endpoint that routes queries to appropriate agents"""
    if agent_manager is None:
        return AgentResponseModel(
            agent_type="fallback",
            response={
                "message": "Agents are not initialized. Please check server logs.",
                "import_errors": import_errors
            },
            confidence=0.0,
            timestamp=datetime.now().isoformat(),
            sources=None,
            recommendations=["Check server logs for import errors", "Ensure all dependencies are installed"],
            query_processed=query
        )
    
    temp_file_paths = []
    
    try:
        # Parse JSON strings
        try:
            symptoms_list = json.loads(symptoms) if symptoms else []
            vital_signs_dict = json.loads(vital_signs) if vital_signs else {}
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format: {str(e)}"
            )
        
        # Save uploaded files
        uploaded_files = []
        for file in files:
            if file.filename:
                temp_path = await save_uploaded_file(file)
                temp_file_paths.append(temp_path)
                uploaded_files.append(temp_path)
        
        # Create user query
        user_query = UserQuery(
            query_type=query_type,
            content=query,
            user_context={
                'age': age,
                'gender': gender,
                'medical_history': medical_history,
                'symptoms': symptoms_list,
                'vital_signs': vital_signs_dict
            },
            files=uploaded_files
        )
        
        logger.info(f"Processing unified query: {query[:100]}... (Type: {query_type})")
        
        # Process through agent manager
        result = await agent_manager.process_query(user_query)
        
        # Format response
        response = AgentResponseModel(
            agent_type=result.agent_type,
            response=result.response_data,
            confidence=result.confidence,
            timestamp=result.timestamp.isoformat(),
            sources=result.sources,
            recommendations=result.recommendations,
            query_processed=query
        )
        
        logger.info(f"Query processed. Agent: {result.agent_type}, Confidence: {result.confidence}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in unified agent query: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )
    finally:
        cleanup_temp_files(temp_file_paths)

@app.get("/debug/imports")
async def debug_imports():
    """Debug endpoint to check import status"""
    return {
        "import_errors": import_errors,
        "agents_available": {
            "AgentManager": AgentManager is not None,
            "MedicalDiagnosticAgent": MedicalDiagnosticAgent is not None,
            "MedicalSearchAgent": MedicalSearchAgent is not None,
            "HospitalOperationsAgent": HospitalOperationsAgent is not None
        },
        "agents_initialized": {
            "agent_manager": agent_manager is not None,
            "diagnostic_agent": diagnostic_agent is not None,
            "search_agent": search_agent is not None,
            "hospital_operations_agent": hospital_operations_agent is not None
        },
        "python_path": sys.path[:5],  # First 5 entries
        "agents_directory": str(agents_path) if agents_path.exists() else "Not found"
    }

# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        workers=1
    )
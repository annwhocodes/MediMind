import sys
import os
from pathlib import Path

current_dir = Path(__file__).parent  
project_root = current_dir.parent  

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
from datetime import datetime, timedelta
from dataclasses import asdict, is_dataclass
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends

# Import auth utils
try:
    from auth_utils import verify_password, get_password_hash, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
except ImportError:
    # Handle relative import if needed
    sys.path.append(str(Path(__file__).parent))
    from auth_utils import verify_password, get_password_hash, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES


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

# Try importing data models
try:
    from hospital_operations_data_model import (
        HospitalOperationsData, DashboardStats, PriorityDistribution, 
        DepartmentStats, AgeDistribution
    )
    logger.info("✓ Successfully imported hospital operations data models")
except ImportError as e:
    logger.error(f"✗ Failed to import hospital operations data models: {e}")
    # Define placeholder classes if missing
    class DashboardStats(BaseModel):
        total_patients: int = 0
    class PriorityDistribution(BaseModel):
        name: str = ""
        value: int = 0
    class DepartmentStats(BaseModel):
        name: str = ""
        value: int = 0
    class AgeDistribution(BaseModel):
        age_range: str = ""
        count: int = 0

# Try importing agents
try:
    from search_agent import MedicalSearchAgent
    logger.info("✓ Successfully imported from search_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from search_agent: {e}")
    import_errors['search_agent'] = str(e)

try:
    print("DEBUG: Attempting to import diagnosis_agent...", flush=True)
    from diagnosis_agent import MedicalDiagnosticAgent, DiagnosticInput, DiagnosticResult
    logger.info("✓ Successfully imported from diagnosis_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from diagnosis_agent: {e}")
    import_errors['diagnosis_agent'] = str(e)

try:
    from hospital_operations_agent import HospitalOperationsAgent
    logger.info("✓ Successfully imported from hospital_operations_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from hospital_operations_agent: {e}")
    import_errors['hospital_operations_agent'] = str(e)

try:
    from manager_agent import AgentManager, UserQuery
    logger.info("✓ Successfully imported from manager_agent")
except ImportError as e:
    logger.error(f"✗ Failed to import from manager_agent: {e}")
    import_errors['manager_agent'] = str(e)

# Import database module
print("=" * 60)
print("ATTEMPTING TO IMPORT DATABASE MODULE...")
print("=" * 60)
try:
    import database as db
    print("✅ Database module IMPORTED successfully")
    print(f"✅ Database file location: {db.DB_FILE}")
    print(f"✅ Database file exists: {db.DB_FILE.exists()}")
    logger.info("✅ Database module loaded successfully")
    logger.info(f"✅ Database initialized at {db.DB_FILE}")
except Exception as e:
    print(f"❌ Database module FAILED to import: {e}")
    import traceback
    traceback.print_exc()
    logger.error(f"❌ Database module failed to import: {e}")
    db = None
print("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize agents
    global agent_manager, diagnostic_agent, search_agent, hospital_operations_agent
    
    logger.info("Initializing Agent Manager and all sub-agents...")
    
    # Load API keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not found in environment variables")
    else:
        logger.info("✅ GROQ_API_KEY found")
        
    try:
        # Initialize Agent Manager (which initializes sub-agents)
        if 'AgentManager' in globals() and AgentManager:
            agent_manager = AgentManager(
                google_api_key=GOOGLE_API_KEY,
                google_cse_id=GOOGLE_CSE_ID,
                groq_api_key=GROQ_API_KEY
            )
            
            # Access initialized sub-agents
            diagnostic_agent = agent_manager.diagnostic_agent
            search_agent = agent_manager.search_agent
            hospital_operations_agent = agent_manager.hospital_agent
            
            info = agent_manager.get_manager_info()
            logger.info("✅ Agent Manager initialized: " + info.get('manager_name', 'AgentManager'))
            logger.info("✅ Available agents: " + str(info.get('agents_available', {})))
            
            # Additional validation
            logger.info("=" * 80)
            logger.info("INITIALIZATION COMPLETE:")
            logger.info(f"  Agent Manager: {'✅ Active' if agent_manager else '❌ Failed'}")
            logger.info(f"  Diagnostic Agent: {'✅ Active' if diagnostic_agent else '❌ Failed'}")
            logger.info(f"  Search Agent: {'✅ Active' if search_agent else '❌ Failed'}")
            logger.info(f"  Hospital Operations Agent: {'✅ Active' if hospital_operations_agent else '❌ Failed'}")
            logger.info("=" * 80)
        else:
             logger.error("AgentManager class not available")
             
    except Exception as e:
        logger.error(f"Error initializing agents: {e}")
        import traceback
        traceback.print_exc()
        
    yield
    
    # Shutdown logic
    logger.info("Application shutting down")


app = FastAPI(title="MediMind AI API", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup_temp_files(file_paths: List[str]):
    """Clean up temporary files"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to delete temp file {path}: {e}")

# ==================== AUTHENTICATION ====================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "user" # 'user' or 'admin'

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str = payload.get("sub")
    role: str = payload.get("role")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": username, "role": role}

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized (Admin only)")
    return current_user

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister):
    if db.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    if db.create_user(user.username, hashed_password, user.role):
        return {"message": "User created successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to create user")

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['username'], "role": user['role']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user['role'], "username": user['username']}

# ==================== PATIENT DATABASE ENDPOINTS ====================

@app.post("/patients", status_code=status.HTTP_201_CREATED)
async def create_patient(
    name: str = Form(...),
    age: int = Form(None),
    gender: str = Form(None),
    symptoms: str = Form(None),
    medical_history: str = Form(None),
    bed_number: str = Form(None),
    bed_type: str = Form("general"),
    department: str = Form(None),
    priority: str = Form("normal"),
    status: str = Form("Active"),
    admission_date: str = Form(None),
    patient_id: str = Form(None),
    current_user: dict = Depends(get_current_admin)
):
    """Create a new patient record"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database module not available")
    
    try:
        patient_data = {
            "name": name,
            "age": age,
            "gender": gender,
            "symptoms": symptoms,
            "medical_history": medical_history,
            "bed_number": bed_number,
            "bed_type": bed_type,
            "department": department,
            "priority": priority,
            "status": status,
            "admission_date": admission_date,
            "patient_id": patient_id
        }
        
        # Save to database
        saved_id = db.save_patient(patient_data)
        if not saved_id:
            raise HTTPException(status_code=500, detail="Failed to save patient")
            
        logger.info(f"Created patient: {saved_id}")
        return {
            "success": True, 
            "patient_id": saved_id,
            "message": "Patient created successfully"
        }
    
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/patients")
async def get_all_patients(current_user: dict = Depends(get_current_admin)):
    """Get all patient records with their latest AI diagnosis"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database module not available")
    
    try:
        patients = db.get_all_patients()
        
        # Add latest diagnosis for each patient
        for patient in patients:
            try:
                diagnosis = db.get_latest_diagnosis(patient['patient_id'])
                if diagnosis:
                    patient['ai_diagnosis'] = {
                        'primary_diagnosis': diagnosis.get('primary_diagnosis'),
                        'confidence_score': diagnosis.get('confidence_score'),
                        'severity': 'normal',
                        'created_at': diagnosis.get('created_at')
                    }
            except Exception as e:
                logger.warning(f"Could not fetch diagnosis for patient {patient.get('patient_id')}: {e}")
                patient['ai_diagnosis'] = None
        
        return {
            "success": True,
            "count": len(patients),
            "patients": patients
        }
    except Exception as e:
        logger.error(f"Error retrieving patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """Get a specific patient record"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database module not available")
    
    try:
        patient = db.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return {
            "success": True,
            "patient": patient
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, current_user: dict = Depends(get_current_admin)):
    """Delete a patient record"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database module not available")
    
    try:
        success = db.delete_patient(patient_id)
        if not success:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return {"success": True, "message": f"Patient {patient_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DIAGNOSTIC ENDPOINTS ====================

@app.post("/analyze")
async def analyze_symptoms(
    files: List[UploadFile] = File(None),
    symptoms: str = Form("[]"),
    medical_history: str = Form("")
):
    """Analyze symptoms and medical reports (Ad-hoc diagnosis)"""
    temp_file_paths = []
    
    try:
        if diagnostic_agent is None:
            raise HTTPException(status_code=503, detail="Diagnostic agent not initialized")
            
        # 1. Process Files
        if files:
            for file in files:
                try:
                    suffix = Path(file.filename).suffix
                    # Create temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                        content = await file.read()
                        temp_file.write(content)
                        temp_file_paths.append(temp_file.name)
                        logger.info(f"Saved temp file: {temp_file.name}")
                except Exception as e:
                    logger.error(f"Error saving uploaded file {file.filename}: {e}")
        
        # 2. Process Symptoms
        try:
            symptoms_list = json.loads(symptoms) if symptoms else []
            if isinstance(symptoms_list, str):
                symptoms_list = [symptoms_list]
        except json.JSONDecodeError:
            symptoms_list = [s.strip() for s in symptoms.split(',') if s.strip()]
            
        # 3. Create Input
        diagnostic_input = DiagnosticInput(
            symptoms=symptoms_list,
            medical_history=medical_history,
            uploaded_reports=temp_file_paths,
            age=None, # Frontend doesn't pass age/gender in this form yet
            gender=None,
            vital_signs={} 
        )
        
        # 4. Run Diagnosis
        logger.info("Running ad-hoc diagnosis...")
        result = await diagnostic_agent.diagnose(diagnostic_input)
        
        # 5. format response using the same logic as diagnose_patient
        if is_dataclass(result):
            diagnosis_data = asdict(result)
        elif hasattr(result, 'to_dict'):
            diagnosis_data = result.to_dict()
        else:
            diagnosis_data = result.__dict__ if hasattr(result, '__dict__') else {}

        return diagnosis_data

    except Exception as e:
        logger.error(f"Error in /analyze: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup temp files
        if temp_file_paths:
            cleanup_temp_files(temp_file_paths)

@app.post("/patients/{patient_id}/diagnose")
async def diagnose_patient(patient_id: str):
    """Run AI diagnosis for a specific patient"""
    try:
        # Get patient data
        patient = db.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        if not agent_manager:
            raise HTTPException(status_code=503, detail="Agent Manager not initialized")
            
        # Create UserQuery for AgentManager
        # This allows us to leverage the manager's history fetching logic
        symptoms_str = patient.get('symptoms', '')
        medical_history = patient.get('medical_history', '')
        
        user_query = UserQuery(
            query_type='diagnosis',
            content=symptoms_str, # Pass symptoms as content string
            user_context={
                'patient_id': patient_id, # CRITICAL: This triggers history fetching in manager
                'medical_history': medical_history,
                'age': int(patient.get('age')) if patient.get('age') else None,
                'gender': patient.get('gender'),
                'vital_signs': patient.get('vitals')
            },
            files=[]
        )
        
        # Run diagnosis via Manager
        logger.info(f"Running diagnosis for patient: {patient_id} via AgentManager")
        response = await agent_manager.process_query(user_query)
        
        diagnosis_data = response.response_data
        
        logger.info(f"Diagnosis data keys: {list(diagnosis_data.keys())}")
        
        # Save diagnosis to database
        db.save_diagnosis_result(patient_id, diagnosis_data)
        
        logger.info(f"Diagnosis completed for patient: {patient_id}")
        return diagnosis_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running diagnosis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CSV UPLOAD ENDPOINT ====================

@app.post("/hospital/upload-csv")
async def upload_hospital_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_admin)):
    """Upload and process hospital patient CSV using Hospital Operations Agent"""
    if hospital_operations_agent is None:
        raise HTTPException(status_code=503, detail="Hospital Operations Agent not available")
    
    # Save uploaded file temporarily
    try:
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
            
        logger.info(f"Processing CSV file: {file.filename}")
        
        # Use agent to process file
        result = hospital_operations_agent.process_file(temp_file_path)
        
        # Check if we got patients back
        if not result or not result.get('patients'):
            # Try to get from stats if not in main result
            raise HTTPException(status_code=400, detail="No valid patient data found in CSV")
            
        patients = result.get('patients', [])
        logger.info(f"Extracted {len(patients)} patients from CSV")
        
        # Save to database
        saved_patients = []
        for p_obj in patients:
            # Convert dataclass to dict if necessary
            if is_dataclass(p_obj):
                p = asdict(p_obj)
            else:
                p = p_obj

            # Ensure required fields
            if not p.get('name'):
                continue
                
            # Map fields for database
            db_patient = {
                'name': p.get('name'),
                'age': p.get('age'),
                'gender': p.get('gender'),
                'bed_number': p.get('bed_number') or p.get('bedNumber'),
                'bed_type': p.get('bed_type') or p.get('bedType'),
                'status': p.get('status', 'Active'),
                'priority': p.get('priority', 'normal'),
                # Parse symptoms if it's a list
                'symptoms': p.get('symptoms') if isinstance(p.get('symptoms'), str) else ", ".join(p.get('symptoms', [])),
                'medical_history': p.get('medical_history') or p.get('medicalHistory'),
                'department': p.get('department'),
                'admission_date': p.get('admission_date') or p.get('admissionDate')
            }
            
            # Save using database module
            pid = db.save_patient(db_patient)
            if pid:
                saved_patients.append(pid)
                logger.info(f"Saved patient to database: {pid} - {p.get('name')}")
        
        # Cleanup
        try:
            os.unlink(temp_file_path)
        except:
            pass
            
        logger.info(f"CSV import complete: {len(saved_patients)} patients saved to database")
        
        return {
            "success": True,
            "message": f"Successfully imported {len(saved_patients)} patients",
            "count": len(saved_patients),
            "stats": result.get('stats', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        # Cleanup
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CHAT ENDPOINT (Ask AI) ====================

class ChatMessage(BaseModel):
    role: str
    content: str
    
class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    patient_id: Optional[str] = None # Added for user personalization

@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint using AgentManager for integrated/personalized responses"""
    try:
        if agent_manager is None:
             raise HTTPException(
                status_code=503,
                detail="Medical AI service unavailable"
            )
        
        logger.info(f"Chat request: {request.message[:100]}... (User: {request.patient_id})")
        
        # Prepare context
        user_context = {
            "conversation_history": [msg.dict() for msg in request.conversation_history],
            "patient_id": request.patient_id # Manager will fetch history using this
        }
        
        # Use AgentManager to process query
        # This automatically routes to search BUT with patient history context if available
        user_query = UserQuery(
            query_type='search', # Default to search for chat, but Manager handles it
            content=request.message,
            user_context=user_context
        )
        
        try:
            # Route through Manager (unifies logic)
            response = await agent_manager.process_query(user_query)
            
            # Extract response text
            # Depending on agent type, data structure varies slightly in our unified response
            if isinstance(response.response_data, dict):
                 # Search/Diag results usually here
                 if 'diagnostic_response' in response.response_data:
                     response_text = response.response_data['diagnostic_response']
                 elif 'response' in response.response_data:
                     response_text = response.response_data['response']
                 elif 'search_results' in response.response_data:
                     # fallback content
                     response_text = response.response_data.get('message', '') + "\n" + str(response.response_data.get('search_results', ''))
                 else:
                     # Flatten/dump provided data if no standard key
                     response_text = str(response.response_data)
            else:
                response_text = str(response.response_data)
                
            sources = response.sources or []
            
            logger.info(f"Chat response generated via Manager ({len(response_text)} chars)")
            
            return {
                "response": response_text,
                "sources": sources
            }
            

            
        except Exception as e:
            logger.error(f"Search agent error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating response: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
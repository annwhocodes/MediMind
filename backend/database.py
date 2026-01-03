import sqlite3
import json
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define database path
DB_DIR = Path(__file__).parent
DB_FILE = DB_DIR / 'patients.db'

def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create patients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                contact_number TEXT,
                email TEXT,
                address TEXT,
                medical_history TEXT,
                symptoms TEXT,
                initial_diagnosis TEXT,
                medications TEXT,
                allergies TEXT,
                admitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Active',
                bed_number TEXT,
                bed_type TEXT,
                priority TEXT,
                department TEXT,
                vitals_json TEXT,
                admission_date TEXT
            )
        ''')
        
        # Create diagnosis results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diagnosis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                primary_diagnosis TEXT,
                confidence_score REAL,
                findings_json TEXT,
                differential_diagnoses_json TEXT,
                recommendations_json TEXT,
                medications_json TEXT,
                emergency_indicators_json TEXT,
                follow_up TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
            )
        ''')

        # Create uploaded files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info(f"Database initialized at {DB_FILE}")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def save_patient(patient_data):
    """Save or update patient data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate patient_id if not present - USE MICROSECONDS TO PREVENT DUPLICATES
        if not patient_data.get('patient_id'):
            now = datetime.now()
            # Format: P + YYYYMMDDHHMMSS + Microseconds (to ensure uniqueness)
            patient_data['patient_id'] = f"P{now.strftime('%Y%m%d%H%M%S')}{now.microsecond:06d}"
        
        # DUPLICATE CHECK: Check if patient with same name and bed already exists
        if patient_data.get('name') and patient_data.get('bed_number'):
            cursor.execute('''
                SELECT patient_id FROM patients 
                WHERE name = ? AND bed_number = ?
            ''', (patient_data.get('name'), patient_data.get('bed_number')))
            existing = cursor.fetchone()
            if existing:
                logger.warning(f"Duplicate patient detected: {patient_data.get('name')} in bed {patient_data.get('bed_number')}")
                return existing[0]  # Return existing ID, don't save duplicate
            
        # Serialize vitals if present
        vitals_json = json.dumps(patient_data.get('vitals', {}))
        
        cursor.execute('''
            INSERT OR REPLACE INTO patients (
                patient_id, name, age, gender, contact_number, email, address,
                medical_history, symptoms, initial_diagnosis, medications, allergies,
                status, bed_number, bed_type, priority, department, vitals_json, admission_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            patient_data['patient_id'],
            patient_data.get('name'),
            patient_data.get('age'),
            patient_data.get('gender'),
            patient_data.get('contact_number'),
            patient_data.get('email'),
            patient_data.get('address'),
            patient_data.get('medical_history'),
            patient_data.get('symptoms'),
            patient_data.get('diagnosis'),  # Map diagnosis to initial_diagnosis
            patient_data.get('medications'),
            patient_data.get('allergies'),
            patient_data.get('status', 'Active'),
            patient_data.get('bed_number'),
            patient_data.get('bed_type', 'general'),
            patient_data.get('priority', 'normal'),
            patient_data.get('department'),
            vitals_json,
            patient_data.get('admission_date')
        ))
        
        conn.commit()
        return patient_data['patient_id']
    except Exception as e:
        logger.error(f"Error saving patient: {e}")
        return None
    finally:
        conn.close()

def get_all_patients():
    """Retrieve all patients"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM patients ORDER BY admitted_at DESC')
        patients = []
        for row in cursor.fetchall():
            p = dict(row)
            # Parse JSON fields
            if p.get('vitals_json'):
                try:
                    p['vitals'] = json.loads(p['vitals_json'])
                except:
                    p['vitals'] = {}
            patients.append(p)
        return patients
    except Exception as e:
        logger.error(f"Error getting patients: {e}")
        return []
    finally:
        conn.close()

def get_patient(patient_id):
    """Retrieve a specific patient"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
        row = cursor.fetchone()
        if row:
            p = dict(row)
            if p.get('vitals_json'):
                try:
                    p['vitals'] = json.loads(p['vitals_json'])
                except:
                    p['vitals'] = {}
            return p
        return None
    except Exception as e:
        logger.error(f"Error getting patient {patient_id}: {e}")
        return None
    finally:
        conn.close()

def delete_patient(patient_id):
    """Delete a patient"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM patients WHERE patient_id = ?', (patient_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting patient {patient_id}: {e}")
        return False
    finally:
        conn.close()

def save_diagnosis_result(patient_id, diagnosis_data):
    """Save diagnosis result"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Helper to safely dump JSON
        def safe_json(key):
            val = diagnosis_data.get(key, [])
            return json.dumps(val if val is not None else [])

        cursor.execute('''
            INSERT INTO diagnosis_results (
                patient_id, primary_diagnosis, confidence_score,
                findings_json, differential_diagnoses_json,
                recommendations_json, medications_json, 
                emergency_indicators_json, follow_up
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            patient_id,
            diagnosis_data.get('primary_diagnosis'),
            diagnosis_data.get('confidence_score'),
            safe_json('findings'),
            safe_json('differential_diagnoses'),
            safe_json('recommendations'),
            safe_json('medications'),
            safe_json('emergency_indicators'),
            diagnosis_data.get('follow_up')
        ))
        
        conn.commit()
        logger.info(f"Diagnosis saved for patient: {patient_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving diagnosis: {e}")
        return False
    finally:
        conn.close()

def get_latest_diagnosis(patient_id):
    """Get latest diagnosis for a patient"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM diagnosis_results 
            WHERE patient_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (patient_id,))
        row = cursor.fetchone()
        
        if row:
            d = dict(row)
            # Parse JSON fields
            for key in ['findings', 'differential_diagnoses', 'recommendations', 'medications', 'emergency_indicators']:
                json_key = f"{key}_json"
                if d.get(json_key):
                    try:
                        d[key] = json.loads(d[json_key])
                    except:
                        d[key] = []
            return d
        return None
    except Exception as e:
        logger.error(f"Error getting diagnosis: {e}")
        return None
    finally:
        conn.close()

def get_patient_diagnosis_history(patient_id):
    """Retrieve full diagnosis history for a patient"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM diagnosis_results 
            WHERE patient_id = ? 
            ORDER BY created_at DESC
        ''', (patient_id,))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            d = dict(row)
            # Parse JSON fields
            for key in ['findings', 'differential_diagnoses', 'recommendations', 'medications', 'emergency_indicators']:
                json_key = f"{key}_json"
                if d.get(json_key):
                    try:
                        d[key] = json.loads(d[json_key])
                    except:
                        d[key] = []
            history.append(d)
        return history
    except Exception as e:
        logger.error(f"Error getting diagnosis history: {e}")
        return []
    finally:
        conn.close()



def create_user(username, password_hash, role='user'):
    """Create a new user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"User {username} already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    """Retrieve user by username"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error getting user {username}: {e}")
        return None
    finally:
        conn.close()

# Initialize on module load
init_db()

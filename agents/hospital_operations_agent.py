import pandas as pd
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import PyPDF2
import openpyxl
from io import BytesIO
import re
from datetime import datetime
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Patient:
    name: str
    age: int
    gender: str
    bed_number: str
    bed_type: str
    status: str  # inpatient/outpatient
    priority: str  # normal/urgent/critical
    admission_date: str
    symptoms: str
    medical_history: str
    diagnosis: str
    department: str
    vitals: Optional[Dict[str, Any]] = None

class HospitalOperationsAgent:
    """Agent for processing hospital operations data from various file formats"""
    
    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls', '.pdf']
        
    def process_file(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Process uploaded file and extract hospital operations data"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.csv':
                return self._process_csv(file_path, file_content)
            elif file_extension in ['.xlsx', '.xls']:
                return self._process_excel(file_path, file_content)
            elif file_extension == '.pdf':
                return self._process_pdf(file_path, file_content)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise
    
    def _process_csv(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Process CSV file containing patient data"""
        try:
            if file_content:
                df = pd.read_csv(BytesIO(file_content))
            else:
                df = pd.read_csv(file_path)
            
            patients = self._extract_patients_from_dataframe(df)
            return self._generate_hospital_stats(patients)
            
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            raise
    
    def _process_excel(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Process Excel file containing patient data"""
        try:
            if file_content:
                df = pd.read_excel(BytesIO(file_content))
            else:
                df = pd.read_excel(file_path)
            
            patients = self._extract_patients_from_dataframe(df)
            return self._generate_hospital_stats(patients)
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            raise
    
    def _process_pdf(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Process PDF file containing patient data"""
        try:
            if file_content:
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            else:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            
            # Parse patient data from text
            patients = self._extract_patients_from_text(text)
            return self._generate_hospital_stats(patients)
            
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            raise
    
    def _extract_patients_from_dataframe(self, df: pd.DataFrame) -> List[Patient]:
        """Extract patient data from pandas DataFrame"""
        patients = []
        
        # Normalize column names (handle different naming conventions)
        df.columns = df.columns.str.lower().str.strip()
        column_mapping = {
            'patient_name': 'name',
            'patient name': 'name',
            'full_name': 'name',
            'full name': 'name',
            'bed_number': 'bed_number',
            'bed number': 'bed_number',
            'bed': 'bed_number',
            'room': 'bed_number',
            'bed_type': 'bed_type',
            'bed type': 'bed_type',
            'room_type': 'bed_type',
            'room type': 'bed_type',
            'patient_status': 'status',
            'patient status': 'status',
            'admission_status': 'status',
            'admission status': 'status',
            'priority_level': 'priority',
            'priority level': 'priority',
            'urgency': 'priority',
            'admission_date': 'admission_date',
            'admission date': 'admission_date',
            'admit_date': 'admission_date',
            'admit date': 'admission_date',
            'medical_history': 'medical_history',
            'medical history': 'medical_history',
            'history': 'medical_history',
            'dept': 'department',
            'ward': 'department'
        }
        
        # Rename columns based on mapping
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
        
        for _, row in df.iterrows():
            try:
                # Handle missing or NaN values more robustly
                age_val = row.get('age')
                if pd.isna(age_val) or age_val == '' or age_val is None:
                    age = 0
                else:
                    try:
                        age = int(float(age_val))  # Handle string numbers
                    except (ValueError, TypeError):
                        age = 0
                
                # Extract patient data with fallbacks and proper NaN handling
                patient = Patient(
                    name=str(row.get('name', f'Patient_{len(patients)+1}')) if pd.notna(row.get('name')) else f'Patient_{len(patients)+1}',
                    age=age,
                    gender=str(row.get('gender', 'Unknown')) if pd.notna(row.get('gender')) else 'Unknown',
                    bed_number=str(row.get('bed_number', 'N/A')) if pd.notna(row.get('bed_number')) else 'N/A',
                    bed_type=str(row.get('bed_type', 'general')).lower() if pd.notna(row.get('bed_type')) else 'general',
                    status=str(row.get('status', 'inpatient')).lower() if pd.notna(row.get('status')) else 'inpatient',
                    priority=str(row.get('priority', 'normal')).lower() if pd.notna(row.get('priority')) else 'normal',
                    admission_date=str(row.get('admission_date', datetime.now().strftime('%Y-%m-%d'))) if pd.notna(row.get('admission_date')) else datetime.now().strftime('%Y-%m-%d'),
                    symptoms=str(row.get('symptoms', '')) if pd.notna(row.get('symptoms')) else '',
                    medical_history=str(row.get('medical_history', '')) if pd.notna(row.get('medical_history')) else '',
                    diagnosis=str(row.get('diagnosis', 'Pending')) if pd.notna(row.get('diagnosis')) else 'Pending',
                    department=str(row.get('department', 'General')) if pd.notna(row.get('department')) else 'General',
                    vitals=self._parse_vitals(row.get('vitals', '{}'))
                )
                
                # Validate and normalize data
                patient = self._validate_patient_data(patient)
                patients.append(patient)
                
            except Exception as e:
                logger.warning(f"Error processing patient row {len(patients)+1}: {e}")
                # Still add a basic patient record to avoid losing data
                try:
                    basic_patient = Patient(
                        name=f'Patient_{len(patients)+1}',
                        age=0,
                        gender='Unknown',
                        bed_number='N/A',
                        bed_type='general',
                        status='inpatient',
                        priority='normal',
                        admission_date=datetime.now().strftime('%Y-%m-%d'),
                        symptoms='',
                        medical_history='',
                        diagnosis='Pending',
                        department='General'
                    )
                    patients.append(basic_patient)
                except:
                    continue
        
        return patients
    
    def _extract_patients_from_text(self, text: str) -> List[Patient]:
        """Extract patient data from PDF text using pattern matching"""
        patients = []
        
        # Common patterns for patient data in medical documents
        patterns = {
            'name': r'(?:Patient|Name):\s*([A-Za-z\s]+)',
            'age': r'(?:Age):\s*(\d+)',
            'gender': r'(?:Gender|Sex):\s*(Male|Female|M|F)',
            'bed': r'(?:Bed|Room):\s*([A-Za-z0-9]+)',
            'department': r'(?:Department|Ward):\s*([A-Za-z\s]+)',
            'status': r'(?:Status):\s*(inpatient|outpatient)',
            'priority': r'(?:Priority|Urgency):\s*(normal|urgent|critical)'
        }
        
        # Split text into potential patient records
        sections = re.split(r'\n\s*\n', text)
        
        for i, section in enumerate(sections):
            if len(section.strip()) < 50:  # Skip short sections
                continue
                
            patient_data = {}
            for field, pattern in patterns.items():
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    patient_data[field] = match.group(1).strip()
            
            # Only create patient if we have at least name or bed number
            if patient_data.get('name') or patient_data.get('bed'):
                patient = Patient(
                    name=patient_data.get('name', f'Patient_{i+1}'),
                    age=int(patient_data.get('age', 0)) if patient_data.get('age') else 0,
                    gender=patient_data.get('gender', 'Unknown'),
                    bed_number=patient_data.get('bed', 'N/A'),
                    bed_type='general',
                    status=patient_data.get('status', 'inpatient'),
                    priority=patient_data.get('priority', 'normal'),
                    admission_date=datetime.now().strftime('%Y-%m-%d'),
                    symptoms='',
                    medical_history='',
                    diagnosis='Pending',
                    department=patient_data.get('department', 'General')
                )
                
                patient = self._validate_patient_data(patient)
                patients.append(patient)
        
        return patients
    
    def _parse_vitals(self, vitals_str: str) -> Dict[str, Any]:
        """Parse vitals from string format"""
        try:
            if pd.isna(vitals_str) or vitals_str is None:
                return {}
            if isinstance(vitals_str, str) and vitals_str.strip():
                # Handle common JSON-like formats
                vitals_str = vitals_str.strip()
                if vitals_str.startswith('{') and vitals_str.endswith('}'):
                    return json.loads(vitals_str)
                else:
                    # Try to parse key-value pairs separated by commas
                    vitals = {}
                    pairs = vitals_str.split(',')
                    for pair in pairs:
                        if ':' in pair:
                            key, value = pair.split(':', 1)
                            vitals[key.strip()] = value.strip()
                    return vitals
            return {}
        except Exception as e:
            logger.warning(f"Error parsing vitals '{vitals_str}': {e}")
            return {}
    
    def _validate_patient_data(self, patient: Patient) -> Patient:
        """Validate and normalize patient data"""
        # Normalize status
        if patient.status.lower() in ['in', 'inpatient', 'admitted']:
            patient.status = 'inpatient'
        elif patient.status.lower() in ['out', 'outpatient', 'discharged']:
            patient.status = 'outpatient'
        else:
            patient.status = 'inpatient'
        
        # Normalize priority
        if patient.priority.lower() in ['high', 'critical', 'emergency']:
            patient.priority = 'critical'
        elif patient.priority.lower() in ['medium', 'urgent', 'moderate']:
            patient.priority = 'urgent'
        else:
            patient.priority = 'normal'
        
        # Normalize bed type
        if patient.bed_type.lower() in ['private', 'single']:
            patient.bed_type = 'private'
        elif patient.bed_type.lower() in ['semi-private', 'semi', 'double']:
            patient.bed_type = 'semi-private'
        else:
            patient.bed_type = 'general'
        
        # Ensure age is non-negative
        if patient.age < 0:
            patient.age = 0
            
        # Clean up string fields
        patient.name = patient.name.strip() if patient.name else f'Unknown_Patient'
        patient.department = patient.department.strip() if patient.department else 'General'
        
        return patient
    
    def _generate_hospital_stats(self, patients: List[Patient]) -> Dict[str, Any]:
        """Generate hospital statistics for visualization"""
        
        # Dashboard stats
        total_patients = len(patients)
        inpatients = sum(1 for p in patients if p.status == 'inpatient')
        outpatients = sum(1 for p in patients if p.status == 'outpatient')
        critical_patients = sum(1 for p in patients if p.priority == 'critical')
        unattended_patients = sum(1 for p in patients if p.diagnosis == 'Pending')
        
        # Estimate bed statistics (assuming 200 total beds)
        total_beds = 200
        occupied_beds = inpatients
        available_beds = max(0, total_beds - occupied_beds)  # Ensure non-negative
        
        dashboard_stats = {
            "total_patients": total_patients,
            "inpatients": inpatients,
            "outpatients": outpatients,
            "critical_patients": critical_patients,
            "unattended_patients": unattended_patients,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds
        }
        
        # Priority distribution for pie chart
        priority_counts = {'normal': 0, 'urgent': 0, 'critical': 0}
        for patient in patients:
            if patient.priority in priority_counts:
                priority_counts[patient.priority] += 1
            else:
                priority_counts['normal'] += 1  # Default unknown priorities to normal
        
        priority_distribution = [
            {"name": "Normal", "value": priority_counts['normal']},
            {"name": "Urgent", "value": priority_counts['urgent']},
            {"name": "Critical", "value": priority_counts['critical']}
        ]
        
        # Department statistics for pie chart
        dept_counts = {}
        for patient in patients:
            dept = patient.department.strip() if patient.department else 'General'
            if not dept:  # Handle empty departments
                dept = 'General'
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        
        department_stats = [
            {"name": dept, "value": count}
            for dept, count in dept_counts.items()
        ]
        
        # Age distribution for bar chart
        age_groups = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
        for patient in patients:
            age = max(0, patient.age)  # Ensure non-negative age
            if age <= 18:
                age_groups['0-18'] += 1
            elif age <= 35:
                age_groups['19-35'] += 1
            elif age <= 50:
                age_groups['36-50'] += 1
            elif age <= 65:
                age_groups['51-65'] += 1
            else:
                age_groups['65+'] += 1
        
        age_distribution = [
            {"age_range": age_range, "count": count}
            for age_range, count in age_groups.items()
        ]
        
        return {
            "dashboard_stats": dashboard_stats,
            "priority_distribution": priority_distribution,
            "department_stats": department_stats,
            "age_distribution": age_distribution,
            "total_patients_processed": total_patients
        }
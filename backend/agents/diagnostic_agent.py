import asyncio
import aiohttp
import json
import logging
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import PyPDF2
from pathlib import Path
import pickle
from llm_wrapper import GroqGenerativeModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch
from sentence_transformers import SentenceTransformer
import numpy as np
from search_agent import MedicalSearchAgent  # Import your existing search agent

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DiagnosticInput:
    symptoms: List[str]
    medical_history: str
    uploaded_reports: List[str]  # File paths or text content
    age: Optional[int] = None
    gender: Optional[str] = None
    vital_signs: Optional[Dict[str, float]] = None

@dataclass
class DiagnosticResult:
    primary_diagnosis: str
    confidence_score: float
    differential_diagnoses: List[Dict[str, Any]]
    severity: str  # 'normal', 'attention', 'critical'
    findings: List[str]
    recommendations: List[str]
    follow_up_questions: List[str]
    first_aid_steps: List[str]
    medications: List[Dict[str, str]]
    emergency_indicators: List[str]
    follow_up: Optional[str] = None
    sources: List[str] = None

class MedicalDiagnosticAgent:
    """Enhanced Medical Diagnostic Agent with ML models and search integration"""
    
    def __init__(self, gemini_api_key: str, google_api_key: str = None, google_cse_id: str = None):
        self.gemini_api_key = gemini_api_key
        self.gemini_model = GroqGenerativeModel(api_key=gemini_api_key)
        
        # Initialize search agent
        self.search_agent = MedicalSearchAgent(
            gemini_api_key=gemini_api_key,
            google_api_key=google_api_key,
            google_cse_id=google_cse_id
        )
        
        # Initialize medical models
        self._initialize_medical_models()
        
        # Medical knowledge base
        self.emergency_symptoms = {
            'critical': [
                'chest pain', 'difficulty breathing', 'severe bleeding', 'loss of consciousness',
                'severe head injury', 'stroke symptoms', 'heart attack', 'seizure',
                'severe allergic reaction', 'poisoning', 'severe burns'
            ],
            'urgent': [
                'high fever', 'severe pain', 'persistent vomiting', 'severe headache',
                'difficulty swallowing', 'severe diarrhea', 'fainting', 'confusion'
            ]
        }
        
        # First aid knowledge base
        self.first_aid_protocols = {
            'chest_pain': [
                "Call emergency services immediately (911/ambulance)",
                "Have the person sit down and rest",
                "Loosen tight clothing around neck and chest",
                "If prescribed, help them take nitroglycerin",
                "If unconscious and not breathing, start CPR",
                "Stay with the person until help arrives"
            ],
            'bleeding': [
                "Apply direct pressure to the wound with clean cloth",
                "Elevate the injured area above heart level if possible",
                "Do not remove embedded objects",
                "Apply additional layers if blood soaks through",
                "Seek immediate medical attention for severe bleeding"
            ],
            'fever': [
                "Monitor temperature regularly",
                "Increase fluid intake",
                "Rest in a cool, comfortable environment",
                "Use fever-reducing medication as appropriate",
                "Seek medical attention if fever exceeds 103°F (39.4°C)"
            ],
            'headache': [
                "Rest in a quiet, dark room",
                "Apply cold or warm compress to head/neck",
                "Stay hydrated",
                "Consider over-the-counter pain relievers",
                "Seek immediate care for sudden severe headache"
            ]
        }
    
    def _initialize_medical_models(self):
        """Initialize Hugging Face medical models"""
        try:
            # Medical NER model for extracting medical entities
            self.medical_ner = pipeline(
                "token-classification",
                model="d4data/biomedical-ner-all",
                tokenizer="d4data/biomedical-ner-all",
                aggregation_strategy="simple"
            )
            
            # Medical classification model
            self.medical_classifier = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english"  # You can replace with medical-specific model
            )
            
            # Sentence transformer for semantic similarity
            self.sentence_encoder = SentenceTransformer('all-MiniLM-L6-v2')
            
            logger.info("Medical models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing medical models: {e}")
            # Fallback to basic processing
            self.medical_ner = None
            self.medical_classifier = None
            self.sentence_encoder = None
    
    async def diagnose(self, diagnostic_input: DiagnosticInput) -> DiagnosticResult:
        """Main diagnostic function"""
        try:
            # Step 1: Extract and process medical information from uploaded reports
            report_analysis = await self._analyze_uploaded_reports(diagnostic_input.uploaded_reports)
            
            # Step 2: Process symptoms using NLP models
            processed_symptoms = await self._process_symptoms(diagnostic_input.symptoms)
            
            # Step 3: Search for relevant medical information
            search_query = self._build_search_query(diagnostic_input.symptoms, report_analysis)
            search_results = await self.search_agent.search_and_respond(search_query)
            
            # Step 4: Assess emergency level
            emergency_level = self._assess_emergency_level(diagnostic_input.symptoms)
            
            # Step 5: Generate comprehensive diagnosis using Gemini
            diagnosis = await self._generate_diagnosis_with_gemini(
                diagnostic_input, processed_symptoms, report_analysis, 
                search_results, emergency_level
            )
            
            # Step 6: Generate follow-up questions
            follow_up_questions = await self._generate_follow_up_questions(
                diagnostic_input, diagnosis
            )
            
            # Step 7: Add first aid and medication recommendations
            first_aid_steps = self._get_first_aid_recommendations(diagnostic_input.symptoms, emergency_level)
            medications = self._get_medication_recommendations(diagnosis, emergency_level)
            
            return DiagnosticResult(
                primary_diagnosis=diagnosis.get('primary_diagnosis', 'Unable to determine'),
                confidence_score=diagnosis.get('confidence_score', 0.5),
                differential_diagnoses=diagnosis.get('differential_diagnoses', []),
                severity=emergency_level,
                findings=diagnosis.get('findings', []),
                recommendations=diagnosis.get('recommendations', []),
                follow_up_questions=follow_up_questions,
                first_aid_steps=first_aid_steps,
                medications=medications,
                emergency_indicators=diagnosis.get('emergency_indicators', []),
                follow_up=diagnosis.get('follow_up'),
                sources=search_results.get('web_results', [])[:3]  # Top 3 sources
            )
            
        except Exception as e:
            logger.error(f"Error in diagnosis: {e}")
            return self._create_error_response(str(e))
    
    async def _analyze_uploaded_reports(self, reports: List[str]) -> Dict[str, Any]:
        """Analyze uploaded medical reports using Gemini"""
        if not reports:
            return {'findings': [], 'lab_values': {}, 'medications': [], 'diagnoses': []}
        
        analysis_results = {
            'findings': [],
            'lab_values': {},
            'medications': [],
            'diagnoses': [],
            'recommendations': []
        }
        
        for report in reports:
            try:
                # If it's a file path, read the content
                if os.path.isfile(report):
                    content = await self._extract_text_from_file(report)
                else:
                    content = report  # Assume it's already text content
                
                if content:
                    # Use Gemini to analyze the medical report
                    analysis = await self._analyze_report_with_gemini(content)
                    
                    # Merge results
                    analysis_results['findings'].extend(analysis.get('findings', []))
                    analysis_results['lab_values'].update(analysis.get('lab_values', {}))
                    analysis_results['medications'].extend(analysis.get('medications', []))
                    analysis_results['diagnoses'].extend(analysis.get('diagnoses', []))
                    analysis_results['recommendations'].extend(analysis.get('recommendations', []))
                    
            except Exception as e:
                logger.error(f"Error analyzing report {report}: {e}")
                continue
        
        return analysis_results
    
    async def _extract_text_from_file(self, file_path: str) -> str:
        """Extract text from various file formats"""
        try:
            if file_path.lower().endswith('.pdf'):
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text
            
            elif file_path.lower().endswith(('.txt', '.doc', '.docx')):
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            
            # Add support for other formats as needed
            else:
                logger.warning(f"Unsupported file format: {file_path}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    async def _analyze_report_with_gemini(self, content: str) -> Dict[str, Any]:
        """Analyze medical report content using Gemini"""
        prompt = f"""
        Analyze the following medical report and extract key information. Return the analysis in JSON format with the following structure:
        {{
            "findings": ["list of key medical findings"],
            "lab_values": {{"test_name": "value_and_range"}},
            "medications": ["list of medications mentioned"],
            "diagnoses": ["list of diagnoses or conditions mentioned"],
            "recommendations": ["list of doctor's recommendations"]
        }}
        
        Medical Report Content:
        {content[:4000]}  # Limit content to avoid token limits
        
        Please provide a thorough analysis focusing on clinically significant information.
        """
        
        try:
            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback parsing if JSON not found
                return self._parse_report_fallback(response_text)
                
        except Exception as e:
            logger.error(f"Error analyzing report with Gemini: {e}")
            return {'findings': [], 'lab_values': {}, 'medications': [], 'diagnoses': []}
    
    def _parse_report_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for medical reports"""
        return {
            'findings': [text[:200]] if text else [],
            'lab_values': {},
            'medications': [],
            'diagnoses': []
        }
    
    async def _process_symptoms(self, symptoms: List[str]) -> Dict[str, Any]:
        """Process symptoms using NLP models"""
        processed = {
            'original_symptoms': symptoms,
            'medical_entities': [],
            'symptom_categories': [],
            'severity_indicators': []
        }
        
        if not self.medical_ner or not symptoms:
            return processed
        
        try:
            # Combine symptoms into text
            symptom_text = ". ".join(symptoms)
            
            # Extract medical entities
            entities = self.medical_ner(symptom_text)
            processed['medical_entities'] = [
                {'entity': ent['word'], 'label': ent['entity_group'], 'confidence': ent['score']}
                for ent in entities if ent['score'] > 0.5
            ]
            
            # Categorize symptoms
            for symptom in symptoms:
                category = self._categorize_symptom(symptom.lower())
                if category:
                    processed['symptom_categories'].append(category)
            
            # Identify severity indicators
            severity_keywords = ['severe', 'intense', 'sharp', 'crushing', 'unbearable', 'sudden']
            for symptom in symptoms:
                if any(keyword in symptom.lower() for keyword in severity_keywords):
                    processed['severity_indicators'].append(symptom)
            
        except Exception as e:
            logger.error(f"Error processing symptoms: {e}")
        
        return processed
    
    def _categorize_symptom(self, symptom: str) -> Optional[str]:
        """Categorize symptoms by body system"""
        categories = {
            'cardiovascular': ['chest pain', 'heart', 'palpitation', 'shortness of breath'],
            'neurological': ['headache', 'dizziness', 'confusion', 'seizure', 'numbness'],
            'gastrointestinal': ['nausea', 'vomiting', 'diarrhea', 'abdominal pain'],
            'respiratory': ['cough', 'breathing', 'wheezing', 'shortness of breath'],
            'musculoskeletal': ['joint pain', 'back pain', 'muscle', 'stiffness'],
            'dermatological': ['rash', 'skin', 'itching', 'bruising']
        }
        
        for category, keywords in categories.items():
            if any(keyword in symptom for keyword in keywords):
                return category
        
        return None
    
    def _build_search_query(self, symptoms: List[str], report_analysis: Dict[str, Any]) -> str:
        """Build search query from symptoms and report analysis"""
        query_parts = []
        
        # Add primary symptoms
        if symptoms:
            query_parts.append(" ".join(symptoms[:3]))  # Top 3 symptoms
        
        # Add diagnoses from reports
        if report_analysis.get('diagnoses'):
            query_parts.append(" ".join(report_analysis['diagnoses'][:2]))
        
        # Add key findings
        if report_analysis.get('findings'):
            query_parts.append(" ".join(report_analysis['findings'][:2]))
        
        return " ".join(query_parts)[:200]  # Limit query length
    
    def _assess_emergency_level(self, symptoms: List[str]) -> str:
        """Assess emergency level based on symptoms"""
        symptom_text = " ".join(symptoms).lower()
        
        # Check for critical symptoms
        for critical_symptom in self.emergency_symptoms['critical']:
            if critical_symptom in symptom_text:
                return 'critical'
        
        # Check for urgent symptoms
        for urgent_symptom in self.emergency_symptoms['urgent']:
            if urgent_symptom in symptom_text:
                return 'attention'
        
        return 'normal'
    
    async def _generate_diagnosis_with_gemini(self, diagnostic_input: DiagnosticInput, 
                                           processed_symptoms: Dict[str, Any],
                                           report_analysis: Dict[str, Any],
                                           search_results: Dict[str, Any],
                                           emergency_level: str) -> Dict[str, Any]:
        """Generate comprehensive diagnosis using Gemini"""
        
        # Build comprehensive prompt
        prompt = f"""
        As an expert medical AI, provide a comprehensive diagnostic analysis based on the following information:

        PATIENT SYMPTOMS:
        {', '.join(diagnostic_input.symptoms)}

        MEDICAL HISTORY:
        {diagnostic_input.medical_history or 'Not provided'}

        UPLOADED REPORT ANALYSIS:
        - Findings: {', '.join(report_analysis.get('findings', []))}
        - Lab Values: {json.dumps(report_analysis.get('lab_values', {}), indent=2)}
        - Previous Diagnoses: {', '.join(report_analysis.get('diagnoses', []))}
        - Medications: {', '.join(report_analysis.get('medications', []))}

        MEDICAL LITERATURE SEARCH RESULTS:
        {search_results.get('final_response', 'No specific search results available')}

        EMERGENCY LEVEL ASSESSMENT: {emergency_level}

        Please provide a diagnostic analysis in the following JSON format:
        {{
            "primary_diagnosis": "Most likely primary diagnosis",
            "confidence_score": 0.0-1.0,
            "differential_diagnoses": [
                {{"diagnosis": "Alternative diagnosis 1", "probability": 0.0-1.0, "reasoning": "Why this is considered"}},
                {{"diagnosis": "Alternative diagnosis 2", "probability": 0.0-1.0, "reasoning": "Why this is considered"}}
            ],
            "findings": ["Key clinical findings that support the diagnosis"],
            "recommendations": ["Specific medical recommendations"],
            "emergency_indicators": ["Signs that require immediate medical attention"],
            "follow_up": "Recommended follow-up timeline and actions"
        }}

        Consider:
        1. Symptom patterns and their clinical significance
        2. Correlation with uploaded medical reports
        3. Evidence from medical literature
        4. Potential red flags or emergency indicators
        5. Most appropriate next steps for patient care

        IMPORTANT: This is for informational purposes only and should not replace professional medical consultation.
        """
        
        try:
            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                diagnosis_data = json.loads(json_match.group())
                return diagnosis_data
            else:
                # Fallback if JSON parsing fails
                return self._parse_diagnosis_fallback(response_text)
                
        except Exception as e:
            logger.error(f"Error generating diagnosis with Gemini: {e}")
            return self._create_fallback_diagnosis(diagnostic_input.symptoms)
    
    def _parse_diagnosis_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback diagnosis parsing"""
        return {
            'primary_diagnosis': 'Requires further medical evaluation',
            'confidence_score': 0.3,
            'differential_diagnoses': [],
            'findings': [text[:300]] if text else [],
            'recommendations': ['Consult with healthcare provider for proper evaluation'],
            'emergency_indicators': [],
            'follow_up': 'Schedule appointment with healthcare provider within 1-2 weeks'
        }
    
    def _create_fallback_diagnosis(self, symptoms: List[str]) -> Dict[str, Any]:
        """Create fallback diagnosis when AI processing fails"""
        return {
            'primary_diagnosis': 'Unable to determine - requires medical evaluation',
            'confidence_score': 0.1,
            'differential_diagnoses': [],
            'findings': [f'Patient reports: {", ".join(symptoms)}'],
            'recommendations': [
                'Seek immediate medical evaluation',
                'Provide complete symptom history to healthcare provider',
                'Monitor symptoms and seek emergency care if they worsen'
            ],
            'emergency_indicators': ['Any worsening of current symptoms'],
            'follow_up': 'Immediate medical consultation recommended'
        }
    
    async def _generate_follow_up_questions(self, diagnostic_input: DiagnosticInput, 
                                          diagnosis: Dict[str, Any]) -> List[str]:
        """Generate relevant follow-up questions"""
        prompt = f"""
        Based on the patient's symptoms: {', '.join(diagnostic_input.symptoms)}
        And the preliminary diagnosis: {diagnosis.get('primary_diagnosis', 'Unknown')}
        
        Generate 3-5 relevant follow-up questions that would help clarify the diagnosis or assess symptom severity.
        
        Return as a simple list of questions, one per line.
        Focus on:
        1. Symptom duration and progression
        2. Associated symptoms
        3. Aggravating or relieving factors
        4. Impact on daily activities
        5. Previous similar episodes
        """
        
        try:
            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            questions = [q.strip() for q in response.text.split('\n') if q.strip() and '?' in q]
            return questions[:5]  # Return max 5 questions
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {e}")
            return self._get_default_follow_up_questions()
    
    def _get_default_follow_up_questions(self) -> List[str]:
        """Default follow-up questions"""
        return [
            "How long have you been experiencing these symptoms?",
            "Have the symptoms gotten worse, better, or stayed the same?",
            "Are there any activities that make the symptoms better or worse?",
            "Have you experienced similar symptoms before?",
            "Are you currently taking any medications?"
        ]
    
    def _get_first_aid_recommendations(self, symptoms: List[str], emergency_level: str) -> List[str]:
        """Get first aid recommendations based on symptoms"""
        if emergency_level == 'critical':
            return [
                "🚨 CALL EMERGENCY SERVICES IMMEDIATELY (911)",
                "Do not leave the person alone",
                "Follow dispatcher instructions",
                "Prepare to perform CPR if needed",
                "Gather medical history and medications for emergency responders"
            ]
        
        first_aid_steps = []
        symptom_text = " ".join(symptoms).lower()
        
        # Match symptoms to first aid protocols
        for condition, steps in self.first_aid_protocols.items():
            if any(keyword in symptom_text for keyword in condition.split('_')):
                first_aid_steps.extend(steps)
        
        # Generic first aid if no specific match
        if not first_aid_steps:
            first_aid_steps = [
                "Ensure the person is in a comfortable, safe position",
                "Monitor vital signs if possible",
                "Keep the person calm and reassured",
                "Do not give food or water unless specifically indicated",
                "Seek medical attention if symptoms worsen"
            ]
        
        return list(set(first_aid_steps))[:6]  # Remove duplicates and limit to 6 steps
    
    def _get_medication_recommendations(self, diagnosis: Dict[str, Any], emergency_level: str) -> List[Dict[str, str]]:
        """Get basic medication recommendations (OTC only for non-critical cases)"""
        if emergency_level == 'critical':
            return [{
                'medication': 'No self-medication',
                'dosage': 'N/A',
                'instructions': 'Seek immediate emergency medical care',
                'warning': 'Do not take any medications without emergency medical guidance'
            }]
        
        # Very basic OTC recommendations - should be expanded with proper medical knowledge
        basic_medications = [
            {
                'medication': 'Acetaminophen/Paracetamol',
                'dosage': '500-1000mg every 6-8 hours',
                'instructions': 'For pain and fever relief. Do not exceed 4000mg per day.',
                'warning': 'Avoid if you have liver problems or are taking other medications containing acetaminophen'
            },
            {
                'medication': 'Ibuprofen',
                'dosage': '200-400mg every 6-8 hours',
                'instructions': 'For pain, inflammation, and fever. Take with food.',
                'warning': 'Avoid if you have stomach ulcers, kidney problems, or are taking blood thinners'
            }
        ]
        
        return basic_medications[:2]  # Return max 2 basic recommendations
    
    def _create_error_response(self, error_message: str) -> DiagnosticResult:
        """Create error response when diagnosis fails"""
        return DiagnosticResult(
            primary_diagnosis='Unable to process - technical error',
            confidence_score=0.0,
            differential_diagnoses=[],
            severity='attention',
            findings=[f'Error occurred: {error_message}'],
            recommendations=[
                'Please try again',
                'If problem persists, seek direct medical consultation',
                'Ensure all uploaded files are in supported formats'
            ],
            follow_up_questions=[
                'Are you experiencing any emergency symptoms?',
                'Do you need immediate medical attention?'
            ],
            first_aid_steps=[
                'If experiencing emergency symptoms, call 911 immediately',
                'Monitor your condition closely',
                'Seek medical attention if symptoms worsen'
            ],
            medications=[],
            emergency_indicators=['Any sudden worsening of symptoms'],
            follow_up='Seek medical consultation as soon as possible'
        )
import requests
gemini_key = os.getenv("GEMINI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")         # optional
google_cse_id = os.getenv("GOOGLE_CSE_ID") 

# url = "https://www.googleapis.com/customsearch/v1"
# params = {
#     "q": "test search",
#     "key": google_key,
#     "cx": google_cse_id
# }

# response = requests.get(url, params=params)
# print(response.status_code)
# print(response.json())
async def main():
    # Load your API keys from environment (or set them here directly)
    gemini_key = os.getenv("GEMINI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")         # optional
    google_cse_id = os.getenv("GOOGLE_CSE_ID")       # optional

    # Instantiate the diagnostic agent
    agent = MedicalDiagnosticAgent(
        gemini_api_key=gemini_key,
        google_api_key=google_key,
        google_cse_id=google_cse_id
    )

    # Prepare a sample patient case
    diag_input = DiagnosticInput(
        symptoms=[
            "Severe headache for 3 days",
            "Nausea and occasional vomiting",
            "Light sensitivity"
        ],
        medical_history="Patient has a history of migraine since age 20. No known drug allergies.",
        uploaded_reports=[],  # e.g., ["reports/labs.pdf"] or raw text snippets
        age=29,
        gender="Female",
        vital_signs={
            "temperature": 37.8,
            "blood_pressure_systolic": 120,
            "blood_pressure_diastolic": 80,
            "heart_rate": 78
        }
    )

    # Run the diagnosis
    result = await agent.diagnose(diag_input)

    # Print out the structured result
    print("Primary Diagnosis:", result.primary_diagnosis)
    print("Confidence Score:", result.confidence_score)
    print("Severity Level:", result.severity)
    print("\nKey Findings:")
    for f in result.findings:
        print(" -", f)
    print("\nRecommendations:")
    for r in result.recommendations:
        print(" -", r)
    print("\nFirst-Aid Steps:")
    for step in result.first_aid_steps:
        print(" -", step)
    print("\nFollow-Up Questions:")
    for q in result.follow_up_questions:
        print(" -", q)
    print("\nMedication Suggestions:")
    for med in result.medications:
        print(f" • {med['medication']} — {med['dosage']} ({med['instructions']})")
    print("\nEmergency Indicators:")
    for ei in result.emergency_indicators:
        print(" -", ei)
    print("\nSources:")
    for src in result.sources:
        print(" -", src)

if __name__ == "__main__":
    asyncio.run(main())
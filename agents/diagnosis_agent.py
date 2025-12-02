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

# Import your updated search agent
from search_agent import MedicalSearchAgent  # This should be your updated search agent

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
    sources: List[Dict[str, str]] = None
    search_context: Optional[str] = None

class MedicalDiagnosticAgent:
    """Enhanced Medical Diagnostic Agent with Ollama + Search Integration"""
    
    def __init__(self, google_api_key: str, google_cse_id: str):
        # Initialize search agent with Ollama integration
        self.search_agent = MedicalSearchAgent(
            google_api_key=google_api_key,
            google_cse_id=google_cse_id
        )
        
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
        
        logger.info("Medical Diagnostic Agent initialized with Ollama + Search integration")
    
    async def diagnose(self, diagnostic_input: DiagnosticInput) -> DiagnosticResult:
        """Main diagnostic function using search agent for enhanced accuracy"""
        try:
            logger.info(f"Starting diagnosis for patient with symptoms: {diagnostic_input.symptoms}")
            
            # Step 1: Build comprehensive search query
            search_query = self._build_diagnostic_query(diagnostic_input)
            
            # Step 2: Search for relevant medical information
            diagnostic_context = self._create_diagnostic_context(diagnostic_input)
            search_results = await self.search_agent.search(search_query, diagnostic_context)
            
            # Step 3: Assess emergency level
            emergency_level = self._assess_emergency_level(diagnostic_input.symptoms)
            
            # Step 4: Process uploaded reports (if any)
            report_analysis = await self._analyze_uploaded_reports(diagnostic_input.uploaded_reports)
            
            # Step 5: Generate comprehensive diagnosis using search results
            diagnosis = await self._generate_comprehensive_diagnosis(
                diagnostic_input, 
                search_results, 
                emergency_level,
                report_analysis
            )
            
            # Step 6: Generate follow-up questions
            follow_up_questions = await self._generate_follow_up_questions(
                diagnostic_input, 
                diagnosis,
                search_results
            )
            
            # Step 7: Add first aid and medication recommendations
            first_aid_steps = self._get_first_aid_recommendations(diagnostic_input.symptoms, emergency_level)
            medications = self._get_medication_recommendations(diagnosis, emergency_level)
            
            # Step 8: Extract sources from search results
            sources = self._extract_sources_from_search(search_results)
            
            return DiagnosticResult(
                primary_diagnosis=diagnosis.get('primary_diagnosis', 'Requires further evaluation'),
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
                sources=sources,
                search_context=search_results.get('diagnostic_response', '')[:1000]  # Truncated for display
            )
            
        except Exception as e:
            logger.error(f"Error in diagnosis: {e}")
            return self._create_error_response(str(e))
    
    def _build_diagnostic_query(self, diagnostic_input: DiagnosticInput) -> str:
        """Build comprehensive search query for diagnosis"""
        query_parts = []
        
        # Add symptoms
        if diagnostic_input.symptoms:
            query_parts.append("differential diagnosis for " + ", ".join(diagnostic_input.symptoms))
        
        # Add demographic information if available
        if diagnostic_input.age and diagnostic_input.gender:
            query_parts.append(f"in {diagnostic_input.age} year old {diagnostic_input.gender}")
        
        # Add medical history keywords
        if diagnostic_input.medical_history:
            # Extract key terms from medical history
            key_terms = self._extract_key_terms(diagnostic_input.medical_history)
            if key_terms:
                query_parts.append("with history of " + ", ".join(key_terms[:3]))
        
        # Add vital signs if abnormal
        if diagnostic_input.vital_signs:
            abnormal_vitals = self._identify_abnormal_vitals(diagnostic_input.vital_signs)
            if abnormal_vitals:
                query_parts.append("with " + ", ".join(abnormal_vitals))
        
        query = " ".join(query_parts)
        
        # Add specific medical context
        if 'chest pain' in query.lower():
            query += " cardiac pulmonary gastrointestinal causes"
        elif 'headache' in query.lower():
            query += " migraine tension cluster causes"
        elif 'fever' in query.lower():
            query += " infectious inflammatory causes"
        
        return query[:200]  # Limit query length
    
    def _extract_key_terms(self, medical_history: str) -> List[str]:
        """Extract key medical terms from history"""
        # Simple extraction - you can enhance this with NER
        common_conditions = [
            'diabetes', 'hypertension', 'asthma', 'migraine', 'arthritis',
            'heart disease', 'kidney disease', 'liver disease', 'cancer',
            'thyroid', 'depression', 'anxiety', 'allergies'
        ]
        
        found_terms = []
        medical_history_lower = medical_history.lower()
        
        for condition in common_conditions:
            if condition in medical_history_lower:
                found_terms.append(condition)
        
        return found_terms
    
    def _identify_abnormal_vitals(self, vital_signs: Dict[str, float]) -> List[str]:
        """Identify abnormal vital signs"""
        abnormal = []
        
        if 'temperature' in vital_signs:
            temp = vital_signs['temperature']
            if temp > 38.0:  # Fever
                abnormal.append(f"fever {temp}°C")
            elif temp < 36.0:  # Hypothermia
                abnormal.append(f"low temperature {temp}°C")
        
        if 'blood_pressure_systolic' in vital_signs and 'blood_pressure_diastolic' in vital_signs:
            systolic = vital_signs['blood_pressure_systolic']
            diastolic = vital_signs['blood_pressure_diastolic']
            
            if systolic > 140 or diastolic > 90:
                abnormal.append(f"high blood pressure {systolic}/{diastolic}")
            elif systolic < 90 or diastolic < 60:
                abnormal.append(f"low blood pressure {systolic}/{diastolic}")
        
        if 'heart_rate' in vital_signs:
            hr = vital_signs['heart_rate']
            if hr > 100:
                abnormal.append(f"tachycardia {hr} bpm")
            elif hr < 60:
                abnormal.append(f"bradycardia {hr} bpm")
        
        return abnormal
    
    def _create_diagnostic_context(self, diagnostic_input: DiagnosticInput) -> Dict[str, Any]:
        """Create diagnostic context for search agent"""
        context = {
            "symptoms": diagnostic_input.symptoms,
            "medical_history": diagnostic_input.medical_history
        }
        
        if diagnostic_input.age:
            context["patient_age"] = diagnostic_input.age
        if diagnostic_input.gender:
            context["patient_gender"] = diagnostic_input.gender
        if diagnostic_input.vital_signs:
            context["vital_signs"] = diagnostic_input.vital_signs
        
        return context
    
    async def _analyze_uploaded_reports(self, reports: List[str]) -> Dict[str, Any]:
        """Analyze uploaded medical reports"""
        if not reports:
            return {'findings': [], 'lab_values': {}, 'medications': [], 'diagnoses': []}
        
        analysis_results = {
            'findings': [],
            'lab_values': {},
            'medications': [],
            'diagnoses': []
        }
        
        for report in reports:
            try:
                # If it's a file path, read the content
                if os.path.isfile(report):
                    content = await self._extract_text_from_file(report)
                else:
                    content = report  # Assume it's already text content
                
                if content:
                    # Simple text analysis - can be enhanced
                    analysis = self._simple_report_analysis(content)
                    
                    # Merge results
                    analysis_results['findings'].extend(analysis.get('findings', []))
                    analysis_results['lab_values'].update(analysis.get('lab_values', {}))
                    analysis_results['medications'].extend(analysis.get('medications', []))
                    analysis_results['diagnoses'].extend(analysis.get('diagnoses', []))
                    
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
            
            elif file_path.lower().endswith(('.txt', '.md')):
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            
            else:
                logger.warning(f"Unsupported file format: {file_path}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    def _simple_report_analysis(self, content: str) -> Dict[str, Any]:
        """Simple analysis of medical report content"""
        findings = []
        lab_values = {}
        medications = []
        diagnoses = []
        
        content_lower = content.lower()
        
        # Look for common patterns
        lines = content.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            # Look for lab values
            if any(term in line_lower for term in ['wbc', 'rbc', 'hgb', 'hct', 'glucose', 'creatinine', 'sodium', 'potassium']):
                lab_values[line[:50]] = line
            
            # Look for medications
            medication_keywords = ['mg', 'tablet', 'capsule', 'injection', 'dose']
            if any(keyword in line_lower for keyword in medication_keywords):
                medications.append(line.strip()[:100])
            
            # Look for diagnoses
            diagnosis_keywords = ['diagnosis:', 'dx:', 'impression:', 'finding:']
            if any(keyword in line_lower for keyword in diagnosis_keywords):
                diagnoses.append(line.strip()[:200])
        
        # If no specific findings, use first few lines
        if not findings and content:
            findings = [content[:300]]
        
        return {
            'findings': findings[:5],
            'lab_values': lab_values,
            'medications': medications[:10],
            'diagnoses': diagnoses[:5]
        }
    
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
    
    async def _generate_comprehensive_diagnosis(self, diagnostic_input: DiagnosticInput,
                                              search_results: Dict[str, Any],
                                              emergency_level: str,
                                              report_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive diagnosis using search results"""
        
        # Extract key information from search results
        search_response = search_results.get('diagnostic_response', '')
        sources = search_results.get('sources', [])
        
        # Prepare structured diagnosis data
        diagnosis_data = {
            'primary_diagnosis': '',
            'confidence_score': 0.7,  # Base confidence
            'differential_diagnoses': [],
            'findings': [],
            'recommendations': [],
            'emergency_indicators': [],
            'follow_up': ''
        }
        
        # Extract primary diagnosis from search response
        diagnosis_data['primary_diagnosis'] = self._extract_primary_diagnosis(
            search_response, diagnostic_input.symptoms
        )
        
        # Extract findings from search results and report analysis
        diagnosis_data['findings'] = self._extract_findings(
            search_response, report_analysis, diagnostic_input
        )
        
        # Generate differential diagnoses
        diagnosis_data['differential_diagnoses'] = self._generate_differential_diagnoses(
            diagnostic_input, search_response
        )
        
        # Generate recommendations
        diagnosis_data['recommendations'] = self._generate_recommendations(
            diagnosis_data['primary_diagnosis'], emergency_level, report_analysis
        )
        
        # Adjust confidence based on information quality
        diagnosis_data['confidence_score'] = self._calculate_confidence(
            search_results, report_analysis, diagnostic_input
        )
        
        # Set emergency indicators
        if emergency_level != 'normal':
            diagnosis_data['emergency_indicators'] = self._identify_emergency_indicators(
                diagnostic_input.symptoms
            )
        
        # Set follow-up timeline
        diagnosis_data['follow_up'] = self._determine_follow_up(emergency_level)
        
        return diagnosis_data
    
    def _extract_primary_diagnosis(self, search_response: str, symptoms: List[str]) -> str:
        """Extract primary diagnosis from search response"""
        # Look for patterns indicating a diagnosis
        diagnosis_patterns = [
            r'likely.*?(?:is|are)\s+([^.,]+)',
            r'probable.*?diagnosis.*?is\s+([^.,]+)',
            r'suggests.*?([^.,]+)',
            r'indicates.*?([^.,]+)'
        ]
        
        for pattern in diagnosis_patterns:
            matches = re.findall(pattern, search_response, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        # If no pattern found, create a diagnosis based on symptoms
        symptom_text = ", ".join(symptoms).lower()
        
        if 'chest pain' in symptom_text:
            return "Possible cardiac or gastrointestinal condition requiring evaluation"
        elif 'headache' in symptom_text and 'nausea' in symptom_text:
            return "Migraine or tension-type headache"
        elif 'fever' in symptom_text and 'cough' in symptom_text:
            return "Respiratory tract infection"
        else:
            return f"Condition presenting with {symptoms[0] if symptoms else 'symptoms'}"
    
    def _extract_findings(self, search_response: str, report_analysis: Dict[str, Any], 
                         diagnostic_input: DiagnosticInput) -> List[str]:
        """Extract findings from search results and reports"""
        findings = []
        
        # Add findings from search response (first few sentences)
        sentences = re.split(r'[.!?]+', search_response)
        for sentence in sentences[:3]:
            if len(sentence.strip()) > 20:  # Meaningful sentences
                findings.append(sentence.strip())
        
        # Add findings from report analysis
        findings.extend(report_analysis.get('findings', [])[:2])
        
        # Add findings from symptoms
        if diagnostic_input.symptoms:
            findings.append(f"Patient reports: {', '.join(diagnostic_input.symptoms[:3])}")
        
        # Add demographic findings
        if diagnostic_input.age and diagnostic_input.gender:
            findings.append(f"{diagnostic_input.age} year old {diagnostic_input.gender}")
        
        # Add vital sign findings
        if diagnostic_input.vital_signs:
            vital_info = []
            for key, value in diagnostic_input.vital_signs.items():
                vital_info.append(f"{key}: {value}")
            findings.append(f"Vitals: {', '.join(vital_info[:3])}")
        
        return findings[:6]  # Limit to 6 findings
    
    def _generate_differential_diagnoses(self, diagnostic_input: DiagnosticInput, 
                                       search_response: str) -> List[Dict[str, Any]]:
        """Generate differential diagnoses"""
        differentials = []
        
        # Common differentials based on symptoms
        symptom_text = " ".join(diagnostic_input.symptoms).lower()
        
        if 'chest pain' in symptom_text:
            differentials.extend([
                {"diagnosis": "Angina Pectoris", "probability": 0.4, "reasoning": "Cardiac chest pain pattern"},
                {"diagnosis": "Gastroesophageal Reflux Disease", "probability": 0.3, "reasoning": "Acid-related chest discomfort"},
                {"diagnosis": "Costochondritis", "probability": 0.2, "reasoning": "Musculoskeletal chest wall pain"},
                {"diagnosis": "Pulmonary Embolism", "probability": 0.1, "reasoning": "Emergency condition requiring exclusion"}
            ])
        elif 'headache' in symptom_text:
            differentials.extend([
                {"diagnosis": "Migraine", "probability": 0.5, "reasoning": "Recurrent headache with possible aura"},
                {"diagnosis": "Tension-Type Headache", "probability": 0.3, "reasoning": "Stress-related headache"},
                {"diagnosis": "Sinusitis", "probability": 0.2, "reasoning": "Facial pressure and congestion"}
            ])
        elif 'abdominal pain' in symptom_text:
            differentials.extend([
                {"diagnosis": "Gastritis", "probability": 0.4, "reasoning": "Upper abdominal discomfort"},
                {"diagnosis": "Irritable Bowel Syndrome", "probability": 0.3, "reasoning": "Chronic abdominal pain with bowel changes"},
                {"diagnosis": "Appendicitis", "probability": 0.1, "reasoning": "Emergency condition if right lower quadrant pain"}
            ])
        else:
            # Generic differentials
            differentials.append({
                "diagnosis": "Requires medical evaluation",
                "probability": 0.9,
                "reasoning": "Insufficient information for specific diagnosis"
            })
        
        return differentials[:4]  # Limit to 4 differential diagnoses
    
    def _generate_recommendations(self, primary_diagnosis: str, emergency_level: str,
                                report_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on diagnosis and emergency level"""
        recommendations = []
        
        # Emergency level-based recommendations
        if emergency_level == 'critical':
            recommendations.append("🚨 SEEK EMERGENCY MEDICAL CARE IMMEDIATELY")
            recommendations.append("Call 911 or go to nearest emergency department")
        elif emergency_level == 'attention':
            recommendations.append("Schedule urgent medical evaluation within 24 hours")
            recommendations.append("Monitor symptoms closely for any worsening")
        else:
            recommendations.append("Schedule appointment with healthcare provider within 1-2 weeks")
        
        # Diagnosis-specific recommendations
        diagnosis_lower = primary_diagnosis.lower()
        
        if any(term in diagnosis_lower for term in ['migraine', 'headache']):
            recommendations.append("Consider keeping headache diary to identify triggers")
            recommendations.append("Avoid known migraine triggers (caffeine, stress, certain foods)")
        
        if any(term in diagnosis_lower for term in ['infection', 'fever']):
            recommendations.append("Increase fluid intake and rest")
            recommendations.append("Monitor temperature every 4-6 hours")
        
        if any(term in diagnosis_lower for term in ['cardiac', 'chest']):
            recommendations.append("Avoid strenuous activity until evaluated")
            recommendations.append("Learn to recognize cardiac emergency symptoms")
        
        # General recommendations
        recommendations.append("Bring all current medications to medical appointment")
        recommendations.append("Prepare list of symptoms, their onset and duration")
        
        # Add recommendations from report analysis if available
        if report_analysis.get('recommendations'):
            recommendations.extend(report_analysis['recommendations'][:2])
        
        return list(set(recommendations))[:8]  # Remove duplicates and limit
    
    def _calculate_confidence(self, search_results: Dict[str, Any], 
                            report_analysis: Dict[str, Any],
                            diagnostic_input: DiagnosticInput) -> float:
        """Calculate confidence score based on available information"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on search results quality
        search_quality = search_results.get('search_results', {})
        google_results = search_quality.get('google_cse_results', 0)
        semantic_results = search_quality.get('semantic_results', 0)
        
        if google_results >= 2:
            confidence += 0.2
        if semantic_results >= 2:
            confidence += 0.1
        
        # Increase confidence based on available information
        if diagnostic_input.symptoms and len(diagnostic_input.symptoms) >= 2:
            confidence += 0.1
        
        if diagnostic_input.age and diagnostic_input.gender:
            confidence += 0.05
        
        if report_analysis.get('findings'):
            confidence += 0.1
        
        if diagnostic_input.vital_signs:
            confidence += 0.05
        
        # Cap at 0.95 to acknowledge AI limitations
        return min(confidence, 0.95)
    
    def _identify_emergency_indicators(self, symptoms: List[str]) -> List[str]:
        """Identify specific emergency indicators from symptoms"""
        indicators = []
        symptom_text = " ".join(symptoms).lower()
        
        emergency_keywords = {
            'chest pain': 'cardiac emergency',
            'difficulty breathing': 'respiratory emergency',
            'severe headache': 'possible neurological emergency',
            'loss of consciousness': 'serious medical condition',
            'severe bleeding': 'hemorrhagic emergency'
        }
        
        for keyword, indicator in emergency_keywords.items():
            if keyword in symptom_text:
                indicators.append(indicator)
        
        return indicators[:3]
    
    def _determine_follow_up(self, emergency_level: str) -> str:
        """Determine follow-up timeline"""
        if emergency_level == 'critical':
            return "Immediate emergency department evaluation required"
        elif emergency_level == 'attention':
            return "Urgent care or same-day appointment recommended"
        else:
            return "Primary care follow-up within 1-2 weeks"
    
    async def _generate_follow_up_questions(self, diagnostic_input: DiagnosticInput,
                                          diagnosis: Dict[str, Any],
                                          search_results: Dict[str, Any]) -> List[str]:
        """Generate relevant follow-up questions"""
        questions = []
        
        # Symptom-specific questions
        if diagnostic_input.symptoms:
            for symptom in diagnostic_input.symptoms[:2]:
                questions.append(f"How severe is the {symptom} on a scale of 1-10?")
                questions.append(f"What makes the {symptom} better or worse?")
        
        # Time-related questions
        questions.append("When did the symptoms first start?")
        questions.append("Have the symptoms been getting better, worse, or staying the same?")
        
        # Context questions
        questions.append("Have you had similar symptoms before?")
        questions.append("Are there any other symptoms you're experiencing?")
        
        # Medical history questions
        if not diagnostic_input.medical_history or len(diagnostic_input.medical_history) < 20:
            questions.append("Do you have any chronic medical conditions?")
            questions.append("Are you currently taking any medications?")
        
        return questions[:6]  # Limit to 6 questions
    
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
            condition_keywords = condition.split('_')
            if any(keyword in symptom_text for keyword in condition_keywords):
                first_aid_steps.extend(steps)
        
        # Generic first aid if no specific match
        if not first_aid_steps:
            first_aid_steps = [
                "Ensure the person is in a comfortable, safe position",
                "Monitor for any worsening of symptoms",
                "Keep the person calm and reassured",
                "Do not give food or water unless specifically indicated",
                "Seek medical attention if symptoms worsen"
            ]
        
        return list(set(first_aid_steps))[:6]
    
    def _get_medication_recommendations(self, diagnosis: Dict[str, Any], emergency_level: str) -> List[Dict[str, str]]:
        """Get basic medication recommendations"""
        if emergency_level == 'critical':
            return [{
                'medication': 'No self-medication',
                'dosage': 'N/A',
                'instructions': 'Wait for emergency medical evaluation',
                'warning': 'Do not take any medications without emergency medical guidance'
            }]
        
        # Basic OTC recommendations for common symptoms
        medications = []
        primary_diagnosis = diagnosis.get('primary_diagnosis', '').lower()
        
        if any(term in primary_diagnosis for term in ['headache', 'migraine', 'pain']):
            medications.append({
                'medication': 'Acetaminophen (Paracetamol)',
                'dosage': '500-1000mg every 6-8 hours',
                'instructions': 'For pain relief. Do not exceed 4000mg per day.',
                'warning': 'Avoid with liver disease or alcohol use'
            })
        
        if any(term in primary_diagnosis for term in ['fever', 'inflammation']):
            medications.append({
                'medication': 'Ibuprofen',
                'dosage': '200-400mg every 6-8 hours',
                'instructions': 'For fever and pain. Take with food.',
                'warning': 'Avoid with stomach ulcers, kidney problems, or bleeding disorders'
            })
        
        if not medications:
            medications.append({
                'medication': 'Consult pharmacist/doctor',
                'dosage': 'N/A',
                'instructions': 'Speak with healthcare professional before taking any medication',
                'warning': 'Self-medication without proper diagnosis can be harmful'
            })
        
        return medications[:2]
    
    def _extract_sources_from_search(self, search_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract sources from search results"""
        sources = []
        
        # Extract from search results
        if 'sources' in search_results:
            for source in search_results['sources'][:3]:  # Top 3 sources
                if isinstance(source, str):
                    sources.append({'name': source, 'type': 'medical_source'})
                elif isinstance(source, dict):
                    sources.append({
                        'name': source.get('name', 'Medical Source'),
                        'type': source.get('type', 'reference'),
                        'url': source.get('url', '')
                    })
        
        # Add search agent info
        agent_info = self.search_agent.get_agent_info()
        sources.append({
            'name': f"Medical Search Agent ({agent_info.get('llm_model', 'Ollama')})",
            'type': 'ai_analysis',
            'description': 'AI-powered medical information synthesis'
        })
        
        return sources[:5]
    
    def _create_error_response(self, error_message: str) -> DiagnosticResult:
        """Create error response when diagnosis fails"""
        return DiagnosticResult(
            primary_diagnosis='Diagnostic processing error',
            confidence_score=0.0,
            differential_diagnoses=[],
            severity='attention',
            findings=[f'Technical error occurred: {error_message}'],
            recommendations=[
                'Please try submitting your symptoms again',
                'If problem persists, seek direct medical consultation',
                'Ensure all information is entered correctly'
            ],
            follow_up_questions=[
                'Are you experiencing emergency symptoms?',
                'Do you need immediate medical attention?'
            ],
            first_aid_steps=[
                'If experiencing emergency symptoms, call 911 immediately',
                'Monitor your condition closely',
                'Seek medical attention if symptoms worsen'
            ],
            medications=[],
            emergency_indicators=['Any sudden worsening of symptoms'],
            follow_up='Seek medical consultation as soon as possible',
            sources=[{'name': 'System Error', 'type': 'error'}]
        )
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get diagnostic agent information"""
        return {
            'agent_name': 'Medical Diagnostic Agent',
            'description': 'AI-powered diagnostic assistant using search integration',
            'components': {
                'search_integration': 'Active (Ollama + Google CSE)',
                'emergency_assessment': 'Enabled',
                'report_analysis': 'Basic',
                'follow_up_generation': 'Enabled'
            },
            'search_agent_info': self.search_agent.get_agent_info() if hasattr(self.search_agent, 'get_agent_info') else {}
        }

# Example usage with backend/frontend integration
async def main():
    """Example usage demonstrating backend integration"""
    
    # Load API keys from environment
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("Error: Google API credentials not found")
        return
    
    # Initialize diagnostic agent
    print("Initializing Diagnostic Agent...")
    diagnostic_agent = MedicalDiagnosticAgent(
        google_api_key=GOOGLE_API_KEY,
        google_cse_id=GOOGLE_CSE_ID
    )
    
    # Example patient case (simulating frontend input)
    patient_input = DiagnosticInput(
        symptoms=[
            "Severe headache for 3 days",
            "Nausea and vomiting",
            "Light sensitivity",
            "Neck stiffness"
        ],
        medical_history="History of migraines since age 25. No known drug allergies.",
        uploaded_reports=[],  # Can add file paths here
        age=32,
        gender="Female",
        vital_signs={
            "temperature": 38.2,
            "blood_pressure_systolic": 135,
            "blood_pressure_diastolic": 85,
            "heart_rate": 92
        }
    )
    
    print(f"\n{'='*80}")
    print("MEDICAL DIAGNOSTIC AGENT - DIAGNOSIS REPORT")
    print(f"{'='*80}")
    
    # Run diagnosis
    result = await diagnostic_agent.diagnose(patient_input)
    
    # Display structured results (simulating frontend display)
    print(f"\n📋 PATIENT SUMMARY:")
    print(f"   Age: {patient_input.age} | Gender: {patient_input.gender}")
    print(f"   Symptoms: {', '.join(patient_input.symptoms)}")
    
    print(f"\n🔴 EMERGENCY ASSESSMENT:")
    print(f"   Severity Level: {result.severity.upper()}")
    if result.emergency_indicators:
        print(f"   Emergency Indicators: {', '.join(result.emergency_indicators)}")
    
    print(f"\n🩺 DIAGNOSIS:")
    print(f"   Primary: {result.primary_diagnosis}")
    print(f"   Confidence: {result.confidence_score:.0%}")
    
    print(f"\n📊 DIFFERENTIAL DIAGNOSES:")
    for diff in result.differential_diagnoses[:3]:
        print(f"   • {diff['diagnosis']} ({diff['probability']:.0%} probability)")
        print(f"     Reasoning: {diff['reasoning']}")
    
    print(f"\n🔍 KEY FINDINGS:")
    for finding in result.findings:
        print(f"   • {finding}")
    
    print(f"\n✅ RECOMMENDATIONS:")
    for rec in result.recommendations:
        print(f"   • {rec}")
    
    print(f"\n🩹 FIRST AID / IMMEDIATE CARE:")
    for step in result.first_aid_steps:
        print(f"   • {step}")
    
    print(f"\n💊 MEDICATION SUGGESTIONS:")
    for med in result.medications:
        print(f"   • {med['medication']}: {med['dosage']}")
        print(f"     Instructions: {med['instructions']}")
        print(f"     ⚠️  {med['warning']}")
    
    print(f"\n❓ FOLLOW-UP QUESTIONS:")
    for q in result.follow_up_questions:
        print(f"   • {q}")
    
    print(f"\n📅 FOLLOW-UP:")
    print(f"   {result.follow_up}")
    
    print(f"\n📚 SOURCES & REFERENCES:")
    for source in result.sources[:3]:
        if isinstance(source, dict):
            print(f"   • {source.get('name', 'Medical Reference')}")
    
    # JSON output for backend storage
    result_dict = {
        "diagnosis_id": f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "patient_data": {
            "age": patient_input.age,
            "gender": patient_input.gender,
            "symptoms": patient_input.symptoms,
            "vital_signs": patient_input.vital_signs
        },
        "diagnostic_results": {
            "primary_diagnosis": result.primary_diagnosis,
            "confidence_score": result.confidence_score,
            "severity": result.severity,
            "findings": result.findings,
            "recommendations": result.recommendations,
            "emergency_indicators": result.emergency_indicators
        },
        "differential_diagnoses": result.differential_diagnoses,
        "care_plan": {
            "first_aid_steps": result.first_aid_steps,
            "medications": result.medications,
            "follow_up_questions": result.follow_up_questions,
            "follow_up_timeline": result.follow_up
        },
        "sources": result.sources,
        "agent_info": diagnostic_agent.get_agent_info()
    }
    
    # Save to file (simulating backend storage)
    with open('diagnosis_report.json', 'w') as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"\n💾 Diagnosis report saved to: diagnosis_report.json")
    
    # Agent information
    agent_info = diagnostic_agent.get_agent_info()
    print(f"\n🤖 AGENT INFORMATION:")
    print(f"   Name: {agent_info['agent_name']}")
    print(f"   Description: {agent_info['description']}")
    if 'search_agent_info' in agent_info:
        search_info = agent_info['search_agent_info']
        print(f"   Search Model: {search_info.get('llm_model', 'Unknown')}")
        print(f"   Search Available: {'Yes' if search_info.get('llm_available') else 'No'}")

# FastAPI/Flask integration example
class DiagnosticAPI:
    """Example API wrapper for backend integration"""
    
    def __init__(self, diagnostic_agent: MedicalDiagnosticAgent):
        self.agent = diagnostic_agent
    
    async def handle_diagnostic_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle diagnostic request from frontend"""
        try:
            # Parse request data
            diagnostic_input = DiagnosticInput(
                symptoms=request_data.get('symptoms', []),
                medical_history=request_data.get('medical_history', ''),
                uploaded_reports=request_data.get('uploaded_reports', []),
                age=request_data.get('age'),
                gender=request_data.get('gender'),
                vital_signs=request_data.get('vital_signs', {})
            )
            
            # Run diagnosis
            result = await self.agent.diagnose(diagnostic_input)
            
            # Prepare response for frontend
            response = {
                'success': True,
                'diagnosis_id': f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'results': {
                    'primary_diagnosis': result.primary_diagnosis,
                    'confidence_score': result.confidence_score,
                    'severity': result.severity,
                    'findings': result.findings,
                    'recommendations': result.recommendations,
                    'emergency_indicators': result.emergency_indicators,
                    'first_aid_steps': result.first_aid_steps,
                    'medications': result.medications,
                    'follow_up_questions': result.follow_up_questions,
                    'follow_up': result.follow_up
                },
                'differential_diagnoses': result.differential_diagnoses,
                'sources': result.sources,
                'timestamp': datetime.now().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"API error: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

if __name__ == "__main__":
    asyncio.run(main())
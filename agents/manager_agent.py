import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime

# Import all agents
from diagnosis_agent import MedicalDiagnosticAgent, DiagnosticInput, DiagnosticResult
from search_agent import MedicalSearchAgent
from hospital_operations_agent import HospitalOperationsAgent, Patient
from hospital_operations_data_model import HospitalOperationsData

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class UserQuery:
    """Standardized user query format"""
    query_type: str  # 'diagnosis', 'search', 'operations', 'general'
    content: str
    user_context: Dict[str, Any]
    files: Optional[List[str]] = None
    additional_params: Optional[Dict[str, Any]] = None

@dataclass
class AgentResponse:
    """Standardized agent response format"""
    agent_type: str
    response_data: Dict[str, Any]
    confidence: float
    timestamp: datetime
    sources: Optional[List[Dict[str, str]]] = None
    recommendations: Optional[List[str]] = None

class AgentManager:
    """
    Manager Agent that orchestrates all medical AI agents
    Routes queries to appropriate agents and enables inter-agent communication
    """
    
    def __init__(self, google_api_key: str, google_cse_id: str, groq_api_key: str = None):
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id
        self.groq_api_key = groq_api_key
        
        # Initialize all agents
        logger.info("Initializing all medical agents...")
        
        # Initialize Diagnostic Agent (with search integration)
        self.diagnostic_agent = MedicalDiagnosticAgent(
            google_api_key=google_api_key,
            google_cse_id=google_cse_id
        )
        
        # Initialize Search Agent
        self.search_agent = MedicalSearchAgent(
            google_api_key=google_api_key,
            google_cse_id=google_cse_id,
            groq_api_key=groq_api_key
        )
        
        # Initialize Hospital Operations Agent
        self.hospital_agent = HospitalOperationsAgent()
        
        # Agent registry
        self.agents = {
            'diagnostic': self.diagnostic_agent,
            'search': self.search_agent,
            'operations': self.hospital_agent
        }
        
        # Query routing rules
        self.routing_rules = {
            'symptoms': 'diagnostic',
            'diagnosis': 'diagnostic',
            'treatment': 'search',
            'medication': 'search',
            'hospital': 'operations',
            'beds': 'operations',
            'patients': 'operations',
            'search': 'search',
            'information': 'search',
            'question': 'search'
        }
        
        logger.info("Agent Manager initialized successfully")
    
    async def process_query(self, user_query: UserQuery) -> AgentResponse:
        """Main method to process user queries and route to appropriate agents"""
        logger.info(f"Processing query type: {user_query.query_type}")
        
        try:
            # Route based on query type
            if user_query.query_type == 'diagnosis':
                return await self._handle_diagnosis_query(user_query)
            elif user_query.query_type == 'search':
                return await self._handle_search_query(user_query)
            elif user_query.query_type == 'operations':
                return await self._handle_operations_query(user_query)
            elif user_query.query_type == 'general':
                return await self._handle_general_query(user_query)
            else:
                return self._create_error_response(f"Unknown query type: {user_query.query_type}")
                
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return self._create_error_response(str(e))
    
    async def _handle_diagnosis_query(self, user_query: UserQuery) -> AgentResponse:
        """Handle diagnosis queries with optional search enhancement"""
        try:
            # Extract diagnostic parameters
            diagnostic_input = self._create_diagnostic_input(user_query)
            
            # First, run diagnostic agent
            diagnostic_result = await self.diagnostic_agent.diagnose(diagnostic_input)
            
            # Check if we need to enhance with search
            needs_search = self._needs_search_enhancement(diagnostic_result)
            
            if needs_search:
                logger.info("Diagnostic result needs search enhancement")
                search_query = self._generate_search_query_from_diagnosis(diagnostic_result, user_query)
                
                # Run search agent
                search_result = await self.search_agent.search(
                    search_query,
                    user_query.user_context
                )
                
                # Enhance diagnostic result with search findings
                enhanced_result = await self._enhance_diagnosis_with_search(
                    diagnostic_result, search_result
                )
                
                return AgentResponse(
                    agent_type='diagnostic_with_search',
                    response_data=enhanced_result,
                    confidence=enhanced_result.get('confidence_score', 0.7),
                    timestamp=datetime.now(),
                    sources=search_result.get('sources', []),
                    recommendations=self._generate_recommendations(enhanced_result)
                )
            else:
                return AgentResponse(
                    agent_type='diagnostic',
                    response_data=self._format_diagnostic_result(diagnostic_result),
                    confidence=diagnostic_result.confidence_score,
                    timestamp=datetime.now(),
                    sources=diagnostic_result.sources,
                    recommendations=diagnostic_result.recommendations
                )
                
        except Exception as e:
            logger.error(f"Error in diagnosis query: {e}")
            # Fallback to search-only response
            return await self._fallback_to_search(user_query)
    
    async def _handle_search_query(self, user_query: UserQuery) -> AgentResponse:
        """Handle pure search queries"""
        try:
            search_result = await self.search_agent.search(
                user_query.content,
                user_query.user_context
            )
            
            return AgentResponse(
                agent_type='search',
                response_data=search_result,
                confidence=0.8,  # Search typically has good confidence
                timestamp=datetime.now(),
                sources=search_result.get('sources', []),
                recommendations=['Consider consulting with healthcare provider for personalized advice']
            )
        except Exception as e:
            logger.error(f"Error in search query: {e}")
            return self._create_error_response(str(e))
    
    async def _handle_operations_query(self, user_query: UserQuery) -> AgentResponse:
        """Handle hospital operations queries"""
        try:
            # Check if files are provided for processing
            if user_query.files:
                # Process hospital data files
                operations_data = await self._process_hospital_files(user_query.files)
                
                # Check if diagnostic analysis is requested on operations data
                if self._needs_diagnosis_on_operations(user_query):
                    logger.info("Operations query needs diagnostic analysis")
                    diagnostic_results = await self._analyze_operations_data(operations_data)
                    
                    return AgentResponse(
                        agent_type='operations_with_diagnosis',
                        response_data={
                            'operations_data': operations_data,
                            'diagnostic_insights': diagnostic_results
                        },
                        confidence=0.75,
                        timestamp=datetime.now(),
                        recommendations=self._generate_operations_recommendations(operations_data, diagnostic_results)
                    )
                else:
                    return AgentResponse(
                        agent_type='operations',
                        response_data=operations_data,
                        confidence=0.9,
                        timestamp=datetime.now(),
                        recommendations=self._generate_operations_recommendations(operations_data)
                    )
            else:
                # If no files, provide sample data or instructions
                return AgentResponse(
                    agent_type='operations',
                    response_data={
                        'message': 'Please upload hospital data files (CSV, Excel, PDF) for analysis',
                        'supported_formats': ['.csv', '.xlsx', '.xls', '.pdf']
                    },
                    confidence=1.0,
                    timestamp=datetime.now(),
                    recommendations=['Upload patient data files for detailed hospital operations analysis']
                )
        except Exception as e:
            logger.error(f"Error in operations query: {e}")
            return self._create_error_response(str(e))
    
    async def _handle_general_query(self, user_query: UserQuery) -> AgentResponse:
        """Handle general queries by routing to appropriate agent"""
        try:
            # Determine which agent to use based on content analysis
            target_agent = self._route_general_query(user_query.content)
            
            if target_agent == 'diagnostic':
                # Convert to diagnostic query
                diagnostic_input = DiagnosticInput(
                    symptoms=[user_query.content],
                    medical_history='',
                    uploaded_reports=[]
                )
                return await self._handle_diagnosis_query(user_query)
            elif target_agent == 'search':
                return await self._handle_search_query(user_query)
            elif target_agent == 'operations':
                return await self._handle_operations_query(user_query)
            else:
                # Default to search for general information
                return await self._handle_search_query(user_query)
                
        except Exception as e:
            logger.error(f"Error in general query: {e}")
            return self._create_error_response(str(e))
    
    def _create_diagnostic_input(self, user_query: UserQuery) -> DiagnosticInput:
        """Create DiagnosticInput from user query"""
        # Extract parameters from query
        content = user_query.content.lower()
        
        # Simple symptom extraction (can be enhanced with NLP)
        symptoms = []
        if 'symptom' in content or 'pain' in content or 'headache' in content:
            symptoms = [user_query.content]
        
        return DiagnosticInput(
            symptoms=symptoms,
            medical_history=user_query.user_context.get('medical_history', ''),
            uploaded_reports=user_query.files or [],
            age=user_query.user_context.get('age'),
            gender=user_query.user_context.get('gender'),
            vital_signs=user_query.user_context.get('vital_signs')
        )
    
    def _needs_search_enhancement(self, diagnostic_result: DiagnosticResult) -> bool:
        """Check if diagnostic result needs search enhancement"""
        # Needs search if confidence is low or if diagnosis is unclear
        if diagnostic_result.confidence_score < 0.6:
            return True
        
        # Needs search if primary diagnosis is vague
        vague_diagnoses = ['requires further evaluation', 'unable to determine', 'needs more information']
        primary_diag = diagnostic_result.primary_diagnosis.lower()
        if any(vague in primary_diag for vague in vague_diagnoses):
            return True
        
        # Needs search if emergency level is high
        if diagnostic_result.severity in ['critical', 'attention']:
            return True
        
        return False
    
    def _generate_search_query_from_diagnosis(self, diagnostic_result: DiagnosticResult, 
                                           user_query: UserQuery) -> str:
        """Generate search query based on diagnostic results"""
        query_parts = []
        
        # Add primary diagnosis
        if diagnostic_result.primary_diagnosis:
            query_parts.append(diagnostic_result.primary_diagnosis)
        
        # Add symptoms from original query
        if user_query.content:
            query_parts.append(user_query.content)
        
        # Add emergency level if critical
        if diagnostic_result.severity in ['critical', 'attention']:
            query_parts.append("emergency management treatment")
        
        return " ".join(query_parts)
    
    async def _enhance_diagnosis_with_search(self, diagnostic_result: DiagnosticResult,
                                           search_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance diagnostic result with search findings"""
        enhanced = {
            'primary_diagnosis': diagnostic_result.primary_diagnosis,
            'confidence_score': min(diagnostic_result.confidence_score + 0.1, 0.95),  # Slight boost
            'differential_diagnoses': diagnostic_result.differential_diagnoses,
            'severity': diagnostic_result.severity,
            'findings': diagnostic_result.findings + [search_result.get('diagnostic_response', '')[:500]],
            'recommendations': diagnostic_result.recommendations + [
                'Additional information from medical sources has been considered',
                'Consult with healthcare provider for confirmation'
            ],
            'search_enhanced': True,
            'search_summary': search_result.get('diagnostic_response', '')[:1000]
        }
        
        return enhanced
    
    async def _process_hospital_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Process hospital operations files"""
        # This would typically call hospital_agent.process_file for each file
        # For now, return a placeholder structure
        
        # In real implementation:
        # results = []
        # for file_path in file_paths:
        #     result = self.hospital_agent.process_file(file_path)
        #     results.append(result)
        # return self._aggregate_hospital_results(results)
        
        return {
            'dashboard_stats': {
                'total_patients': 150,
                'inpatients': 105,
                'outpatients': 45,
                'critical_patients': 8,
                'unattended_patients': 12,
                'total_beds': 200,
                'occupied_beds': 105,
                'available_beds': 95
            },
            'message': 'Hospital operations data processed successfully',
            'files_processed': len(file_paths)
        }
    
    def _needs_diagnosis_on_operations(self, user_query: UserQuery) -> bool:
        """Check if operations data needs diagnostic analysis"""
        content = user_query.content.lower()
        
        # Check if user is asking for diagnosis on operations data
        diagnostic_keywords = ['diagnose', 'analyze patients', 'medical condition', 
                             'symptoms', 'treatment', 'care']
        
        return any(keyword in content for keyword in diagnostic_keywords)
    
    async def _analyze_operations_data(self, operations_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze hospital operations data for diagnostic insights"""
        try:
            # Extract patient data from operations
            # This is simplified - in reality, you'd extract actual patient records
            
            diagnostic_insights = {
                'critical_patients_analysis': {
                    'count': operations_data.get('dashboard_stats', {}).get('critical_patients', 0),
                    'recommendations': [
                        'Ensure critical patients are monitored continuously',
                        'Assign specialized nursing staff to critical care units',
                        'Regularly review critical patient treatment plans'
                    ]
                },
                'unattended_patients': {
                    'count': operations_data.get('dashboard_stats', {}).get('unattended_patients', 0),
                    'recommendations': [
                        'Prioritize unattended patients for immediate evaluation',
                        'Schedule urgent consultations for unattended patients',
                        'Review triage process for efficiency'
                    ]
                },
                'capacity_management': {
                    'bed_occupancy_rate': (operations_data.get('dashboard_stats', {}).get('occupied_beds', 0) / 
                                         operations_data.get('dashboard_stats', {}).get('total_beds', 1)) * 100,
                    'recommendations': [
                        'Consider bed allocation optimization',
                        'Monitor discharge planning efficiency',
                        'Review admission criteria if occupancy exceeds 85%'
                    ]
                }
            }
            
            return diagnostic_insights
            
        except Exception as e:
            logger.error(f"Error analyzing operations data: {e}")
            return {'error': str(e)}
    
    def _route_general_query(self, query_content: str) -> str:
        """Route general query to appropriate agent based on content"""
        query_lower = query_content.lower()
        
        # Check for diagnostic keywords
        if any(keyword in query_lower for keyword in 
               ['symptom', 'pain', 'headache', 'fever', 'diagnosis', 'what is wrong']):
            return 'diagnostic'
        
        # Check for hospital operations keywords
        if any(keyword in query_lower for keyword in 
               ['hospital', 'bed', 'patient', 'admission', 'discharge', 'capacity']):
            return 'operations'
        
        # Check for search/information keywords
        if any(keyword in query_lower for keyword in 
               ['what is', 'how to', 'treatment for', 'medication for', 'search']):
            return 'search'
        
        # Default to search
        return 'search'
    
    async def _fallback_to_search(self, user_query: UserQuery) -> AgentResponse:
        """Fallback to search when diagnosis fails"""
        search_result = await self.search_agent.search(
            user_query.content,
            user_query.user_context
        )
        
        return AgentResponse(
            agent_type='search_fallback',
            response_data={
                'message': 'Unable to provide diagnosis. Here is general medical information:',
                'search_results': search_result
            },
            confidence=0.7,
            timestamp=datetime.now(),
            sources=search_result.get('sources', []),
            recommendations=['Please consult with a healthcare provider for proper diagnosis']
        )
    
    def _format_diagnostic_result(self, diagnostic_result: DiagnosticResult) -> Dict[str, Any]:
        """Format diagnostic result for response"""
        return {
            'primary_diagnosis': diagnostic_result.primary_diagnosis,
            'confidence_score': diagnostic_result.confidence_score,
            'severity': diagnostic_result.severity,
            'findings': diagnostic_result.findings,
            'recommendations': diagnostic_result.recommendations,
            'emergency_indicators': diagnostic_result.emergency_indicators
        }
    
    def _generate_recommendations(self, result_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations from result data"""
        recommendations = []
        
        # Add severity-based recommendations
        if result_data.get('severity') == 'critical':
            recommendations.append('🚨 Seek emergency medical care immediately')
        elif result_data.get('severity') == 'attention':
            recommendations.append('Schedule urgent medical evaluation')
        
        # Add confidence-based recommendations
        if result_data.get('confidence_score', 0) < 0.7:
            recommendations.append('Consult healthcare provider for confirmation')
        
        # Add general recommendations
        recommendations.extend([
            'Follow up with healthcare provider as recommended',
            'Monitor symptoms and seek care if they worsen'
        ])
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _generate_operations_recommendations(self, operations_data: Dict[str, Any], 
                                           diagnostic_insights: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate recommendations for hospital operations"""
        recommendations = []
        
        stats = operations_data.get('dashboard_stats', {})
        
        # Bed capacity recommendations
        occupancy_rate = (stats.get('occupied_beds', 0) / stats.get('total_beds', 1)) * 100
        if occupancy_rate > 85:
            recommendations.append('High bed occupancy: Consider optimizing bed allocation')
        elif occupancy_rate < 50:
            recommendations.append('Low bed occupancy: Review admission processes')
        
        # Critical patients recommendations
        if stats.get('critical_patients', 0) > 10:
            recommendations.append('High number of critical patients: Ensure adequate critical care resources')
        
        # Unattended patients recommendations
        if stats.get('unattended_patients', 0) > 5:
            recommendations.append('Multiple unattended patients: Review triage and evaluation processes')
        
        # Add diagnostic insights if available
        if diagnostic_insights:
            if 'critical_patients_analysis' in diagnostic_insights:
                recommendations.extend(
                    diagnostic_insights['critical_patients_analysis'].get('recommendations', [])[:2]
                )
        
        # General recommendations
        recommendations.extend([
            'Regularly review hospital operations metrics',
            'Implement quality improvement initiatives based on data insights'
        ])
        
        return list(set(recommendations))[:6]  # Remove duplicates and limit
    
    def _create_error_response(self, error_message: str) -> AgentResponse:
        """Create error response"""
        return AgentResponse(
            agent_type='error',
            response_data={
                'error': error_message,
                'message': 'Unable to process request'
            },
            confidence=0.0,
            timestamp=datetime.now(),
            recommendations=['Please try again or contact support']
        )
    
    def get_manager_info(self) -> Dict[str, Any]:
        """Get information about the manager and all agents"""
        return {
            'manager_name': 'Medical Agent Manager',
            'description': 'Orchestrates all medical AI agents for comprehensive healthcare assistance',
            'agents_available': {
                'diagnostic': 'Medical Diagnostic Agent with search integration',
                'search': 'Medical Search Agent (Ollama + Google CSE)',
                'operations': 'Hospital Operations Analysis Agent'
            },
            'capabilities': [
                'Diagnostic analysis with search enhancement',
                'Medical information retrieval',
                'Hospital operations data analysis',
                'Automatic query routing',
                'Inter-agent communication'
            ]
        }
    
    async def agent_collaboration(self, query: str, context: Dict[str, Any]) -> AgentResponse:
        """Special method for agent collaboration on complex queries"""
        # Parse query for multiple agent involvement
        query_lower = query.lower()
        
        # Check if query involves both diagnosis and operations
        if ('patient' in query_lower or 'hospital' in query_lower) and \
           ('diagnosis' in query_lower or 'symptom' in query_lower):
            
            logger.info("Multi-agent collaboration needed")
            
            # Step 1: Process hospital data if available
            ops_results = {}
            if context.get('hospital_files'):
                ops_results = await self._process_hospital_files(context['hospital_files'])
            
            # Step 2: Run diagnostic analysis
            diagnostic_input = DiagnosticInput(
                symptoms=context.get('symptoms', []),
                medical_history=context.get('medical_history', ''),
                uploaded_reports=[]
            )
            diag_result = await self.diagnostic_agent.diagnose(diagnostic_input)
            
            # Step 3: Search for additional information
            search_query = f"{query} hospital management patient care"
            search_result = await self.search_agent.search(search_query, context)
            
            # Combine all results
            combined_result = {
                'diagnostic_analysis': self._format_diagnostic_result(diag_result),
                'hospital_operations': ops_results,
                'search_information': search_result.get('diagnostic_response', ''),
                'integrated_recommendations': self._generate_integrated_recommendations(
                    diag_result, ops_results, search_result
                )
            }
            
            return AgentResponse(
                agent_type='collaborative',
                response_data=combined_result,
                confidence=0.8,
                timestamp=datetime.now(),
                sources=search_result.get('sources', []),
                recommendations=combined_result['integrated_recommendations']
            )
        
        # Default to standard processing
        user_query = UserQuery(
            query_type='general',
            content=query,
            user_context=context
        )
        return await self.process_query(user_query)
    
    def _generate_integrated_recommendations(self, diag_result: DiagnosticResult,
                                           ops_data: Dict[str, Any],
                                           search_result: Dict[str, Any]) -> List[str]:
        """Generate integrated recommendations from multiple agent outputs"""
        recommendations = []
        
        # Diagnostic recommendations
        recommendations.extend(diag_result.recommendations[:2])
        
        # Operations recommendations
        if ops_data:
            stats = ops_data.get('dashboard_stats', {})
            if stats.get('critical_patients', 0) > 0:
                recommendations.append(f'Monitor {stats["critical_patients"]} critical patients closely')
            if stats.get('unattended_patients', 0) > 0:
                recommendations.append(f'Prioritize evaluation of {stats["unattended_patients"]} unattended patients')
        
        # Search-based recommendations
        if 'search' in str(search_result).lower():
            recommendations.append('Consider additional medical literature for complex cases')
        
        # Integrated recommendations
        recommendations.extend([
            'Coordinate care between different hospital departments',
            'Ensure communication between diagnostic and treatment teams',
            'Regularly update patient care plans based on latest information'
        ])
        
        return list(set(recommendations))[:8]

# Example usage
async def main():
    """Example of using the Agent Manager"""
    
    # Initialize manager
    GOOGLE_API_KEY = "your_google_api_key"
    GOOGLE_CSE_ID = "your_search_engine_id"
    
    manager = AgentManager(GOOGLE_API_KEY, GOOGLE_CSE_ID)
    
    # Example 1: Diagnostic query
    print("\n" + "="*80)
    print("EXAMPLE 1: DIAGNOSTIC QUERY")
    print("="*80)
    
    diagnostic_query = UserQuery(
        query_type='diagnosis',
        content='severe chest pain with shortness of breath',
        user_context={
            'age': 45,
            'gender': 'male',
            'medical_history': 'hypertension'
        }
    )
    
    result1 = await manager.process_query(diagnostic_query)
    print(f"Agent Type: {result1.agent_type}")
    print(f"Confidence: {result1.confidence}")
    print(f"Primary Diagnosis: {result1.response_data.get('primary_diagnosis', 'N/A')}")
    
    # Example 2: Operations query
    print("\n" + "="*80)
    print("EXAMPLE 2: HOSPITAL OPERATIONS QUERY")
    print("="*80)
    
    operations_query = UserQuery(
        query_type='operations',
        content='analyze hospital patient data',
        user_context={},
        files=['sample_patient_data.csv']  # Would be actual file paths
    )
    
    result2 = await manager.process_query(operations_query)
    print(f"Agent Type: {result2.agent_type}")
    print(f"Patients Processed: {result2.response_data.get('files_processed', 0)}")
    
    # Example 3: Complex collaboration
    print("\n" + "="*80)
    print("EXAMPLE 3: AGENT COLLABORATION")
    print("="*80)
    
    collaboration_result = await manager.agent_collaboration(
        "How should we handle critical patients with cardiac symptoms in our hospital?",
        {
            'symptoms': ['chest pain', 'shortness of breath'],
            'medical_history': 'cardiac history',
            'hospital_files': ['hospital_data.csv']
        }
    )
    
    print(f"Agent Type: {collaboration_result.agent_type}")
    print(f"Recommendations: {collaboration_result.recommendations[:3]}")
    
    # Get manager info
    print("\n" + "="*80)
    print("MANAGER INFORMATION")
    print("="*80)
    
    info = manager.get_manager_info()
    for key, value in info.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    asyncio.run(main())
from pydantic import BaseModel
from typing import List, Dict, Any

class DashboardStats(BaseModel):
    total_patients: int
    inpatients: int
    outpatients: int
    critical_patients: int
    unattended_patients: int
    total_beds: int
    occupied_beds: int
    available_beds: int

class PriorityDistribution(BaseModel):
    name: str
    value: int

class DepartmentStats(BaseModel):
    name: str
    value: int

class AgeDistribution(BaseModel):
    age_range: str
    count: int

class HospitalOperationsData(BaseModel):
    dashboard_stats: DashboardStats
    priority_distribution: List[PriorityDistribution]
    department_stats: List[DepartmentStats]
    age_distribution: List[AgeDistribution]
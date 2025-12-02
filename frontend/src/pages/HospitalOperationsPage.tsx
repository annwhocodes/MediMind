// Enhanced HospitalManagementAgent with Filtering Functionality
// This code adds filtering to the patients view without changing other functionalities

import React, { useState, useEffect, useMemo } from 'react';
import { FC } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell, LineChart, Line, ResponsiveContainer } from 'recharts';
import { Users, Bed, AlertTriangle, UserCheck, FileText, Activity, TrendingUp, Calendar, Heart, Thermometer, BedDouble, Filter, X } from 'lucide-react';
import * as Papa from 'papaparse';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/layout/MainLayout';

type Patient = {
  name: string;
  age: number;
  gender: string;
  bedNumber: string;
  bedType: 'general' | 'semi-private' | 'private';
  status: 'inpatient' | 'outpatient';
  priority: 'critical' | 'urgent' | 'normal';
  admissionDate: string;
  symptoms: string;
  medicalHistory: string;
  vitals: {
    temperature: number;
    heartRate: number;
    bloodPressure: string;
  };
  diagnosis: string;
  department: string;
};

type CsvPatientRow = {
  name: string;
  age: string | number;
  gender: string;
  bedNumber?: string;
  bed_number?: string;
  bedType?: string;
  bed_type?: string;
  status?: string;
  priority?: string;
  admissionDate?: string;
  admission_date?: string;
  symptoms?: string;
  medicalHistory?: string;
  medical_history?: string;
  vitals?: string;
  diagnosis?: string;
  department?: string;
};

type PatientCardProps = {
  patient: Patient;
  onClick: (patient: Patient) => void;
};

type PatientModalProps = {
  patient: Patient;
  onClose: () => void;
};

const HospitalManagementAgent = () => {
  const navigate = useNavigate();
  const [csvData, setCsvData] = useState<Patient[]>([]);
  const [customPatient, setCustomPatient] = useState({
    name: '',
    age: '',
    gender: '',
    bedNumber: '',
    bedType: 'general',
    status: 'inpatient',
    priority: 'normal',
    admissionDate: '',
    symptoms: '',
    medicalHistory: '',
    department: ''
  });
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [activeView, setActiveView] = useState('dashboard');

  // NEW: Filter states
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    priority: 'all',
    department: 'all',
    status: 'all',
    bedType: 'all',
    gender: 'all',
    searchTerm: ''
  });

  // Sample data for demonstration
  const sampleData: Patient[] = [
    {
      name: 'John Smith',
      age: 45,
      gender: 'Male',
      bedNumber: 'A101',
      bedType: 'general',
      status: 'inpatient',
      priority: 'critical',
      admissionDate: '2024-12-01',
      symptoms: 'Chest pain, shortness of breath, dizziness',
      medicalHistory: 'Hypertension, diabetes',
      vitals: { temperature: 38.2, heartRate: 95, bloodPressure: '140/90' },
      diagnosis: 'Acute coronary syndrome - requires immediate intervention',
      department: 'Cardiology'
    },
    {
      name: 'Sarah Johnson',
      age: 32,
      gender: 'Female',
      bedNumber: 'B205',
      bedType: 'general',
      status: 'inpatient',
      priority: 'normal',
      admissionDate: '2024-12-02',
      symptoms: 'Fever, headache, body aches',
      medicalHistory: 'No significant history',
      vitals: { temperature: 39.1, heartRate: 88, bloodPressure: '120/80' },
      diagnosis: 'Viral infection - monitor and symptomatic treatment',
      department: 'Internal Medicine'
    },
    {
      name: 'Michael Brown',
      age: 67,
      gender: 'Male',
      bedNumber: 'C302',
      bedType: 'general',
      status: 'outpatient',
      priority: 'urgent',
      admissionDate: '2024-12-03',
      symptoms: 'Severe abdominal pain, nausea',
      medicalHistory: 'Gallstones, previous surgery',
      vitals: { temperature: 37.8, heartRate: 102, bloodPressure: '135/85' },
      diagnosis: 'Possible gallbladder inflammation - requires imaging',
      department: 'Surgery'
    },
    {
      name: 'Emily Davis',
      age: 28,
      gender: 'Female',
      bedNumber: 'D101',
      bedType: 'general',
      status: 'inpatient',
      priority: 'normal',
      admissionDate: '2024-12-01',
      symptoms: 'Persistent cough, fatigue',
      medicalHistory: 'Asthma',
      vitals: { temperature: 37.2, heartRate: 78, bloodPressure: '110/70' },
      diagnosis: 'Respiratory infection - antibiotics prescribed',
      department: 'Pulmonology'
    },
    {
      name: 'Robert Wilson',
      age: 55,
      gender: 'Male',
      bedNumber: 'A205',
      bedType: 'private',
      status: 'inpatient',
      priority: 'urgent',
      admissionDate: '2024-12-04',
      symptoms: 'Chest tightness, irregular heartbeat',
      medicalHistory: 'Previous heart attack',
      vitals: { temperature: 37.0, heartRate: 110, bloodPressure: '150/95' },
      diagnosis: 'Cardiac arrhythmia - monitoring required',
      department: 'Cardiology'
    },
    {
      name: 'Lisa Anderson',
      age: 42,
      gender: 'Female',
      bedNumber: 'B110',
      bedType: 'semi-private',
      status: 'inpatient',
      priority: 'critical',
      admissionDate: '2024-12-03',
      symptoms: 'Severe headache, vision problems, nausea',
      medicalHistory: 'Migraines, hypertension',
      vitals: { temperature: 37.5, heartRate: 92, bloodPressure: '180/110' },
      diagnosis: 'Hypertensive crisis - immediate treatment required',
      department: 'Emergency Medicine'
    }
  ];

  useEffect(() => {
    setCsvData(sampleData);
  }, []);

  // NEW: Get unique values for filter dropdowns
  const filterOptions = useMemo(() => {
    const departments = [...new Set(csvData.map(p => p.department))].sort();
    const priorities = ['normal', 'urgent', 'critical'];
    const statuses = ['inpatient', 'outpatient'];
    const bedTypes = ['general', 'semi-private', 'private'];
    const genders = [...new Set(csvData.map(p => p.gender))].sort();

    return { departments, priorities, statuses, bedTypes, genders };
  }, [csvData]);

  // NEW: Filter patients based on selected criteria
  const filteredPatients = useMemo(() => {
    return csvData.filter(patient => {
      const matchesPriority = filters.priority === 'all' || patient.priority === filters.priority;
      const matchesDepartment = filters.department === 'all' || patient.department === filters.department;
      const matchesStatus = filters.status === 'all' || patient.status === filters.status;
      const matchesBedType = filters.bedType === 'all' || patient.bedType === filters.bedType;
      const matchesGender = filters.gender === 'all' || patient.gender === filters.gender;
      
      const matchesSearch = filters.searchTerm === '' || 
        patient.name.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
        patient.bedNumber.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
        patient.symptoms.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
        patient.diagnosis.toLowerCase().includes(filters.searchTerm.toLowerCase());

      return matchesPriority && matchesDepartment && matchesStatus && 
             matchesBedType && matchesGender && matchesSearch;
    });
  }, [csvData, filters]);

  // NEW: Clear all filters
  const clearFilters = () => {
    setFilters({
      priority: 'all',
      department: 'all',
      status: 'all',
      bedType: 'all',
      gender: 'all',
      searchTerm: ''
    });
  };

  // NEW: Count active filters
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.priority !== 'all') count++;
    if (filters.department !== 'all') count++;
    if (filters.status !== 'all') count++;
    if (filters.bedType !== 'all') count++;
    if (filters.gender !== 'all') count++;
    if (filters.searchTerm !== '') count++;
    return count;
  }, [filters]);

  const validBedTypes = ['general', 'semi-private', 'private'] as const;
  const validStatuses = ['inpatient', 'outpatient'] as const;
  const validPriorities = ['normal', 'urgent', 'critical'] as const;

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type === 'text/csv') {
      Papa.parse<CsvPatientRow>(file, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
        delimitersToGuess: [',', '\t', '|', ';'],
        complete: (result: Papa.ParseResult<CsvPatientRow>) => {
          const processedData: Patient[] = result.data
            .filter((row: CsvPatientRow) => row.name && row.name.trim() !== '')
            .map((row: CsvPatientRow): Patient => {
              const bedNumber = row.bedNumber || row.bed_number || 'N/A';
              
              return {
                name: row.name.trim(),
                age: parseInt(String(row.age)) || 0,
                gender: row.gender || 'Not specified',
                bedNumber: bedNumber,
                bedType: validBedTypes.includes(row.bedType as any) || validBedTypes.includes(row.bed_type as any)
                  ? ((row.bedType || row.bed_type) as Patient['bedType'])
                  : 'general',
                status: validStatuses.includes(row.status as any)
                  ? (row.status as Patient['status'])
                  : 'inpatient',
                priority: validPriorities.includes(row.priority as any)
                  ? (row.priority as Patient['priority'])
                  : 'normal',
                admissionDate: row.admissionDate || row.admission_date || new Date().toISOString().slice(0, 10),
                symptoms: row.symptoms || '',
                medicalHistory: row.medicalHistory || row.medical_history || '',
                vitals: row.vitals
                  ? (typeof row.vitals === 'string' ? JSON.parse(row.vitals) : row.vitals)
                  : { temperature: 37, heartRate: 72, bloodPressure: '120/80' },
                diagnosis: row.diagnosis || 'Pending diagnosis',
                department: row.department || 'General'
              };
            });

          setCsvData(processedData);
          console.log(`Loaded ${processedData.length} patients from CSV`);
        },
        error: (error) => {
          console.error('CSV parsing error:', error);
          alert('Error parsing CSV file. Please check the format.');
        }
      });
    } else {
      alert('Please select a valid CSV file.');
    }
  };

  const addCustomPatient = () => {
    if (customPatient.name.trim()) {
      const generateBedNumber = (): string => {
        const floors = ['A', 'B', 'C', 'D'];
        const existingBeds = csvData.map(p => p.bedNumber).filter(bed => bed !== 'N/A');
        let bedNumber = '';
        
        for (let floor of floors) {
          for (let room = 101; room <= 399; room++) {
            bedNumber = `${floor}${room}`;
            if (!existingBeds.includes(bedNumber)) {
              return bedNumber;
            }
          }
        }
        
        return `TEMP${Date.now()}`;
      };

      const newPatient: Patient = {
        name: customPatient.name.trim(),
        age: parseInt(customPatient.age) || 0,
        gender: customPatient.gender || 'Not specified',
        bedNumber: customPatient.bedNumber || generateBedNumber(),
        bedType: ['general', 'semi-private', 'private'].includes(customPatient.bedType)
          ? (customPatient.bedType as Patient['bedType'])
          : 'general',
        status: ['inpatient', 'outpatient'].includes(customPatient.status)
          ? (customPatient.status as Patient['status'])
          : 'inpatient',
        priority: ['normal', 'urgent', 'critical'].includes(customPatient.priority)
          ? (customPatient.priority as Patient['priority'])
          : 'normal',
        admissionDate: customPatient.admissionDate || new Date().toISOString().slice(0, 10),
        symptoms: customPatient.symptoms || '',
        medicalHistory: customPatient.medicalHistory || '',
        vitals: {
          temperature: 37,
          heartRate: 72,
          bloodPressure: '120/80'
        },
        diagnosis: 'Pending diagnosis - requires evaluation',
        department: customPatient.department || 'General'
      };

      setCsvData([...csvData, newPatient]);

      setCustomPatient({
        name: '',
        age: '',
        gender: '',
        bedNumber: '',
        bedType: 'general',
        status: 'inpatient',
        priority: 'normal',
        admissionDate: '',
        symptoms: '',
        medicalHistory: '',
        department: ''
      });

      setShowAddForm(false);
    }
  };

  const getDashboardStats = useMemo(() => {
    const stats = csvData.reduce((acc, patient) => {
      acc.total++;
      if (patient.status === 'inpatient') acc.inpatients++;
      if (patient.status === 'outpatient') acc.outpatients++;
      if (patient.priority === 'critical') acc.critical++;
      if (patient.priority === 'urgent') acc.urgent++;
      
      if (patient.status === 'inpatient' && patient.bedNumber !== 'N/A') {
        acc.occupiedBeds++;
      }
      
      return acc;
    }, { 
      total: 0, 
      inpatients: 0, 
      outpatients: 0, 
      critical: 0, 
      urgent: 0,
      occupiedBeds: 0
    });

    return [
      { name: 'Total Patients', value: stats.total, color: '#3B82F6', icon: Users },
      { name: 'Inpatients', value: stats.inpatients, color: '#10B981', icon: Bed },
      { name: 'Outpatients', value: stats.outpatients, color: '#F59E0B', icon: UserCheck },
      { name: 'Critical Cases', value: stats.critical, color: '#EF4444', icon: AlertTriangle },
      { name: 'Occupied Beds', value: stats.occupiedBeds, color: '#8B5CF6', icon: BedDouble }
    ];
  }, [csvData]);

  const getPriorityDistribution = useMemo(() => {
    const priorityCount: Record<'normal' | 'urgent' | 'critical', number> = {
      normal: 0,
      urgent: 0,
      critical: 0
    };

    csvData.forEach((patient) => {
      priorityCount[patient.priority] += 1;
    });

    return Object.entries(priorityCount).map(([priority, count]) => ({
      name: priority.charAt(0).toUpperCase() + priority.slice(1),
      value: count,
      color: priority === 'critical' ? '#EF4444' : priority === 'urgent' ? '#F59E0B' : '#10B981'
    }));
  }, [csvData]);

  const getDepartmentStats = useMemo(() => {
    const deptCount: Record<string, number> = csvData.reduce((acc, patient) => {
      const dept = patient.department || 'General';
      acc[dept] = (acc[dept] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(deptCount)
      .map(([department, patients]) => ({
        department,
        patients,
        name: department,
        value: patients,
        color: `hsl(${Math.floor(Math.random() * 360)}, 70%, 50%)`
      }))
      .sort((a, b) => b.patients - a.patients);
  }, [csvData]);

  const getAgeDistribution = useMemo(() => {
    const ageGroups = { '0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0 };

    csvData.forEach(patient => {
      const age = patient.age;
      if (age <= 18) ageGroups['0-18']++;
      else if (age <= 35) ageGroups['19-35']++;
      else if (age <= 50) ageGroups['36-50']++;
      else if (age <= 65) ageGroups['51-65']++;
      else ageGroups['65+']++;
    });

    return Object.entries(ageGroups).map(([range, count]) => ({
      ageRange: range,
      count
    }));
  }, [csvData]);

  const getBedOccupancyByType = useMemo(() => {
    const bedTypeCount: Record<string, { total: number; occupied: number }> = {
      general: { total: 0, occupied: 0 },
      'semi-private': { total: 0, occupied: 0 },
      private: { total: 0, occupied: 0 }
    };

    csvData.forEach((patient) => {
      if (patient.status === 'inpatient' && patient.bedNumber !== 'N/A') {
        bedTypeCount[patient.bedType].occupied++;
      }
    });

    bedTypeCount.general.total = 50;
    bedTypeCount['semi-private'].total = 20;
    bedTypeCount.private.total = 10;

    return Object.entries(bedTypeCount).map(([bedType, stats]) => ({
      bedType,
      occupied: stats.occupied,
      total: stats.total,
      occupancyRate: stats.total > 0 ? (stats.occupied / stats.total) * 100 : 0
    }));
  }, [csvData]);

  const getDepartmentBedDistribution = useMemo(() => {
    const deptBeds = csvData
      .filter(patient => patient.status === 'inpatient' && patient.bedNumber !== 'N/A')
      .reduce((acc, patient) => {
        const dept = patient.department || 'General';
        if (!acc[dept]) acc[dept] = [];
        acc[dept].push(patient.bedNumber);
        return acc;
      }, {} as Record<string, string[]>);

    return Object.entries(deptBeds).map(([department, beds]) => ({
      department,
      bedsOccupied: beds.length,
      bedNumbers: beds.sort()
    }));
  }, [csvData]);

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

  const PatientCard: FC<PatientCardProps> = ({ patient, onClick }) => (
    <div
      className={`bg-white rounded-lg shadow-md p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 ${
        patient.priority === 'critical' ? 'border-red-500' :
        patient.priority === 'urgent' ? 'border-yellow-500' : 'border-green-500'
      }`}
      onClick={() => onClick(patient)}
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold text-lg text-gray-800">{patient.name}</h3>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          patient.priority === 'critical' ? 'bg-red-100 text-red-800' :
          patient.priority === 'urgent' ? 'bg-yellow-100 text-yellow-800' :
          'bg-green-100 text-green-800'
        }`}>
          {patient.priority}
        </span>
      </div>
      <div className="space-y-1 text-sm text-gray-600">
        <p><strong>Age:</strong> {patient.age} | <strong>Gender:</strong> {patient.gender}</p>
        <p><strong>Bed:</strong> {patient.bedNumber || 'N/A'} | <strong>Status:</strong> {patient.status}</p>
        <p><strong>Department:</strong> {patient.department || 'General'}</p>
        <p className="text-xs mt-2 line-clamp-2">{patient.symptoms}</p>
      </div>
    </div>
  );

  const PatientModal: FC<PatientModalProps> = ({ patient, onClose }) => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">{patient.name} - Medical Profile</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 text-xl font-bold"
            >
              ×
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-semibold text-blue-800 mb-2">Patient Information</h3>
                <div className="space-y-2 text-sm">
                  <p><strong>Age:</strong> {patient.age}</p>
                  <p><strong>Gender:</strong> {patient.gender}</p>
                  <p><strong>Bed Number:</strong> {patient.bedNumber || 'N/A'}</p>
                  <p><strong>Status:</strong> {patient.status}</p>
                  <p><strong>Priority:</strong> <span className={`font-medium ${
                    patient.priority === 'critical' ? 'text-red-600' :
                    patient.priority === 'urgent' ? 'text-yellow-600' :
                    'text-green-600'
                  }`}>{patient.priority}</span></p>
                  <p><strong>Department:</strong> {patient.department}</p>
                  <p><strong>Admission Date:</strong> {patient.admissionDate}</p>
                </div>
              </div>

              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-semibold text-green-800 mb-2 flex items-center">
                  <Heart className="w-4 h-4 mr-2" />
                  Vital Signs
                </h3>
                <div className="space-y-2 text-sm">
                  <p><strong>Temperature:</strong> {patient.vitals?.temperature}°C</p>
                  <p><strong>Heart Rate:</strong> {patient.vitals?.heartRate} bpm</p>
                  <p><strong>Blood Pressure:</strong> {patient.vitals?.bloodPressure}</p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="bg-yellow-50 p-4 rounded-lg">
                <h3 className="font-semibold text-yellow-800 mb-2">Symptoms</h3>
                <p className="text-sm">{patient.symptoms}</p>
              </div>

              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="font-semibold text-purple-800 mb-2">Medical History</h3>
                <p className="text-sm">{patient.medicalHistory}</p>
              </div>

              <div className="bg-red-50 p-4 rounded-lg">
                <h3 className="font-semibold text-red-800 mb-2 flex items-center">
                  <Activity className="w-4 h-4 mr-2" />
                  AI Diagnosis
                </h3>
                <p className="text-sm">{patient.diagnosis}</p>
                <button className="mt-2 bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700 transition-colors">
                  Run Full Diagnostic Analysis
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <MainLayout>
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-800 mb-2">Hospital Management System</h1>
                <p className="text-gray-600">Advanced patient management with AI-powered diagnostics</p>
              </div>
              <div className="flex space-x-4">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="csv-upload"
                />
                <label
                  htmlFor="csv-upload"
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
                >
                  Upload CSV
                </label>
                <button
                  onClick={() => setShowAddForm(true)}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
                >
                  Add Patient
                </button>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <div className="bg-white rounded-lg shadow-md p-4 mb-6">
            <div className="flex space-x-4">
              {['dashboard', 'patients', 'analytics'].map((view) => (
                <button
                  key={view}
                  onClick={() => setActiveView(view)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    activeView === view
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {view.charAt(0).toUpperCase() + view.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Dashboard View */}
          {activeView === 'dashboard' && (
            <div className="space-y-6">
              {/* Stats Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {getDashboardStats.map((stat, index) => {
                  const IconComponent = stat.icon;
                  return (
                    <div key={index} className="bg-white rounded-lg shadow-md p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                          <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                        </div>
                        <div className={`p-3 rounded-full`} style={{ backgroundColor: stat.color + '20' }}>
                          <IconComponent className="w-6 h-6" style={{ color: stat.color }} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Priority Distribution Pie Chart */}
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4">Patient Priority Distribution</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={getPriorityDistribution}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${value}`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {getPriorityDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Department Distribution Pie Chart */}
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4">Patients by Department</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={getDepartmentStats}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${value}`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {getDepartmentStats.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Age Distribution Bar Chart */}
                <div className="bg-white rounded-lg shadow-md p-6 lg:col-span-2">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4">Age Distribution</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={getAgeDistribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="ageRange" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="count" fill="#3B82F6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* NEW: Enhanced Patients View with Filtering */}
          {activeView === 'patients' && (
            <div className="space-y-6">
              {/* Filter Controls */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex justify-between items-center mb-4">
                  <div className="flex items-center space-x-4">
                    <h3 className="text-lg font-semibold text-gray-800">Patient List</h3>
                    <span className="text-sm text-gray-500">
                      Showing {filteredPatients.length} of {csvData.length} patients
                    </span>
                    {activeFiltersCount > 0 && (
                      <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                        {activeFiltersCount} filter{activeFiltersCount > 1 ? 's' : ''} active
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    {activeFiltersCount > 0 && (
                      <button
                        onClick={clearFilters}
                        className="flex items-center space-x-1 text-sm text-gray-600 hover:text-gray-800"
                      >
                        <X className="w-4 h-4" />
                        <span>Clear filters</span>
                      </button>
                    )}
                    <button
                      onClick={() => setShowFilters(!showFilters)}
                      className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors ${
                        showFilters ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      <Filter className="w-4 h-4" />
                      <span>Filters</span>
                    </button>
                  </div>
                </div>

                {/* Filter Panel */}
                {showFilters && (
                  <div className="border-t pt-4 mt-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                      {/* Search */}
                      <div className="xl:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
                        <input
                          type="text"
                          placeholder="Name, bed, symptoms, diagnosis..."
                          value={filters.searchTerm}
                          onChange={(e) => setFilters({ ...filters, searchTerm: e.target.value })}
                          className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>

                      {/* Priority Filter */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                        <select
                          value={filters.priority}
                          onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
                          className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">All Priorities</option>
                          {filterOptions.priorities.map(priority => (
                            <option key={priority} value={priority}>
                              {priority.charAt(0).toUpperCase() + priority.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Department Filter */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                        <select
                          value={filters.department}
                          onChange={(e) => setFilters({ ...filters, department: e.target.value })}
                          className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">All Departments</option>
                          {filterOptions.departments.map(dept => (
                            <option key={dept} value={dept}>{dept}</option>
                          ))}
                        </select>
                      </div>

                      {/* Status Filter */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <select
                          value={filters.status}
                          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                          className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">All Statuses</option>
                          {filterOptions.statuses.map(status => (
                            <option key={status} value={status}>
                              {status.charAt(0).toUpperCase() + status.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Bed Type Filter */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Bed Type</label>
                        <select
                          value={filters.bedType}
                          onChange={(e) => setFilters({ ...filters, bedType: e.target.value })}
                          className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">All Bed Types</option>
                          {filterOptions.bedTypes.map(bedType => (
                            <option key={bedType} value={bedType}>
                              {bedType.charAt(0).toUpperCase() + bedType.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                )}

                {/* Patient Cards */}
                <div className="mt-6">
                  {filteredPatients.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {filteredPatients.map((patient, index) => (
                        <PatientCard
                          key={index}
                          patient={patient}
                          onClick={setSelectedPatient}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-gray-500">No patients match the current filters.</p>
                      <button
                        onClick={clearFilters}
                        className="mt-2 text-blue-600 hover:text-blue-800"
                      >
                        Clear all filters
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

{/* Analytics View - Complete with all charts */}
          {activeView === 'analytics' && (
            <div className="space-y-6">
              {/* First Row - Original Priority and Department Charts */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Hospital Analytics</h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Priority Distribution */}
                  <div>
                    <h4 className="text-md font-medium text-gray-700 mb-2">Priority Distribution</h4>
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={getPriorityDistribution}
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                          label={({ name, value }) => `${name}: ${value}`}
                        >
                          {getPriorityDistribution.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Department Stats */}
                  <div>
                    <h4 className="text-md font-medium text-gray-700 mb-2">Department Distribution</h4>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={getDepartmentStats}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="value" fill="#10B981" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Second Row - New Analytics Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold mb-4">Monthly Admissions Trend</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={[
                      { month: 'Jan', admissions: 120 },
                      { month: 'Feb', admissions: 135 },
                      { month: 'Mar', admissions: 148 },
                      { month: 'Apr', admissions: 162 },
                      { month: 'May', admissions: 178 },
                      { month: 'Jun', admissions: 155 }
                    ]}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="admissions" stroke="#3B82F6" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold mb-4">Bed Occupancy by Type</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={getBedOccupancyByType}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="bedType" />
                      <YAxis />
                      <Tooltip formatter={(value, name) => [
                        name === 'occupied' ? `${value} occupied` : `${value}% rate`,
                        name === 'occupied' ? 'Beds' : 'Occupancy Rate'
                      ]} />
                      <Bar dataKey="occupied" fill="#3B82F6" name="occupied" />
                      <Bar dataKey="occupancyRate" fill="#10B981" name="occupancyRate" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Third Row - Department Bed Distribution */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold mb-4">Department Bed Distribution</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {getDepartmentBedDistribution.map((dept, index) => (
                    <div key={index} className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-800 mb-2">{dept.department}</h4>
                      <p className="text-2xl font-bold text-blue-600 mb-1">{dept.bedsOccupied}</p>
                      <p className="text-sm text-gray-600 mb-2">Beds Occupied</p>
                      <div className="text-xs text-gray-500">
                        <strong>Beds:</strong> {dept.bedNumbers.join(', ')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Fourth Row - Critical Metrics */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold mb-4">Critical Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-red-50 p-4 rounded-lg border-l-4 border-red-500">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-red-800 font-medium">Critical Patients</p>
                        <p className="text-2xl font-bold text-red-600">
                          {csvData.filter(p => p.priority === 'critical').length}
                        </p>
                      </div>
                      <AlertTriangle className="w-8 h-8 text-red-500" />
                    </div>
                  </div>
                  
                  <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-500">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-yellow-800 font-medium">Average Age</p>
                        <p className="text-2xl font-bold text-yellow-600">
                          {Math.round(csvData.reduce((sum, p) => sum + p.age, 0) / csvData.length) || 0}
                        </p>
                      </div>
                      <Calendar className="w-8 h-8 text-yellow-500" />
                    </div>
                  </div>
                  
                  <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-500">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-green-800 font-medium">Bed Utilization</p>
                        <p className="text-2xl font-bold text-green-600">
                          {Math.round((csvData.filter(p => p.status === 'inpatient' && p.bedNumber !== 'N/A').length / 80) * 100)}%
                        </p>
                      </div>
                      <TrendingUp className="w-8 h-8 text-green-500" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}


          {/* Patient Modal - unchanged */}
          {selectedPatient && (
            <PatientModal
              patient={selectedPatient}
              onClose={() => setSelectedPatient(null)}
            />
          )}

          {/* Add Patient Form Modal - unchanged */}
          {showAddForm && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div className="p-6">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold text-gray-800">Add New Patient</h2>
                    <button
                      onClick={() => setShowAddForm(false)}
                      className="text-gray-500 hover:text-gray-700 text-xl font-bold"
                    >
                      ×
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                      <input
                        type="text"
                        value={customPatient.name}
                        onChange={(e) => setCustomPatient({ ...customPatient, name: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Patient name"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Age</label>
                      <input
                        type="number"
                        value={customPatient.age}
                        onChange={(e) => setCustomPatient({ ...customPatient, age: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Age"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
                      <select
                        value={customPatient.gender}
                        onChange={(e) => setCustomPatient({ ...customPatient, gender: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="">Select gender</option>
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                      <input
                        type="text"
                        value={customPatient.department}
                        onChange={(e) => setCustomPatient({ ...customPatient, department: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Department"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Bed Number</label>
                      <input
                        type="text"
                        value={customPatient.bedNumber}
                        onChange={(e) => setCustomPatient({ ...customPatient, bedNumber: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Bed number (auto-generated if empty)"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Bed Type</label>
                      <select
                        value={customPatient.bedType}
                        onChange={(e) => setCustomPatient({ ...customPatient, bedType: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="general">General</option>
                        <option value="semi-private">Semi-private</option>
                        <option value="private">Private</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                      <select
                        value={customPatient.status}
                        onChange={(e) => setCustomPatient({ ...customPatient, status: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="inpatient">Inpatient</option>
                        <option value="outpatient">Outpatient</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                      <select
                        value={customPatient.priority}
                        onChange={(e) => setCustomPatient({ ...customPatient, priority: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="normal">Normal</option>
                        <option value="urgent">Urgent</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Admission Date</label>
                      <input
                        type="date"
                        value={customPatient.admissionDate}
                        onChange={(e) => setCustomPatient({ ...customPatient, admissionDate: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Symptoms</label>
                      <textarea
                        value={customPatient.symptoms}
                        onChange={(e) => setCustomPatient({ ...customPatient, symptoms: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        rows={3}
                        placeholder="Patient symptoms"
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Medical History</label>
                      <textarea
                        value={customPatient.medicalHistory}
                        onChange={(e) => setCustomPatient({ ...customPatient, medicalHistory: e.target.value })}
                        className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        rows={3}
                        placeholder="Medical history"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end space-x-4 mt-6">
                    <button
                      onClick={() => setShowAddForm(false)}
                      className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addCustomPatient}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Add Patient
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
};

export default HospitalManagementAgent;
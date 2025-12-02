// src/pages/Diagnostics.tsx

import { FC, useState, useEffect, useRef } from "react";
import MainLayout from "../components/layout/MainLayout";

interface DiagnosticResult {
  primary_diagnosis: string;
  confidence_score: number;
  differential_diagnoses: Array<{
    diagnosis: string;
    probability: number;
    reasoning: string;
  }>;
  severity: "normal" | "attention" | "critical";
  findings: string[];
  recommendations: string[];
  follow_up_questions: string[];
  first_aid_steps: string[];
  medications: Array<{
    medication: string;
    dosage: string;
    instructions: string;
    warning: string;
  }>;
  emergency_indicators: string[];
  follow_up?: string;
  sources?: string[];
}

const DiagnosticsPage: FC = () => {
  const [activeTab, setActiveTab] = useState<"upload" | "results" | "history">("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState<DiagnosticResult | null>(null);
  const [symptomInput, setSymptomInput] = useState("");
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [medicalHistory, setMedicalHistory] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [history, setHistory] = useState<DiagnosticResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("diagnosticHistory");
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch (e) {
        console.error("Error parsing saved history:", e);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("diagnosticHistory", JSON.stringify(history));
  }, [history]);

  const commonSymptoms = [
    "Headache",
    "Fever",
    "Cough",
    "Fatigue",
    "Shortness of breath",
    "Chest pain",
    "Nausea",
    "Dizziness",
    "Back pain",
    "Joint pain",
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleSymptomAdd = () => {
    const trimmed = symptomInput.trim();
    if (trimmed && !symptoms.includes(trimmed)) {
      setSymptoms([...symptoms, trimmed]);
      setSymptomInput("");
    }
  };

  const removeSymptom = (symptom: string) => {
    setSymptoms(symptoms.filter((s) => s !== symptom));
  };

  const addCommonSymptom = (symptom: string) => {
    if (!symptoms.includes(symptom)) {
      setSymptoms([...symptoms, symptom]);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "normal":
        return "bg-green-50 border-green-500 text-green-700";
      case "attention":
        return "bg-yellow-50 border-yellow-500 text-yellow-700";
      case "critical":
        return "bg-red-50 border-red-500 text-red-700";
      default:
        return "bg-gray-50 border-gray-500 text-gray-700";
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "normal":
        return "✓";
      case "attention":
        return "⚠️";
      case "critical":
        return "🚨";
      default:
        return "ℹ️";
    }
  };

  const getSeverityMessage = (severity: string) => {
    switch (severity) {
      case "normal":
        return "Results are within normal ranges or indicate manageable conditions.";
      case "attention":
        return "Results require medical attention and follow-up.";
      case "critical":
        return "Critical findings that need immediate medical attention.";
      default:
        return "Analysis completed.";
    }
  };

  const analyzeDiagnostics = async () => {
    if (files.length === 0 && symptoms.length === 0 && medicalHistory.trim() === "") {
      alert("Please upload at least one medical report, add symptoms, or enter medical history.");
      return;
    }

    setIsAnalyzing(true);
    setActiveTab("results");
    setError(null);

    try {
      const formData = new FormData();
      
      // Add files
      files.forEach((file) => formData.append("files", file));
      
      // Add other data
      formData.append("symptoms", JSON.stringify(symptoms));
      formData.append("medical_history", medicalHistory);

      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to analyze diagnostics");
      }

      const data: DiagnosticResult = await response.json();
      setResults(data);

      // Save to history
      setHistory((prev) => {
        const updated = [...prev, data];
        localStorage.setItem("diagnosticHistory", JSON.stringify(updated));
        return updated;
      });

    } catch (error) {
      console.error("Analysis error:", error);
      setError(error instanceof Error ? error.message : "Something went wrong while analyzing.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const renderUploadTab = () => (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Upload Medical Reports</h2>

      {/* File Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center mb-6 ${
          isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 mb-4 bg-blue-100 rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              ></path>
            </svg>
          </div>
          <p className="mb-2 text-lg font-semibold text-gray-700">Drag & drop files here</p>
          <p className="mb-4 text-sm text-gray-500">
            or{" "}
            <span className="text-blue-600 hover:underline cursor-pointer" onClick={() => fileInputRef.current?.click()}>
              browse files
            </span>
          </p>
          <p className="text-xs text-gray-500">Supported formats: PDF, JPG, PNG, DICOM, etc.</p>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.dcm,.dicom,.txt,.doc,.docx"
          />
        </div>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mb-8">
          <h3 className="font-medium text-gray-700 mb-2">Uploaded Files:</h3>
          <ul className="space-y-2">
            {files.map((file, index) => (
              <li key={index} className="flex items-center justify-between p-3 bg-white border rounded-lg">
                <div className="flex items-center">
                  <div className="p-2 bg-blue-100 rounded">📄</div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-700">{file.name}</p>
                    <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
                <button onClick={() => removeFile(index)} className="text-red-500 hover:text-red-700">
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Symptom Section */}
      <div className="mb-8">
        <h3 className="font-medium text-gray-700 mb-3">Add Your Symptoms (Optional)</h3>
        <p className="text-sm text-gray-600 mb-4">
          Adding your symptoms will help our AI provide more accurate insights.
        </p>

        {/* Symptom Input */}
        <div className="flex mb-2">
          <input
            type="text"
            value={symptomInput}
            onChange={(e) => setSymptomInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSymptomAdd()}
            placeholder="Type a symptom..."
            className="flex-grow p-2 border border-gray-300 rounded-l focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button onClick={handleSymptomAdd} className="bg-blue-600 text-white py-2 px-4 rounded-r hover:bg-blue-700">
            Add
          </button>
        </div>

        {/* Common Symptoms */}
        <div className="mb-4">
          <p className="text-xs text-gray-600 mb-2">Common symptoms:</p>
          <div className="flex flex-wrap gap-2">
            {commonSymptoms.map((symptom, index) => (
              <button
                key={index}
                onClick={() => addCommonSymptom(symptom)}
                className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full hover:bg-gray-200"
              >
                + {symptom}
              </button>
            ))}
          </div>
        </div>

        {/* Selected Symptoms */}
        {symptoms.length > 0 && (
          <div>
            <p className="text-xs text-gray-600 mb-2">Your symptoms:</p>
            <div className="flex flex-wrap gap-2">
              {symptoms.map((symptom, index) => (
                <div key={index} className="flex items-center bg-blue-100 text-blue-800 px-3 py-1 rounded-full">
                  <span className="text-sm">{symptom}</span>
                  <button onClick={() => removeSymptom(symptom)} className="ml-2 text-blue-600 hover:text-blue-800">
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Medical History Section */}
      <div className="mb-8">
        <h3 className="font-medium text-gray-700 mb-3">Medical History (Optional)</h3>
        <textarea
          placeholder="Enter any relevant medical history or additional information here..."
          value={medicalHistory}
          onChange={(e) => setMedicalHistory(e.target.value)}
          className="w-full p-3 border border-gray-300 rounded h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
        ></textarea>
      </div>

      {/* Analyze Button */}
      <div className="flex justify-center">
        <button
          onClick={analyzeDiagnostics}
          disabled={isAnalyzing}
          className="bg-blue-600 text-white py-3 px-8 rounded-lg text-lg font-semibold hover:bg-blue-700 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isAnalyzing ? "Analyzing..." : "Analyze Reports"}
        </button>
      </div>
    </div>
  );

  const renderResultsTab = () => (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Diagnostic Results</h2>

      {isAnalyzing ? (
        <div className="flex flex-col items-center justify-center py-10">
          <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-700 font-medium">Analyzing your medical reports...</p>
          <p className="text-sm text-gray-500 mt-2">This may take a few moments</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-start">
            <div className="text-red-500 mr-3">❌</div>
            <div>
              <h3 className="font-bold text-red-800">Analysis Error</h3>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      ) : results ? (
        <div className="space-y-6">
          {/* Primary Diagnosis Card */}
          <div className={`p-4 rounded-lg border-l-4 ${getSeverityColor(results.severity)}`}>
            <div className="flex items-start">
              <div className="text-2xl mr-3">{getSeverityIcon(results.severity)}</div>
              <div className="flex-1">
                <h3 className="text-xl font-bold mb-2">{results.primary_diagnosis}</h3>
                <p className="text-sm mb-2">{getSeverityMessage(results.severity)}</p>
                <div className="flex items-center space-x-4">
                  <span className="text-sm font-medium">Confidence: {Math.round(results.confidence_score * 100)}%</span>
                  {results.follow_up && (
                    <span className="text-sm">
                      <strong>Follow-up:</strong> {results.follow_up}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Differential Diagnoses */}
          {results.differential_diagnoses && results.differential_diagnoses.length > 0 && (
            <div className="bg-white border rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">Alternative Diagnoses</h3>
              <div className="space-y-3">
                {results.differential_diagnoses.map((diff, index) => (
                  <div key={index} className="border-l-2 border-gray-300 pl-4">
                    <div className="flex justify-between items-start mb-1">
                      <h4 className="font-medium text-gray-800">{diff.diagnosis}</h4>
                      <span className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">
                        {Math.round(diff.probability * 100)}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{diff.reasoning}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Findings */}
          <div className="bg-white border rounded-lg p-4">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Key Findings</h3>
            <ul className="space-y-2">
              {results.findings.map((finding, index) => (
                <li key={index} className="flex items-start">
                  <span className="text-blue-600 mr-2">•</span>
                  <span className="text-gray-700">{finding}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Emergency Indicators */}
          {results.emergency_indicators && results.emergency_indicators.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-red-800 mb-3 flex items-center">
                <span className="mr-2">🚨</span> Emergency Indicators
              </h3>
              <ul className="space-y-2">
                {results.emergency_indicators.map((indicator, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span className="text-red-700">{indicator}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          <div className="bg-white border rounded-lg p-4">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Recommendations</h3>
            <ul className="space-y-3">
              {results.recommendations.map((rec, index) => (
                <li key={index} className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 w-6 h-6 rounded-full flex items-center justify-center mr-3 shrink-0 text-sm font-medium">
                    {index + 1}
                  </div>
                  <span className="text-gray-700">{rec}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* First Aid Steps */}
          {results.first_aid_steps && results.first_aid_steps.length > 0 && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-green-800 mb-3 flex items-center">
                <span className="mr-2">🩹</span> First Aid Steps
              </h3>
              <ul className="space-y-2">
                {results.first_aid_steps.map((step, index) => (
                  <li key={index} className="flex items-start">
                    <div className="bg-green-100 text-green-800 w-6 h-6 rounded-full flex items-center justify-center mr-3 shrink-0 text-sm font-medium">
                      {index + 1}
                    </div>
                    <span className="text-green-700">{step}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Medications */}
          {results.medications && results.medications.length > 0 && (
            <div className="bg-white border rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                <span className="mr-2">💊</span> Suggested Medications
              </h3>
              <div className="space-y-4">
                {results.medications.map((med, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-3">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-medium text-gray-800">{med.medication}</h4>
                      <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded">{med.dosage}</span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{med.instructions}</p>
                    {med.warning && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
                        <p className="text-sm text-yellow-800">
                          <strong>⚠️ Warning:</strong> {med.warning}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Follow-up Questions */}
          {results.follow_up_questions && results.follow_up_questions.length > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-blue-800 mb-3 flex items-center">
                <span className="mr-2">❓</span> Follow-up Questions for Your Doctor
              </h3>
              <ul className="space-y-2">
                {results.follow_up_questions.map((question, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span className="text-blue-700">{question}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sources */}
          {results.sources && results.sources.length > 0 && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                <span className="mr-2">📚</span> Sources
              </h3>
              <ul className="space-y-1">
                {results.sources.map((source, index) => (
                  <li key={index} className="text-sm text-gray-600">
                    <span className="mr-2">•</span>
                    {source.includes('http') ? (
                      <a href={source} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {source}
                      </a>
                    ) : (
                      source
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-4 pt-4">
            <button className="flex items-center bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700">
              <span className="mr-2">💾</span> Save Results
            </button>
            <button className="flex items-center bg-white border border-blue-600 text-blue-600 py-2 px-4 rounded hover:bg-blue-50">
              <span className="mr-2">🖨️</span> Print Report
            </button>
            <button className="flex items-center bg-white border border-gray-300 text-gray-700 py-2 px-4 rounded hover:bg-gray-50">
              <span className="mr-2">✉️</span> Email Results
            </button>
            <button 
              onClick={() => {
                setResults(null);
                setError(null);
                setActiveTab("upload");
              }}
              className="flex items-center bg-gray-600 text-white py-2 px-4 rounded hover:bg-gray-700"
            >
              <span className="mr-2">🔄</span> New Analysis
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-10 text-gray-500">
          <div className="text-6xl mb-4">📋</div>
          <p className="text-lg">No results to display</p>
          <p className="text-sm mt-2">Please upload medical reports and analyze them.</p>
          <button 
            onClick={() => setActiveTab("upload")}
            className="mt-4 bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
          >
            Start Analysis
          </button>
        </div>
      )}
    </div>
  );

  const renderHistoryTab = () => (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">Diagnostic History</h2>
      {history.length === 0 ? (
        <div className="text-center py-10 text-gray-500">
          <div className="text-6xl mb-4">📚</div>
          <p className="text-lg">No saved results yet</p>
          <p className="text-sm mt-2">Your diagnostic history will appear here after you analyze reports.</p>
          <button
            onClick={() => setActiveTab("upload")}
            className="mt-4 bg-blue-600 text-white py-2 px-6 rounded hover:bg-blue-700"
          >
            Start New Diagnostic
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {history.map((item, idx) => (
            <div key={idx} className="bg-white border rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <h3 className="text-lg font-semibold text-gray-800">{item.primary_diagnosis}</h3>
                <span className={`px-2 py-1 rounded text-sm font-medium ${
                  item.severity === "normal" ? "bg-green-100 text-green-800" :
                  item.severity === "attention" ? "bg-yellow-100 text-yellow-800" :
                  "bg-red-100 text-red-800"
                }`}>
                  {item.severity}
                </span>
              </div>
              
              <div className="mb-3">
                <span className="text-sm font-semibold text-gray-700">Confidence: </span>
                <span className="text-sm text-gray-600">{Math.round(item.confidence_score * 100)}%</span>
              </div>

              <div className="mb-3">
                <p className="text-sm font-semibold text-gray-700 mb-1">Key Findings:</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {item.findings.slice(0, 3).map((finding, i) => (
                    <li key={i} className="flex items-start">
                      <span className="text-blue-600 mr-2">•</span>
                      {finding}
                    </li>
                  ))}
                  {item.findings.length > 3 && (
                    <li className="text-gray-500 italic">...and {item.findings.length - 3} more</li>
                  )}
                </ul>
              </div>

              <div className="mb-3">
                <p className="text-sm font-semibold text-gray-700 mb-1">Top Recommendations:</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {item.recommendations.slice(0, 2).map((rec, i) => (
                    <li key={i} className="flex items-start">
                      <span className="text-green-600 mr-2">•</span>
                      {rec}
                    </li>
                  ))}
                  {item.recommendations.length > 2 && (
                    <li className="text-gray-500 italic">...and {item.recommendations.length - 2} more</li>
                  )}
                </ul>
              </div>

              {item.follow_up && (
                <div className="bg-blue-50 rounded p-2 mt-3">
                  <p className="text-sm">
                    <strong className="text-blue-800">Follow-up:</strong>
                    <span className="text-blue-700 ml-1">{item.follow_up}</span>
                  </p>
                </div>
              )}
            </div>
          ))}
          
          <div className="text-center mt-6">
            <button
              onClick={() => setActiveTab("upload")}
              className="bg-blue-600 text-white py-2 px-6 rounded hover:bg-blue-700"
            >
              Start New Diagnostic
            </button>
          </div>
        </div>
      )}
    </div>
  );

  return (
  <MainLayout>
    <div className="bg-white rounded-xl shadow-md overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-4">
        <h1 className="text-2xl font-bold text-white">AI Diagnostic Assistant</h1>
        <p className="text-blue-100 text-sm">
          Upload your medical reports for AI-powered insights and recommendations
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        <button
          className={`flex-1 py-3 px-4 text-center ${
            activeTab === "upload"
              ? "border-b-2 border-blue-600 text-blue-600 font-medium"
              : "text-gray-600 hover:text-blue-500"
          }`}
          onClick={() => setActiveTab("upload")}
        >
          Upload Reports
        </button>
        <button
          className={`flex-1 py-3 px-4 text-center ${
            activeTab === "results"
              ? "border-b-2 border-blue-600 text-blue-600 font-medium"
              : "text-gray-600 hover:text-blue-500"
          }`}
          onClick={() => setActiveTab("results")}
        >
          Results
        </button>
        <button
          className={`flex-1 py-3 px-4 text-center ${
            activeTab === "history"
              ? "border-b-2 border-blue-600 text-blue-600 font-medium"
              : "text-gray-600 hover:text-blue-500"
          }`}
          onClick={() => setActiveTab("history")}
        >
          History
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "upload" && renderUploadTab()}
      {activeTab === "results" && renderResultsTab()}
      {activeTab === "history" && renderHistoryTab()}
    </div>

    {/* Information Cards */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
      <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-100">
        <div className="text-blue-600 text-lg mb-2">🔍 Advanced Analysis</div>
        <p className="text-sm text-gray-600">
          Our AI analyzes your reports using data from millions of medical cases, providing insights that might be missed
          in standard reviews.
        </p>
      </div>
      <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-100">
        <div className="text-blue-600 text-lg mb-2">🔒 Secure & Private</div>
        <p className="text-sm text-gray-600">
          Your medical data is encrypted and securely processed. We adhere to strict privacy standards and regulations.
        </p>
      </div>
      <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-100">
        <div className="text-blue-600 text-lg mb-2">👩‍⚕️ Not a Replacement</div>
        <p className="text-sm text-gray-600">
          Our AI provides insights to help you and your doctor make informed decisions, but does not replace professional
          medical care.
        </p>
      </div>
    </div>

    {/* Disclaimer */}
    <div className="mt-8 p-4 border border-orange-200 bg-orange-50 rounded-lg">
      <div className="flex items-start">
        <div className="text-orange-500 mr-3">⚠️</div>
        <div>
          <h3 className="font-bold text-orange-800">Medical Disclaimer</h3>
          <p className="text-sm text-orange-700">
            The diagnostic information provided by MediMind AI is for informational purposes only and is not a substitute
            for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other
            qualified health provider with any questions you may have regarding a medical condition.
          </p>
        </div>
      </div>
    </div>
  </MainLayout>
);
};

export default DiagnosticsPage;

// src/components/HeroSection.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
// 1️⃣ Make sure the file exists at src/assets/backGroundimg.png
import bgImg from '../../assets/backGroundimg.png';

const HeroSection: React.FC = () => {
  const navigate = useNavigate();

  return (
    <section
      className="relative text-center py-10 px-5 rounded-xl shadow-md mb-8 overflow-hidden"
      style={{
        backgroundImage: `url(${bgImg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Lower-opacity overlay so the image shows through */}
      <div className="absolute inset-0 bg-white bg-opacity-30"></div>

      {/* Content */}
      <div className="relative z-10">
        <h1 className="text-4xl font-bold text-blue-600 mb-4">
          Medi<span className="text-green-500">Mind AI</span>
        </h1>

        <p className="text-lg text-gray-700 max-w-3xl mx-auto mb-6">
          Transforming Healthcare with Artificial Intelligence
        </p>

        <p className="text-base text-gray-600 max-w-2xl mx-auto mb-8">
          Experience the future of healthcare with our AI-powered platform. Get instant insights from patient reports, 
          manage hospital operations efficiently, and access reliable medical information with ease.
        </p>

        <div className="flex flex-wrap justify-center gap-4">
          <button
            onClick={() => navigate('/diagnostics')}
            className="bg-blue-600 text-white px-6 py-2.5 rounded-md font-medium hover:bg-blue-700 transition-colors shadow-sm"
          >
            Start Diagnosis
          </button>

          <button
            onClick={() => navigate('/ask')}
            className="border-2 border-blue-600 text-blue-600 px-6 py-2.5 rounded-md font-medium hover:bg-blue-50 transition-colors"
          >
            Search Medical Info
          </button>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;

import React from 'react';

const Footer: React.FC = () => {
  return (
    <footer className="text-center p-5 bg-white text-gray-500 rounded-xl shadow-md mt-8">
      <div className="flex flex-col md:flex-row justify-center items-center space-y-2 md:space-y-0 md:space-x-6">
        <a href="#" className="hover:text-gray-800 transition-colors">About Us</a>
        <a href="#" className="hover:text-gray-800 transition-colors">Privacy Policy</a>
        <a href="#" className="hover:text-gray-800 transition-colors">Terms of Service</a>
      </div>
      <div className="mt-4">
        <p>© 2025 MediMind AI. All rights reserved.</p>
        <p className="text-sm mt-2">Powered by AI & Streamlit</p>
      </div>
    </footer>
  );
};

export default Footer;
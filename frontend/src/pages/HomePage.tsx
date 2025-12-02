import type { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/layout/MainLayout';

const HomePage: FC = () => {
  const navigate = useNavigate();

  return (
    <MainLayout>
      
      {/* Contact Us */}
      <section className="mt-10 bg-white p-6 rounded shadow">
        <div className="text-blue-600 font-bold text-lg">📞 Contact Us -</div>
        <p className="text-md text-gray-700 mt-1">
          You can contact us using the following number:
        </p>
        <p className="text-xl font-semibold text-gray-900 mt-2">
          +91-9876543210
        </p>
      </section>
    </MainLayout>
  );
};

export default HomePage;

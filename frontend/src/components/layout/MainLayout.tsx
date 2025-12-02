import type { FC, ReactNode } from 'react';
import Header from './Header';
import HeroSection from './HeroSection';
import Footer from './Footer';  // <-- import the Footer component

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="bg-blue-50 min-h-screen flex flex-col">
      <Header />
      <HeroSection />  
      <main className="px-8 py-6 flex-grow">{children}</main>
      <div className="px-8">
        <Footer />
      </div>
    </div>
  );
};

export default MainLayout;
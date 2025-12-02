//import styles from './Button.module.css';

interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
}

const Button = ({ children, variant = 'primary', onClick, type = 'button' }: ButtonProps) => {
  return (
    <button 
      //className={`${styles.button} ${styles[variant]}`}
      onClick={onClick}
      type={type}
    >
      {children}
    </button>
  );
};

export default Button;
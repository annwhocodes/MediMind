import { FC, useState, useRef, useEffect } from 'react';
import MainLayout from '../components/layout/MainLayout';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../context/AuthContext';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  sources?: Array<{
    name: string;
    type?: string;
    url?: string;
    description?: string;
  } | string>;
}

const AskAIPage: FC = () => {
  const { user } = useAuth(); // NEW: Get user context
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'ai',
      content: 'Hello! I\'m MediMind AI. How can I assist you with your medical questions today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showFaqs, setShowFaqs] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Backend API base URL - adjust this to match your backend URL
  const API_BASE_URL = 'http://127.0.0.1:8001';

  // Sample FAQs
  const faqs = [
    "What are common symptoms of diabetes?",
    "How can I lower my blood pressure naturally?",
    "What vaccination schedule is recommended for children?",
    "How to identify signs of a stroke?",
    "What causes migraines and how to prevent them?"
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessageToBackend = async (message: string, conversationHistory: ChatMessage[]): Promise<{ response: string; sources?: any[] }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          conversation_history: conversationHistory.map(msg => ({
            role: msg.role,
            content: msg.content
          })),
          // Pass username as patient_id if it's a patient/user role
          patient_id: user?.role === 'user' ? user.username : undefined
        }),
      });

      if (!response.ok) {
        if (response.status === 503) {
          throw new Error('Medical AI service is currently unavailable. Please try again later.');
        } else if (response.status >= 500) {
          throw new Error('Server error occurred. Please try again later.');
        } else if (response.status >= 400) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Invalid request. Please check your input.');
        } else {
          throw new Error('An unexpected error occurred. Please try again.');
        }
      }

      const data = await response.json();
      return {
        response: data.response,
        sources: data.sources
      };
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Unable to connect to the medical AI service. Please check your internet connection and try again.');
      }
      throw error;
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    // Clear any previous errors
    setError(null);

    // Add user message
    const userMessage: ChatMessage = { role: 'user', content: input };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setShowFaqs(false);
    setIsLoading(true);

    try {
      // Send message to backend
      const result = await sendMessageToBackend(input, messages);

      // Add AI response
      const aiResponse: ChatMessage = {
        role: 'ai',
        content: result.response,
        sources: result.sources
      };

      setMessages(prev => [...prev, aiResponse]);
    } catch (error) {
      console.error('Error sending message:', error);

      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
      setError(errorMessage);

      // Add error message to chat
      const errorResponse: ChatMessage = {
        role: 'ai',
        content: `I apologize, but I encountered an error: ${errorMessage}. Please try again or contact support if the problem persists.`
      };

      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFaqClick = (faq: string) => {
    setInput(faq);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      // For now, we'll just show a message about file upload
      // You can implement file upload to your backend later
      const fileName = files[0].name;
      const fileMessage: ChatMessage = {
        role: 'user',
        content: `Uploaded file: ${fileName}`
      };
      const aiResponse: ChatMessage = {
        role: 'ai',
        content: `I've received your file "${fileName}". Currently, file analysis is handled through the diagnostic endpoint. For now, please describe what specific questions you have about this medical report, and I'll do my best to provide general guidance.`
      };

      setMessages(prev => [...prev, fileMessage, aiResponse]);
      setShowFaqs(false);
    }
  };

  const triggerFileUpload = () => {
    fileInputRef.current?.click();
  };

  const renderMessageContent = (message: ChatMessage) => {
    return (
      <div>
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown
            components={{
              h1: ({ node, ...props }: any) => <h1 className="text-xl font-bold my-2 text-blue-800" {...props} />,
              h2: ({ node, ...props }: any) => <h2 className="text-lg font-bold my-2 text-blue-700" {...props} />,
              h3: ({ node, ...props }: any) => <h3 className="text-md font-semibold my-1 text-blue-600" {...props} />,
              ul: ({ node, ...props }: any) => <ul className="list-disc list-inside my-2 space-y-1" {...props} />,
              li: ({ node, ...props }: any) => <li className="text-gray-800" {...props} />,
              strong: ({ node, ...props }: any) => <strong className="font-semibold text-gray-900" {...props} />,
              p: ({ node, ...props }: any) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-medium text-gray-600 mb-2">Sources:</p>
            <ul className="text-xs text-gray-500 space-y-1">
              {message.sources.map((source, index) => {
                const isString = typeof source === 'string';
                const sourceName = isString ? source : source.name;
                const sourceUrl = isString ? (source.includes('http') ? source : undefined) : source.url;

                return (
                  <li key={index} className="flex items-start">
                    <span className="mr-2">•</span>
                    {sourceUrl ? (
                      <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {sourceName}
                      </a>
                    ) : (
                      <span>{sourceName}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <MainLayout>
      <div className="flex flex-col h-[calc(100vh-200px)] bg-white rounded-xl shadow-md overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-4">
          <h2 className="text-2xl font-bold text-white">
            Ask<span className="text-green-300">AI</span> - Medical Assistant
          </h2>
          <p className="text-blue-100 text-sm">
            Get answers to your medical questions from our AI-powered medical assistant
          </p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <div className="flex">
              <div className="text-red-500 mr-2">⚠️</div>
              <div className="text-sm text-red-700">{error}</div>
            </div>
          </div>
        )}

        {/* Message Area */}
        <div className="flex-grow p-4 overflow-y-auto bg-gray-50">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`mb-4 ${message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}`}
            >
              <div
                className={`max-w-[80%] p-3 rounded-lg ${message.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none'
                  : 'bg-white text-gray-800 shadow rounded-tl-none border border-gray-200'
                  }`}
              >
                {renderMessageContent(message)}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-white text-gray-500 p-3 rounded-lg shadow rounded-tl-none border border-gray-200">
                <div className="flex items-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                  <span className="text-sm text-gray-500">MediMind AI is thinking...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* FAQs */}
        {showFaqs && (
          <div className="px-4 py-3 bg-gray-100 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Frequently Asked Questions:</h3>
            <div className="flex flex-wrap gap-2">
              {faqs.map((faq, index) => (
                <button
                  key={index}
                  onClick={() => handleFaqClick(faq)}
                  className="bg-white border border-gray-300 text-gray-700 text-sm px-3 py-1 rounded-full hover:bg-gray-50 transition-colors"
                >
                  {faq}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 border-t border-gray-200 bg-white">
          <div className="flex items-center">
            <button
              onClick={triggerFileUpload}
              className="p-2 text-gray-500 hover:text-blue-600 focus:outline-none transition-colors"
              title="Upload medical report"
            >
              📎
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
              />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !isLoading && handleSendMessage()}
              placeholder="Ask a medical question or upload your report..."
              className="flex-grow p-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              className={`p-2 px-4 rounded-r-md transition-colors ${input.trim() && !isLoading
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>

          <div className="mt-2 text-xs text-gray-500 flex justify-between items-center">
            <div>
              MediMind AI provides general information only. Consult a healthcare professional for medical advice.
            </div>
            <button
              onClick={() => setShowFaqs(!showFaqs)}
              className="text-blue-600 hover:underline"
            >
              {showFaqs ? 'Hide FAQs' : 'Show FAQs'}
            </button>
          </div>
        </div>
      </div>

      {/* Medical Topics Section */}
      <section className="mt-8 bg-white p-6 rounded-xl shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">Popular Medical Topics</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {['Cardiology', 'Neurology', 'Pediatrics', 'Dermatology', 'Orthopedics', 'Gynecology', 'Oncology', 'Nutrition'].map((topic, index) => (
            <div
              key={index}
              className="bg-blue-50 border border-blue-100 p-4 rounded-lg hover:bg-blue-100 cursor-pointer transition-colors"
              onClick={() => handleFaqClick(`Tell me about ${topic.toLowerCase()}`)}
            >
              <h3 className="font-medium text-blue-800">{topic}</h3>
              <p className="text-xs text-gray-600 mt-1">Common questions and information</p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <section className="mt-6 p-4 border border-orange-200 bg-orange-50 rounded-lg">
        <div className="flex items-start">
          <div className="text-orange-500 mr-3">⚠️</div>
          <div>
            <h3 className="font-bold text-orange-800">Important Disclaimer</h3>
            <p className="text-sm text-orange-700">
              MediMind AI is designed to provide general information only and should not be used as a substitute for professional medical advice,
              diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may
              have regarding a medical condition.
            </p>
          </div>
        </div>
      </section>
    </MainLayout>
  );
};

export default AskAIPage;
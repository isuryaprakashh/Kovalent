import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, User, Bot, Sparkles } from 'lucide-react';

export function ChatDrawer({ isOpen, onClose, data }) {
  const [messages, setMessages] = useState([
    { role: 'bot', content: "Hello! I'm the Kovalent Intelligence Engine. I have analyzed your cluster topology and identified " + data.incidents.length + " pending incidents. How can I help you today?" }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      const result = await response.json();
      setMessages(prev => [...prev, { role: 'bot', content: result.response }]);
    } catch (err) {
      console.error('Chat failed:', err);
      setMessages(prev => [...prev, { role: 'bot', content: "I'm sorry, I'm having trouble connecting to the intelligence engine right now. Please check if the backend is running." }]);
    } finally {
      setIsTyping(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed top-0 right-0 h-full w-[450px] bg-[#080808] border-l border-[#333333] flex flex-col z-[110] shadow-2xl animate-in slide-in-from-right duration-300">
      <div className="p-8 border-b border-[#333333] flex justify-between items-center bg-[#101010]/50">
        <h2 className="text-[20px] font-bold text-[#F3F3F3] flex items-center gap-2">
          <MessageSquare size={20} className="text-[#E7C59A]" />
          Kovalent Chat
        </h2>
        <button onClick={onClose} className="text-[#949494] hover:text-[#F3F3F3] transition-colors">
          <X size={24} />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 space-y-6 scroll-smooth">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-[4px] flex items-center justify-center shrink-0 ${msg.role === 'bot' ? 'bg-[#E7C59A]/20 text-[#E7C59A]' : 'bg-[#333333] text-[#F3F3F3]'}`}>
              {msg.role === 'bot' ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div className={`max-w-[85%] p-4 rounded-[8px] text-[14px] leading-relaxed ${msg.role === 'bot' ? 'bg-[#101010] border border-[#333333] text-[#F3F3F3]' : 'bg-[#E7C59A] text-[#101010] font-bold'}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-[4px] bg-[#E7C59A]/20 text-[#E7C59A] flex items-center justify-center shrink-0">
              <Bot size={18} />
            </div>
            <div className="bg-[#101010] border border-[#333333] p-4 rounded-[8px] flex gap-1 items-center">
              <div className="w-1.5 h-1.5 bg-[#E7C59A] rounded-full animate-bounce" />
              <div className="w-1.5 h-1.5 bg-[#E7C59A] rounded-full animate-bounce [animation-delay:0.2s]" />
              <div className="w-1.5 h-1.5 bg-[#E7C59A] rounded-full animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSend} className="p-8 border-t border-[#333333] bg-[#101010]/30">
        <div className="relative">
          <input 
            type="text" 
            placeholder="Ask anything about your cluster..."
            value={input}
            onChange={e => setInput(e.target.value)}
            className="w-full bg-[#080808] border border-[#333333] rounded-[8px] pl-4 pr-12 py-3 text-[14px] text-[#F3F3F3] focus:outline-none focus:border-[#E7C59A]/50 transition-all"
          />
          <button 
            type="submit"
            disabled={!input.trim() || isTyping}
            className="absolute right-2 top-2 p-1.5 bg-[#E7C59A] text-[#101010] rounded-[6px] hover:bg-[#d6b48a] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="mt-4 text-[11px] text-[#555] flex items-center gap-1.5 justify-center uppercase tracking-wider font-bold">
          <Sparkles size={10} /> AI-Powered Cluster Analysis
        </p>
      </form>
    </div>
  );
}

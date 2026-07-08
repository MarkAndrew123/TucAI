import { useState, useRef, useEffect } from 'react';
import { 
  Send, Paperclip, Video, FileVideo, Bot, User, List, 
  ArrowRight, ArrowLeft, Mail, Lock, Check,
  Play, Sparkles, Sliders, Zap, LogOut,
  Plus, MessageSquare, Settings, Trash2, Menu, CreditCard, Upload
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import HubModal from './components/HubModal';

const TypewriterText = ({ text }) => {
  const [displayedText, setDisplayedText] = useState('');

  useEffect(() => {
    setDisplayedText('');
    let i = 0;
    const interval = setInterval(() => {
      setDisplayedText(text.slice(0, i + 1));
      i++;
      if (i >= text.length) clearInterval(interval);
    }, 15);
    return () => clearInterval(interval);
  }, [text]);

  return <span>{displayedText}</span>;
};

// Custom SVG icons for brand links (since lucide-react brand icons are removed in this version)
const GithubIcon = (props) => (
  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
  </svg>
);

const TwitterIcon = (props) => (
  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z" />
  </svg>
);

const LinkedinIcon = (props) => (
  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect x="2" y="9" width="4" height="12" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);

const YoutubeIcon = (props) => (
  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z" />
    <polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02" fill="currentColor" />
  </svg>
);

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'https://tuc-backend-530507298858.us-central1.run.app'
  : `https://tuc-backend-530507298858.us-central1.run.app`;

function App() {
  // Navigation & Session State
  const [view, setView] = useState('landing');
  const [showHubModal, setShowHubModal] = useState(false); // 'landing' | 'login' | 'signup' | 'app' | 'pricing'
  const [user, setUser] = useState(null);
  const [isYearly, setIsYearly] = useState(false);

  // Auth Forms State
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');

  // App Editor Layout State
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Session State
  const [sessionsList, setSessionsList] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  
  // Workspace Revamp State
  const [libraryTab, setLibraryTab] = useState('uploads');
  const [uploadedVideos, setUploadedVideos] = useState([]);

  useEffect(() => {
    if (view === 'library' && libraryTab === 'uploads') {
      const fetchVideos = async () => {
        try {
          const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/api/videos`, {
            headers: { Authorization: `Bearer ${user?.token}` }
          });
          setUploadedVideos(res.data.videos || []);
          if (res.data.total_storage_bytes !== undefined) {
            setTotalStorageBytes(res.data.total_storage_bytes);
          }
        } catch (err) {
          console.error('Failed to fetch videos', err);
        }
      };
      if (user?.token) {
        fetchVideos();
      }
    }
  }, [view, libraryTab, user?.token]);

  const loadSessions = async (token, restoreLatest = false) => {
    try {
      const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/chat/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const sessions = res.data.sessions || [];
      setSessionsList(sessions);
      
      // On page reload, auto-load the most recent session
      if (restoreLatest && sessions.length > 0 && !activeSessionId) {
        const latest = sessions[0]; // already sorted by updated_at desc
        loadSessionDetails(latest.id, token);
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
      if (e.response && e.response.status === 401) {
        handleLogout();
      }
    }
  };

  const loadSessionDetails = async (id, token) => {
    try {
      const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/chat/sessions/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = res.data.session;
      if (data.chat_history && data.chat_history.length > 0) {
        const loadedMsgs = data.chat_history.map((msg, i) => ({
          id: Date.now() + i,
          role: msg.role === 'user' ? 'user' : 'bot',
          text: msg.content,
          file: msg.file,
          videoUrl: msg.videoUrl,
          status: msg.status,
          candidates: msg.candidates,
          timeline: msg.timeline,
          project_id: msg.project_id
        }));
        setMessages(loadedMsgs);

        // Resume polling if there's an active job
        const processingMsg = loadedMsgs.find(m => m.status === 'processing' && m.project_id);
        if (processingMsg) {
          setIsProcessing(true);
          setProcessingStage('queued');
          startPolling(processingMsg.project_id);
        }
      } else {
        setMessages([]);
      }
      setActiveSessionId(id);
    } catch (e) {
      console.error('Failed to load session details:', e);
      if (e.response && e.response.status === 401) {
        handleLogout();
      }
    }
  };

  const deleteSession = async (id, e) => {
    e.stopPropagation();
    try {
      await axios.delete(`https://tuc-backend-530507298858.us-central1.run.app/chat/sessions/${id}`, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      setSessionsList(prev => prev.filter(s => s.id !== id));
      if (activeSessionId === id) {
        createNewSession();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const createNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setFile(null);
  };



  // Main Chat App State (Existing Logic)
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadSpeed, setUploadSpeed] = useState(0);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const uploadStatsRef = useRef({ startTime: 0, lastLoaded: 0, lastTime: 0 });
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [localVideos, setLocalVideos] = useState([]);
  const [totalStorageBytes, setTotalStorageBytes] = useState(0);
  const [showVideoModal, setShowVideoModal] = useState(false);
  const [mode, setMode] = useState('general'); // 'general' | 'player'
  const [isProcessing, setIsProcessing] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [activeProject, setActiveProject] = useState(null);
  const [processingStage, setProcessingStage] = useState(null);
  const pollingRef = useRef(null);
  
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [upgradeReason, setUpgradeReason] = useState("");
  
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedPlanForPayment, setSelectedPlanForPayment] = useState(null);

  const handleInitiatePayment = (plan) => {
    if (!user) {
      setView('signup');
      return;
    }
    setSelectedPlanForPayment(plan);
    setShowPaymentModal(true);
  };

  const handlePaystackCheckout = (plan) => {
    if (!user) return;
    const amountNGN = plan === 'Basic' ? 300000 : 750000; // in kobo
    
    if (!window.PaystackPop) {
      alert('Paystack failed to load. Please refresh and try again.');
      return;
    }

    const handler = window.PaystackPop.setup({
      key: 'pk_test_9d49b5a072825c0e164ec1fe8dc4f314db424f99',
      email: user.email,
      amount: amountNGN,
      currency: 'NGN',
      metadata: {
        user_id: user.id,
        plan_tier: plan.toUpperCase()
      },
      callback: function(response){
        alert('Payment successful! Your account is upgrading...');
        setShowPaymentModal(false);
        // In a real app, you might poll the backend here to auto-refresh the UI
      },
      onClose: function(){
        console.log('Payment window closed');
      }
    });
    handler.openIframe();
  };

  const handleLemonSqueezyCheckout = (plan) => {
    if (!user) return;
    const checkoutUrl = plan === 'Basic' 
      ? 'https://tuc-ai.lemonsqueezy.com/checkout/buy/d46f414e-45ca-4836-b02e-a0c7a5a96200'
      : 'https://tuc-ai.lemonsqueezy.com/checkout/buy/6eca916a-bda1-4faf-a085-faa055c41a2e';
      
    // Pass user_id and plan_tier via custom data for the webhook
    window.location.href = `${checkoutUrl}?checkout[custom][user_id]=${user.id}&checkout[custom][plan_tier]=${plan.toUpperCase()}&checkout[email]=${user.email}`;
  };

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (view === 'app') {
      scrollToBottom();
    }
  }, [messages, isProcessing, view]);

  // Restore user session on load and handle initial route
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      const isAuth = !!localStorage.getItem('highlight_user');
      
      // Prevent user from backing out to landing/login if authenticated
      if (isAuth && (path === '/' || path === '/landing' || path === '/login' || path === '/signup')) {
        window.history.pushState(null, '', '/chat');
        setView('app');
        return;
      }

      if (path === '/' || path === '/landing') setView('landing');
      else if (path === '/chat') setView('app');
      else if (path === '/library') setView('app');
      else if (path === '/login') setView('login');
      else if (path === '/signup') setView('signup');
      else if (path === '/pricing') setView('pricing');
    };
    window.addEventListener('popstate', handlePopState);

    // Parse OAuth hash fragment from Supabase redirect
    const hash = window.location.hash;
    if (hash && hash.includes('access_token=')) {
      const params = new URLSearchParams(hash.replace('#', '?'));
      const accessToken = params.get('access_token');
      if (accessToken) {
        const fetchOAuthUser = async () => {
          try {
            const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/auth/me`, {
              headers: { Authorization: `Bearer ${accessToken}` }
            });
            if (res.data.status === 'success') {
              const userData = res.data.user;
              const sessionData = {
                email: userData.email,
                name: userData.user_metadata?.name || userData.email.split('@')[0],
                token: accessToken,
                plan_tier: userData.plan_tier || 'FREE'
              };
              setUser(sessionData);
              localStorage.setItem('highlight_user', JSON.stringify(sessionData));
              loadSessions(sessionData.token);
              setView('app');
              // Clear hash
              window.history.replaceState(null, '', window.location.origin + window.location.pathname);
            }
          } catch (err) {
            console.error('Failed to verify OAuth login:', err);
            alert('Failed to complete Google Sign-In. Please try again.');
          }
        };
        fetchOAuthUser();
        return;
      }
    }

    const path = window.location.pathname;
    const savedUser = localStorage.getItem('highlight_user');
    
    if (savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        if (parsed && parsed.token) {
          setUser(parsed);
          loadSessions(parsed.token, true);
          // If authenticated and on root or chat, go to app/library
          if (path === '/' || path === '/library') {
            setView('app');
          } else if (path === '/chat') {
            setView('app');
          } else {
            setView(path.substring(1) || 'app'); // fallback
          }
          return;
        }
      } catch (e) {
        console.error("Failed to load session:", e);
      }
    }
    
    // Not authenticated or no valid session
    if (path === '/login') setView('login');
    else if (path === '/signup') setView('signup');
    else setView('landing');
    
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Sync URL when view changes
  useEffect(() => {
    if (view === 'landing') {
      window.history.pushState(null, '', '/');
    } else if (view === 'login') {
      window.history.pushState(null, '', '/login');
    } else if (view === 'signup') {
      window.history.pushState(null, '', '/signup');
    } else if (view === 'app') {
      window.history.pushState(null, '', '/chat');
    } else if (view === 'library') {
      window.history.pushState(null, '', '/chat');
    }
  }, [view]);

  const handleFileChange = (e) => {
    if (e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleDirectUpload = async (uploadFile) => {
    if (!user || !user.token) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setUploadSpeed(0);
    setTimeRemaining(0);
    setUploadError('');
    uploadStatsRef.current = { startTime: Date.now(), lastLoaded: 0, lastTime: Date.now() };

    const handleProgress = (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
      setUploadProgress(percentCompleted);
      
      const now = Date.now();
      const timeElapsed = (now - uploadStatsRef.current.lastTime) / 1000;
      
      if (timeElapsed > 0.5) {
        const bytesLoadedSinceLast = progressEvent.loaded - uploadStatsRef.current.lastLoaded;
        const speedBps = bytesLoadedSinceLast / timeElapsed;
        const speedMbps = (speedBps / (1024 * 1024)).toFixed(2);
        
        const bytesRemaining = progressEvent.total - progressEvent.loaded;
        const timeRemainingSecs = speedBps > 0 ? Math.round(bytesRemaining / speedBps) : 0;
        
        setUploadSpeed(speedMbps);
        setTimeRemaining(timeRemainingSecs);
        
        uploadStatsRef.current.lastLoaded = progressEvent.loaded;
        uploadStatsRef.current.lastTime = now;
      }
    };

    try {
      // 1. Get Pre-signed URL
      const urlRes = await axios.post(`https://tuc-backend-530507298858.us-central1.run.app/api/videos/upload-url`, {
        filename: uploadFile.name,
        contentType: uploadFile.type || 'video/mp4'
      }, {
        headers: { Authorization: `Bearer ${user.token}` }
      });

      const { uploadUrl, blobName, provider } = urlRes.data;

      // 2. Upload directly to Cloud Storage (or Local if mock)
      if (provider === 'gcp') {
        await axios.put(uploadUrl, uploadFile, {
          headers: {
            'Content-Type': uploadFile.type || 'video/mp4'
          },
          onUploadProgress: handleProgress
        });
      } else {
        // Fallback for local testing if GCP isn't setup
        const formData = new FormData();
        formData.append('file', uploadFile);
        await axios.post(uploadUrl, formData, {
          headers: { Authorization: `Bearer ${user.token}` },
          onUploadProgress: handleProgress
        });
      }

      // 3. Finalize
      await axios.post(`https://tuc-backend-530507298858.us-central1.run.app/api/videos/finalize`, { blobName }, {
        headers: { Authorization: `Bearer ${user.token}` }
      });

      // 4. Trigger Chat
      setIsUploading(false);
      setFile(uploadFile); // For UI reference
      setView('app');
      createNewSession();

    } catch (err) {
      console.error("Upload failed", err);
      if (!err.response) {
        setUploadError("Network connection lost. Please try uploading again.");
      } else {
        setUploadError(err.response?.data?.detail || "Upload failed. Please try again.");
      }
      setIsUploading(false);
    }
  };

  const fetchLocalVideos = async () => {
    try {
      const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/api/videos`, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      setLocalVideos(res.data.videos || []);
      if (res.data.total_storage_bytes !== undefined) {
        setTotalStorageBytes(res.data.total_storage_bytes);
      }
    } catch (e) {
      console.error('Failed to load local videos:', e);
      if (e.response && e.response.status === 401) {
        handleLogout();
      }
    }
  };

  useEffect(() => {
    if (user && user.token) {
      fetchLocalVideos();
    }
  }, [user]);

  const handleGoogleLogin = () => {
    const supabaseUrl = "https://tvrzglufdryylmcywoth.supabase.co";
    const redirectUrl = window.location.origin;
    window.location.href = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${redirectUrl}`;
  };

  // Production authentication logic connecting to backend
  const handleAuthSubmit = async (e, type) => {
    e.preventDefault();
    if (!authEmail || !authPassword || (type === 'signup' && !authName)) {
      alert('Please fill out all fields.');
      return;
    }
    
    try {
      const endpoint = type === 'signup' ? 'signup' : 'login';
      const payload = {
        email: authEmail,
        password: authPassword
      };
      if (type === 'signup') {
        payload.name = authName;
      }
      
      const response = await axios.post(`https://tuc-backend-530507298858.us-central1.run.app/auth/${endpoint}`, payload);
      
      if (response.data.status === 'success') {
        const userData = response.data.user;
        const sessionData = {
          email: userData.email,
          name: userData.user_metadata?.name || userData.email.split('@')[0],
          token: response.data.access_token,
          plan_tier: userData.plan_tier || 'FREE'
        };
        
        setUser(sessionData);
        localStorage.setItem('highlight_user', JSON.stringify(sessionData));
        loadSessions(sessionData.token);
        setView('app');
      } else if (response.data.status === 'verification_required') {
        alert(response.data.message || 'Signup successful! Please check your email inbox to verify your account before logging in.');
        setView('login');
      } else {
        alert(response.data.message || 'Authentication failed.');
      }
    } catch (error) {
      console.error(error);
      alert(error.response?.data?.detail || error.message || 'Authentication error.');
    }
  };

  function handleLogout() {
    setUser(null);
    localStorage.removeItem('highlight_user');
    setView('login'); // The user asked to be taken to the login page on expiry
    setSessionsList([]);
    createNewSession();
  }

  const startPolling = (projectId) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    
    pollingRef.current = setInterval(async () => {
      try {
        if (!pollingRef.current) return;
        const headers = {};
        if (user && user.token) {
          headers['Authorization'] = `Bearer ${user.token}`;
        }
        const res = await axios.get(`https://tuc-backend-530507298858.us-central1.run.app/projects/${projectId}/status`, { headers });
        if (!pollingRef.current) return; // Prevent race condition if cleared during network request
        
        const project = res.data;
        setActiveProject(project);
        setProcessingStage(project.status);
        
        if (project.status === 'complete') {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setIsProcessing(false);
          
          // Add the completed message with video
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'bot',
            text: 'Your highlight reel is ready!',
            videoUrl: project.video_url,
            status: 'success',
            timeline: project.timeline_state
          }]);
          setProcessingStage(null);
        } else if (project.status === 'conversational_pushback') {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setIsProcessing(false);
          
          let pushbackText = project.last_error_log || "I need some clarification.";
          let candidates = [];
          try {
              if (project.last_error_log && project.last_error_log.startsWith('{')) {
                  const errData = JSON.parse(project.last_error_log);
                  pushbackText = errData.message;
                  candidates = errData.candidates.map(c => ({ id: c, label: c }));
              }
          } catch (e) { console.error("Failed to parse pushback json", e); }
          
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'bot',
            text: pushbackText,
            candidates: candidates.length > 0 ? candidates : undefined,
            isNew: true
          }]);
          setProcessingStage(null);
        } else if (project.status === 'error') {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setIsProcessing(false);
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'bot',
            text: `Processing failed: ${project.last_error_log || 'Unknown error'}`,
            status: 'error'
          }]);
          setProcessingStage(null);
        }
      } catch (err) {
        console.error('Polling error:', err);
        if (err.response && err.response.status === 404) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setIsProcessing(false);
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'bot',
            text: "Failed to connect to the database. The background task crashed before it could start.",
            status: 'error'
          }]);
          setProcessingStage(null);
        }
      }
    }, 2000);
  };
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // Main chat API call (Existing Logic)
  const sendMessage = async (promptText, attachedFileName) => {
    if (!promptText.trim() && !attachedFileName) return;

    const userMsg = {
      id: Date.now(),
      role: 'user',
      text: promptText,
      file: attachedFileName
    };

    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    const formData = new FormData();
    formData.append('prompt', promptText);
    formData.append('mode', mode);
    if (attachedFileName) {
      formData.append('filename', attachedFileName);
    }
    if (activeSessionId) {
      formData.append('session_id', activeSessionId);
    }

    try {
      const headers = { 'Content-Type': 'multipart/form-data' };
      if (user && user.token) {
        headers['Authorization'] = `Bearer ${user.token}`;
      }
      
      const response = await axios.post(`https://tuc-backend-530507298858.us-central1.run.app/chat`, formData, {
        headers: headers
      });
      
      const data = response.data;

      if (data.status === 'out_of_credits') {
        setIsTyping(false);
        setUpgradeReason(data.reason);
        setShowUpgradeModal(true);
        // We still add the bot message to chat history for context
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: 'bot',
          text: data.message,
          status: 'error'
        }]);
        return;
      }

      if (data.status === 'processing' && data.project_id) {
        setIsTyping(false);
        setIsProcessing(true);
        // Async pipeline — start polling
        // We DO NOT push the 'processing' message to the frontend array anymore
        // because we want the cinematic UI to take over entirely without a chat bubble.
        if (data.session_id && !activeSessionId) {
          setActiveSessionId(data.session_id);
          if (user?.token) loadSessions(user.token);
        }
        setProcessingStage('queued');
        startPolling(data.project_id);
        // Don't set isProcessing to false — polling will do it
        return;
      } else {
        const botResponse = {
          id: Date.now() + 1,
          role: 'bot',
          text: data.message || 'I processed your request.',
          videoUrl: data.videoUrl,
          status: data.status,
          candidates: data.candidates || null,
          timeline: data.timeline || [],
          isNew: true
        };
        setMessages(prev => [...prev, botResponse]);
        setIsTyping(false);
        if (data.session_id && !activeSessionId) {
            setActiveSessionId(data.session_id);
            if (user?.token) loadSessions(user.token);
        }
      }
    } catch (error) {
      console.error(error);
      setIsTyping(false);
      
      if (error.response && error.response.status === 401) {
        handleLogout();
        return;
      }
      
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        text: `Error processing request: ${error.response?.data?.message || error.message}`
      }]);
    } finally {
      setIsTyping(false);
      if (!pollingRef.current) {
        setIsProcessing(false);
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(inputValue, file ? file.name : null);
    setInputValue('');
    setFile(null);
  };

  const handleCandidateSelect = (candidate) => {
    let lastFile = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user' && messages[i].file) {
        lastFile = messages[i].file;
        break;
      }
    }
    const prompt = `id:${candidate.id}`;
    sendMessage(prompt, lastFile);
  };



  const ProcessingMonitor = ({ stage, project }) => {
    const stageConfig = {
      queued: { label: 'Getting Match Details', detail: 'Searching database and extracting instructions...' },
      scanning: { label: 'Scanning Match', detail: project?.stage_message || 'Scanning match database...' },
      analyzing: { label: 'Analyzing', detail: project?.stage_message || `Identified ${project?.total_moments || '...'} target moments` },
      calibrating: { label: 'Syncing Timeline', detail: project?.stage_message || 'Calibrating video clock offset...' },
      calibrated: { label: 'Timeline Synced', detail: project?.stage_message || 'Offset locked. Beginning extraction...' },
      cutting: { label: 'Extracting Moments', detail: project?.stage_message || `Processing moment ${(project?.current_moment_index || 0) + 1}...` },
      rendering: { label: 'Rendering', detail: project?.stage_message || 'Stitching final highlight reel...' },
    };

    const config = stageConfig[stage] || stageConfig.queued;
    const progress = stage === 'cutting' && project?.total_moments 
      ? Math.round(((project?.current_moment_index || 0) / project.total_moments) * 100) 
      : null;

    return (
      <motion.div 
        className="processing-monitor"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="monitor-header">
          <div className="monitor-dot live" />
          <span className="monitor-label">LIVE PROCESSING</span>
        </div>
        
        <div className="monitor-body">
          <AnimatePresence mode="wait">
            <motion.div 
              key={stage}
              className={`stage-visual stage-${stage}`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              {stage === 'queued' && (
                <div className="radar-container" style={{ borderColor: 'var(--accent)' }}>
                  <div className="radar-sweep" style={{ animationDuration: '3s' }} />
                  <div className="render-icon" style={{ fontSize: '24px' }}>&#128269;</div>
                </div>
              )}
              
              {stage === 'scanning' && (
                <div className="radar-container">
                  <div className="radar-sweep" />
                  <div className="radar-grid">
                    {[...Array(12)].map((_, i) => <div key={i} className="radar-dot" style={{ animationDelay: `${i * 0.15}s` }} />)}
                  </div>
                </div>
              )}
              
              {stage === 'calibrating' && (
                <div className="wave-container">
                  {[...Array(20)].map((_, i) => (
                    <div key={i} className="wave-bar" style={{ animationDelay: `${i * 0.05}s` }} />
                  ))}
                </div>
              )}
              
              {(stage === 'cutting' || stage === 'analyzing' || stage === 'calibrated') && (
                <div className="film-strip-container">
                  <div className="film-strip">
                    {[...Array(8)].map((_, i) => (
                      <div key={i} className={`film-frame ${i <= (project?.current_moment_index || 0) ? 'processed' : ''}`} 
                           style={{ animationDelay: `${i * 0.1}s` }}>
                        <div className="frame-inner" />
                      </div>
                    ))}
                  </div>
                  {stage === 'cutting' && <div className="scissors-icon">&#9986;</div>}
                </div>
              )}
              
              {stage === 'rendering' && (
                <div className="render-ring-container">
                  <svg className="render-ring" viewBox="0 0 100 100">
                    <circle className="render-ring-bg" cx="50" cy="50" r="42" />
                    <circle className="render-ring-progress" cx="50" cy="50" r="42" />
                  </svg>
                  <div className="render-icon">&#9881;</div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
          
          <div className="stage-info">
            <h4 className="stage-label">{config.label}</h4>
            <p className="stage-detail">{config.detail}</p>
            {progress !== null && (
              <div className="progress-bar-container">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                <span className="progress-text">{progress}%</span>
              </div>
            )}
          </div>
        </div>
        
        <div className="monitor-stages">
          {['scanning', 'analyzing', 'calibrating', 'cutting', 'rendering'].map((s, i) => (
            <div key={s} className={`stage-pip ${stage === s ? 'active' : ''} ${['scanning','analyzing','calibrating','cutting','rendering'].indexOf(stage) > i ? 'done' : ''}`}>
              <div className="pip-dot" />
              <span className="pip-label">{s === 'scanning' ? 'Scan' : s === 'analyzing' ? 'Analyze' : s === 'calibrating' ? 'Sync' : s === 'cutting' ? 'Extract' : 'Render'}</span>
            </div>
          ))}
        </div>
      </motion.div>
    );
  };

  // ─────────────────────────────────────────────────────────────
  // RENDER PURE LANDING PAGE
  // ─────────────────────────────────────────────────────────────
  if (view === 'landing') {
    return (
      <div className="landing-layout">
        {/* Curved backdrop panel */}
        <div className="hero-curve-bg"></div>

        <header className="nav-header">
          <div className="logo-container" onClick={() => setView('landing')}>
            <div className="logo-icon-wrap">T</div>
            <span>Tuc AI</span>
          </div>
          <nav className="nav-links">
            <a href="#features" className="nav-link">Features</a>
            <a href="#pipelines" className="nav-link">Pipelines</a>
            <a href="#about" className="nav-link">Aesthetics</a>
            <span className="nav-link" onClick={() => setView('pricing')} style={{cursor: 'pointer'}}>Pricing</span>
          </nav>
          <div className="nav-actions">
            {user ? (
              <button className="btn btn-primary" onClick={() => setView('app')}>Go to Studio</button>
            ) : (
              <>
                <button className="btn btn-ghost" onClick={() => setView('login')}>Login</button>
                <button className="btn btn-primary" onClick={() => setView('pricing')}>Sign Up</button>
              </>
            )}
          </div>
        </header>

        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-content">
            <div className="hero-badge">
              <Sparkles size={14} />
              <span>Next-Gen Vision AI Highlight Editor</span>
            </div>
            <h1 className="hero-title">
              Welcome to <br />Tuc AI.
            </h1>
            <p className="hero-description">
              Upload raw match recordings and let vision intelligence trace clocks, scores, goals, and player touches. Cut hours of editing work into seconds with synchronized frame grids.
            </p>

            <div style={{ marginTop: '1.5rem', marginBottom: '2.5rem' }}>
              <button 
                className="btn btn-primary" 
                style={{ padding: '1rem 2.5rem', fontSize: '1.1rem', borderRadius: '30px', display: 'inline-flex', alignItems: 'center' }} 
                onClick={() => setView('pricing')}
              >
                Start Editing <ArrowRight size={18} style={{ marginLeft: '8px' }} />
              </button>
            </div>

            {/* Prompt bar mimicking image layout (static showcase) */}
            <div className="hero-prompt-bar">
              <input 
                type="text" 
                placeholder="Enter a match prompt... (e.g., Jonathan David vs Qatar)" 
                disabled
              />
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                background: 'var(--accent-primary)',
                color: 'var(--bg-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginRight: '4px'
              }}>
                <ArrowRight size={20} />
              </div>
            </div>

            {/* Social Nodes Row mimicking reference image footer */}
            <div className="hero-socials-row">
              <div className="social-circle-group">
                <a href="https://github.com" target="_blank" rel="noreferrer" className="social-circle"><GithubIcon style={{ width: 16, height: 16 }} /></a>
                <a href="https://twitter.com" target="_blank" rel="noreferrer" className="social-circle"><TwitterIcon style={{ width: 16, height: 16 }} /></a>
                <a href="https://linkedin.com" target="_blank" rel="noreferrer" className="social-circle"><LinkedinIcon style={{ width: 16, height: 16 }} /></a>
                <a href="https://youtube.com" target="_blank" rel="noreferrer" className="social-circle"><YoutubeIcon style={{ width: 16, height: 16 }} /></a>
              </div>
              <div className="social-line-connector"></div>
              <div className="social-subtitle">socials</div>
            </div>
          </div>

          {/* Right column editor preview mockup */}
          <div className="hero-visual">
            <div className="editor-preview-card">
              <div className="preview-header">
                <div className="preview-dots">
                  <div className="preview-dot"></div>
                  <div className="preview-dot"></div>
                  <div className="preview-dot"></div>
                </div>
                <div className="preview-badge">vision_ai</div>
              </div>
              <div className="preview-video-box">
                <div className="preview-video-mesh"></div>
                <div className="preview-ai-box">
                  <div className="preview-ai-label">Active Climax Hunt</div>
                </div>
              </div>
              <div className="preview-timeline">
                <div className="preview-waveform">
                  {[10, 15, 25, 45, 12, 18, 32, 60, 80, 95, 30, 24, 62, 70, 44, 28, 12, 8, 30, 48, 55, 15, 10].map((h, i) => (
                    <div 
                      key={i} 
                      className={`wave-bar ${i >= 8 && i <= 14 ? 'highlighted' : ''}`}
                      style={{ height: `${h}%` }}
                    ></div>
                  ))}
                </div>
                <div className="preview-clips">
                  <div className="preview-clip">0:00 - 0:28</div>
                  <div className="preview-clip active">Goal Climax</div>
                  <div className="preview-clip">0:43 - 1:12</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="features-section">
          <div className="section-header">
            <div className="section-subtitle">Core Features</div>
            <h2 className="section-title">Automating the Edit</h2>
            <p className="section-desc">We build tools that completely bypass manual scrubbing. Spend less time in timeline files and more time publishing content.</p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon"><Video size={24} /></div>
              <h3 className="feature-title">Match Highlights</h3>
              <p className="feature-text">AI scans the match, monitors big chances and goals.</p>
              <div className="feature-pill-list">
                <span className="feature-pill">AI Detection</span>
                <span className="feature-pill">Goal Climax</span>
                <span className="feature-pill">Saves & Shots</span>
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-icon"><Sliders size={24} /></div>
              <h3 className="feature-title">Player Highlights</h3>
              <p className="feature-text">With your jersey number and our match tracking data, we find big moments of your select players in matches.</p>
              <div className="feature-pill-list">
                <span className="feature-pill">Jersey Detection</span>
                <span className="feature-pill">Match Tracking</span>
                <span className="feature-pill">Touch Isolation</span>
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-icon"><Zap size={24} /></div>
              <h3 className="feature-title">Dynamic Re-Rendering</h3>
              <p className="feature-text">Instantly cut clips, modify durations, and rebuild timelines in seconds without re-running any heavy AI models.</p>
              <div className="feature-pill-list">
                <span className="feature-pill">Fast Cut Engine</span>
                <span className="feature-pill">Timeline Editing</span>
                <span className="feature-pill">Instant Assembly</span>
              </div>
            </div>
          </div>
        </section>

        {/* Pipelines Section */}
        <section id="pipelines" className="features-section" style={{ borderTop: 'none', background: 'var(--bg-primary)' }}>
          <div className="section-header">
            <div className="section-subtitle">Pipelines</div>
            <h2 className="section-title">Targeted Flows</h2>
            <p className="section-desc">Choose between two custom automated paths depending on your editing goals.</p>
          </div>

          <div className="features-grid">
            <div className="feature-card" style={{ background: 'var(--bg-secondary)' }}>
              <div className="feature-icon" style={{ background: 'var(--bg-primary)' }}><Sparkles size={24} /></div>
              <h3 className="feature-title">General Highlights Flow</h3>
              <p className="feature-text">Tracks the general narrative flow of the match. Collects goals, big chances, red cards, and major game-changing details to assemble a comprehensive match recap.</p>
            </div>

            <div className="feature-card" style={{ background: 'var(--bg-secondary)' }}>
              <div className="feature-icon" style={{ background: 'var(--bg-primary)' }}><User size={24} /></div>
              <h3 className="feature-title">Player Focus Flow</h3>
              <p className="feature-text">Zeroes in on a single player. Feeds their specific jersey number and matches their timeline coordinates to isolate every pass, dribble, and major touch they made.</p>
            </div>
          </div>
        </section>

        {/* Aesthetics Section */}
        <section id="about" className="features-section">
          <div className="section-header">
            <div className="section-subtitle">Aesthetics</div>
            <h2 className="section-title">Designed for Editors</h2>
            <p className="section-desc">A premium, high-contrast dark space built to reduce eye strain and provide a tactile, responsive workspace.</p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon"><Play size={24} /></div>
              <h3 className="feature-title">Monochrome Elegance</h3>
              <p className="feature-text">A professional slate-black color system featuring high-contrast white text, subtle glowing shadows, and clear visual hierarchies.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon"><Sliders size={24} /></div>
              <h3 className="feature-title">Tactile Audio Waveforms</h3>
              <p className="feature-text">Visual representation of timeline intensity waves that lets you align and inspect highlight clips and climax cuts with precision.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon"><Zap size={24} /></div>
              <h3 className="feature-title">Fluid Animations</h3>
              <p className="feature-text">Micro-interactions and smooth page transitions powered by Framer Motion that respond directly to your timeline edits and chat actions.</p>
            </div>
          </div>
        </section>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER PRICING VIEW
  // ─────────────────────────────────────────────────────────────
  if (view === 'pricing') {
    return (
      <div className="pricing-layout">


        <button 
          className="btn btn-outline auth-back-btn" 
          onClick={() => setView('landing')}
          style={{ position: 'absolute', top: '2rem', left: '2rem', zIndex: 10 }}
        >
          <ArrowLeft size={16} style={{ marginRight: '8px' }} />
          Back to Home
        </button>

        <div className="pricing-container">
          <div className="pricing-header">
            <h1 className="hero-title" style={{ fontSize: '3rem', marginBottom: '16px' }}>Simple, transparent pricing.</h1>
            <p className="hero-description" style={{ marginBottom: '32px' }}>Choose the plan that fits your editing workflow.</p>
            
            <div className="billing-toggle">
              <span className={!isYearly ? 'active' : ''}>Monthly</span>
              <label className="switch">
                <input type="checkbox" checked={isYearly} onChange={() => setIsYearly(!isYearly)} />
                <span className="slider round"></span>
              </label>
              <span className={isYearly ? 'active' : ''}>Yearly <span className="discount-badge">Save 20%</span></span>
            </div>
          </div>

          <div className="pricing-cards">
            {/* Free Trial */}
            <div className="pricing-card">
              <div className="card-header">
                <h3>7-Day Free Trial</h3>
                <div className="price">$0</div>
                <p>7-day limit</p>
              </div>
              <ul className="feature-list">
                <li><Check size={16} /> 1 Video Generation Limit</li>
                <li><Check size={16} /> Match Highlights</li>
                <li><Check size={16} /> Player Highlights</li>
                <li><Check size={16} /> Standard Processing</li>
                <li><Check size={16} /> 2GB Storage</li>
                <li><Check size={16} /> 7-day video retention</li>
                <li><Check size={16} /> Account expires after 7 days</li>
              </ul>
              <button 
                className="btn btn-outline" 
                onClick={() => setView('signup')} 
                style={{ width: '100%', marginTop: 'auto' }}
                disabled={!!user}
              >
                {user ? 'Current Plan' : 'Start Free Trial'}
              </button>
            </div>

            {/* Basic Plan */}
            <div className="pricing-card popular">
              <div className="popular-badge">Most Popular</div>
              <div className="card-header">
                <h3>Basic</h3>
                <div className="price">${isYearly ? '30' : '3'}<span>/{isYearly ? 'yr' : 'mo'}</span></div>
                <p>For casual fans</p>
              </div>
              <ul className="feature-list">
                <li><Check size={16} /> Unlimited Match Highlights</li>
                <li><Check size={16} /> 2 Player Highlights / day</li>
                <li><Check size={16} /> 720p Export Quality</li>
                <li><Check size={16} /> Standard Processing</li>
                <li><Check size={16} /> 25GB Storage</li>
                <li><Check size={16} /> 30-day video retention</li>
              </ul>
              <button className="btn btn-primary" onClick={() => handleInitiatePayment('Basic')} style={{ width: '100%', marginTop: 'auto' }}>
                Get Basic
              </button>
            </div>

            {/* Pro Plan */}
            <div className="pricing-card">
              <div className="card-header">
                <h3>Pro</h3>
                <div className="price">${isYearly ? '75' : '7.50'}<span>/{isYearly ? 'yr' : 'mo'}</span></div>
                <p>For content creators</p>
              </div>
              <ul className="feature-list">
                <li><Check size={16} /> Unlimited Match Highlights</li>
                <li><Check size={16} /> Unlimited Player Highlights</li>
                <li><Check size={16} /> 1080p Export Quality</li>
                <li><Check size={16} /> Priority Processing</li>
                <li><Check size={16} /> 100GB Storage</li>
                <li><Check size={16} /> Unlimited video retention</li>
              </ul>
              <button className="btn btn-primary" onClick={() => handleInitiatePayment('Pro')} style={{ width: '100%', marginTop: 'auto' }}>
                Get Pro
              </button>
            </div>
          </div>
        </div>

        {/* Payment Method Modal */}
        {showPaymentModal && (
          <div className="modal-overlay" onClick={() => setShowPaymentModal(false)}>
            <div className="modal-content payment-modal" onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-secondary)', padding: '2rem', borderRadius: '16px', maxWidth: '400px', width: '90%', textAlign: 'center' }}>
              <h2 style={{ marginBottom: '8px' }}>Select Payment Method</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Choose how you'd like to pay for the {selectedPlanForPayment} Plan</p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <button 
                  className="btn btn-primary" 
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', fontSize: '1.1rem' }}
                  onClick={() => handlePaystackCheckout(selectedPlanForPayment)}
                >
                  Pay with Paystack (NGN)
                </button>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Includes Cards, Bank Transfer, USSD</div>
                
                <div style={{ height: '1px', background: 'var(--border-color)', margin: '8px 0' }}></div>
                
                <button 
                  className="btn btn-outline" 
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', fontSize: '1.1rem' }}
                  onClick={() => handleLemonSqueezyCheckout(selectedPlanForPayment)}
                >
                  Pay with Lemon Squeezy (USD)
                </button>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Includes Global Cards, Apple Pay, PayPal</div>
              </div>
              
              <button 
                className="btn btn-outline" 
                onClick={() => setShowPaymentModal(false)} 
                style={{ marginTop: '24px', width: '100%' }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER AUTHENTICATION VIEW (Login / Sign Up)
  // ─────────────────────────────────────────────────────────────
  if (view === 'login' || view === 'signup') {
    return (
      <div className="auth-layout">
        <button className="btn btn-outline auth-back-btn" onClick={() => setView('landing')}>
          <ArrowLeft size={16} style={{ marginRight: '8px' }} />
          Back to Home
        </button>

        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo-icon">T</div>
            <h2 className="auth-title">{view === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
            <p className="auth-subtitle">
              {view === 'login' ? 'Sign in to access your video editor' : 'Sign up to start editing sports footage'}
            </p>
          </div>

          <form onSubmit={(e) => handleAuthSubmit(e, view)} className="auth-form">
            {view === 'signup' && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <div className="input-wrapper">
                  <User className="input-icon" size={18} />
                  <input 
                    type="text" 
                    placeholder="Enter your name" 
                    className="form-input" 
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email Address</label>
              <div className="input-wrapper">
                <Mail className="input-icon" size={18} />
                <input 
                  type="email" 
                  placeholder="name@example.com" 
                  className="form-input" 
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <div className="input-wrapper">
                <Lock className="input-icon" size={18} />
                <input 
                  type="password" 
                  placeholder="Enter password" 
                  className="form-input" 
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary auth-submit-btn">
              {view === 'login' ? 'Sign In' : 'Register'}
            </button>
          </form>

          <div className="auth-separator">OR</div>

          <button type="button" className="google-btn" onClick={handleGoogleLogin}>
            <svg className="google-icon" viewBox="0 0 24 24" width="18" height="18" style={{ marginRight: '10px' }}>
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <div className="auth-toggle">
            {view === 'login' ? (
              <>
                Don't have an account? 
                <span className="auth-toggle-link" onClick={() => setView('signup')}>Sign Up</span>
              </>
            ) : (
              <>
                Already have an account? 
                <span className="auth-toggle-link" onClick={() => setView('login')}>Log In</span>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER VIDEO LIBRARY VIEW
  // ─────────────────────────────────────────────────────────────
  if (view === 'library') {
    return (
      <div className="library-layout" style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex' }}>
        <aside className="sidebar open" style={{ borderRight: '1px solid var(--border-color)' }}>
          <div className="sidebar-header" style={{ padding: '20px', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center' }}>
            <div className="logo-icon-wrap" style={{ background: '#fff', color: '#000', marginRight: '12px' }}>T</div>
            <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Tuc AI</h2>
          </div>
          <div className="sidebar-sessions" style={{ padding: '20px 12px' }}>
            <div className="session-item active" style={{ cursor: 'pointer', marginBottom: '8px' }}>
              <FileVideo size={18} />
              <span className="session-title">My Videos</span>
            </div>
            <div className="session-item" style={{ cursor: 'pointer' }} onClick={() => setView('pricing')}>
              <CreditCard size={18} />
              <span className="session-title">Billing</span>
            </div>
          </div>
          <div className="sidebar-footer">
            <div className="user-profile">
              <div className="user-avatar">{user?.name?.charAt(0).toUpperCase() || 'U'}</div>
              <div className="user-info">
                <span className="user-name">{user?.name}</span>
                <span className="user-email">{user?.email}</span>
              </div>
              <button className="btn-logout" onClick={handleLogout} title="Log Out">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </aside>

        <main className="library-main" style={{ flex: 1, padding: '3rem', overflowY: 'auto' }}>
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
            <div>
              <h1 style={{ fontSize: '2.5rem', margin: '0 0 8px 0' }}>Workspace</h1>
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Upload raw matches or continue editing past highlights.</p>
            </div>
            <button 
              className="btn btn-primary" 
              onClick={() => { createNewSession(); setView('app'); }} 
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 24px', fontSize: '1.1rem', borderRadius: '30px' }}
            >
              <MessageSquare size={20} /> New Edit Session
            </button>
            <input type="file" id="video-upload" style={{ display: 'none' }} accept="video/*" onChange={(e) => {
              if(e.target.files.length > 0) {
                 handleDirectUpload(e.target.files[0]);
              }
            }} />
          </header>

          {isUploading && (
            <div style={{ background: 'var(--bg-secondary)', padding: '1rem 2rem', borderRadius: '12px', marginBottom: '2rem', border: '1px solid var(--accent)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>Uploading to Cloud Workspace...</span>
                <span style={{ color: 'var(--text-secondary)' }}>{uploadProgress}% ({uploadSpeed} MB/s) - {timeRemaining}s remaining</span>
              </div>
              <div style={{ height: '8px', background: 'var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${uploadProgress}%`, background: 'var(--accent)', transition: 'width 0.3s ease' }}></div>
              </div>
            </div>
          )}
          
          {uploadError && (
             <div style={{ color: 'var(--error)', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', marginBottom: '2rem' }}>
                {uploadError}
             </div>
          )}

          <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-color)', marginBottom: '2rem' }}>
            <button 
              style={{ padding: '0.5rem 1rem', background: 'none', border: 'none', color: libraryTab === 'uploads' ? 'var(--text-primary)' : 'var(--text-secondary)', borderBottom: libraryTab === 'uploads' ? '2px solid var(--accent)' : '2px solid transparent', cursor: 'pointer', fontSize: '1.1rem', fontWeight: libraryTab === 'uploads' ? 'bold' : 'normal' }}
              onClick={() => setLibraryTab('uploads')}
            >
              My Uploads
            </button>
            <button 
              style={{ padding: '0.5rem 1rem', background: 'none', border: 'none', color: libraryTab === 'edits' ? 'var(--text-primary)' : 'var(--text-secondary)', borderBottom: libraryTab === 'edits' ? '2px solid var(--accent)' : '2px solid transparent', cursor: 'pointer', fontSize: '1.1rem', fontWeight: libraryTab === 'edits' ? 'bold' : 'normal' }}
              onClick={() => setLibraryTab('edits')}
            >
              Past Edits
            </button>
          </div>

          <div className="video-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '2rem' }}>
            {libraryTab === 'uploads' && (
              <>
                <div className="video-card empty-upload" onClick={() => document.getElementById('video-upload').click()} style={{ border: '2px dashed var(--border-color)', borderRadius: '16px', height: '240px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--text-secondary)', transition: 'all 0.2s ease', background: 'var(--bg-secondary)' }} onMouseOver={e => e.currentTarget.style.borderColor = 'var(--accent)'} onMouseOut={e => e.currentTarget.style.borderColor = 'var(--border-color)'}>
                  <Upload size={40} style={{ marginBottom: '16px', color: 'var(--text-primary)' }} />
                  <h3 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>Upload New Video</h3>
                  <p style={{ fontSize: '0.9rem', margin: 0 }}>Drag & drop or click to browse</p>
                </div>

                {uploadedVideos.map((video, idx) => (
                  <div key={idx} className="video-card" style={{ background: 'var(--bg-secondary)', borderRadius: '16px', overflow: 'hidden', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}>
                    <div className="video-thumbnail" style={{ height: '160px', background: 'linear-gradient(45deg, #1f2937, #111827)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {video.thumbnail_url ? (
                        <img src={video.thumbnail_url} alt="thumbnail" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <Video size={40} color="rgba(255,255,255,0.8)" style={{ filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.5))' }} />
                      )}
                    </div>
                    <div className="video-info" style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column' }}>
                      <h4 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{video.filename || 'Untitled Video'}</h4>
                      <button 
                        className="btn btn-primary"
                        style={{ marginTop: 'auto', width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
                        onClick={() => {
                          setActiveSessionId(null);
                          setMessages([]);
                          setFile({ name: video.filename });
                          setView('app');
                        }}
                      >
                        <Sparkles size={16} /> Edit Video
                      </button>
                    </div>
                  </div>
                ))}
              </>
            )}

            {libraryTab === 'edits' && sessionsList.map(s => (
              <div key={s.id} className="video-card" style={{ background: 'var(--bg-secondary)', borderRadius: '16px', overflow: 'hidden', cursor: 'pointer', border: '1px solid var(--border-color)', transition: 'transform 0.2s ease', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }} onClick={() => { loadSessionDetails(s.id, user?.token); setView('app'); }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-4px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                <div className="video-thumbnail" style={{ height: '160px', background: 'linear-gradient(45deg, #1f2937, #111827)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  <Play size={40} color="rgba(255,255,255,0.8)" style={{ filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.5))' }} />
                  {s.video_path && (
                    <div style={{ position: 'absolute', bottom: '12px', right: '12px', background: 'rgba(0,0,0,0.7)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Video size={12} /> Source Connected
                    </div>
                  )}
                </div>
                <div className="video-info" style={{ padding: '16px' }}>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.title || 'Match Highlight Edit'}</h4>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    <span>{new Date(s.updated_at || Date.now()).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                    <button onClick={(e) => { e.stopPropagation(); deleteSession(s.id, e); }} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }} title="Delete Edit">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </main>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER APP EDITOR WORKSPACE (Full Chat Skinned)
  // ─────────────────────────────────────────────────────────────
  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <button className="btn-new-chat" onClick={() => { createNewSession(); setView('app'); }} style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
            <Plus size={16} /> New Session
          </button>
        </div>
        <div className="sidebar-sessions">
          <h3 className="sessions-label">Past Edits</h3>
          {sessionsList.map(s => (
            <div 
              key={s.id} 
              className={`session-item ${activeSessionId === s.id ? 'active' : ''}`}
              onClick={() => loadSessionDetails(s.id, user?.token)}
            >
              <MessageSquare size={16} />
              <span className="session-title">{s.title || 'New Session'}</span>
              <button className="session-delete" onClick={(e) => deleteSession(s.id, e)}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <div className="user-profile" onClick={() => setShowHubModal(true)} style={{ cursor: 'pointer' }}>
            <div className="user-avatar">{user?.name?.charAt(0).toUpperCase() || 'U'}</div>
            <div className="user-info">
              <span className="user-name" style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                {user?.name}
                <span className={`plan-tag ${user?.plan_tier?.toLowerCase() || 'free'}`}>
                  {user?.plan_tier || 'FREE'}
                </span>
              </span>
              <span className="user-email">{user?.email}</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="chat-container">
        <header className="chat-header">
          <div className="chat-header-left">
            <button className="sidebar-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
              <Menu size={20} />
            </button>
            <div className="logo-icon-wrap" style={{ background: '#fff', color: '#000' }}>T</div>
            <h2>Tuc AI Editor</h2>
          </div>

          <div className="mode-selector">
            <button 
              className={`mode-btn ${mode === 'general' ? 'active' : ''}`}
              onClick={() => setMode('general')}
            >
              Match Highlights
            </button>
            <button 
              className={`mode-btn ${mode === 'player' ? 'active' : ''}`}
              onClick={() => setMode('player')}
            >
              Player Highlights
            </button>
          </div>

          <div className="chat-header-actions">
            {/* Header actions moved to sidebar */}
          </div>
        </header>

        <main className="messages-area">
          {messages.length === 0 && !isProcessing && (
            <div className="empty-state-welcome">
              <h3>Welcome, {user?.name ? user.name.split(' ')[0] : 'Creator'}</h3>
              <p>Ready to edit your videos?</p>
            </div>
          )}
          <AnimatePresence>
            {messages.filter(msg => msg.status !== 'processing' && msg.text && msg.text.trim()).map((msg) => (
              <motion.div 
                key={msg.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`message-wrapper ${msg.role}`}
              >
                <div className="message-bubble">
                  
                  {msg.file && (
                    <div className="attachment-badge">
                      <FileVideo size={16} /> {msg.file} attached
                    </div>
                  )}
                  
                  <div className="message-text">
                    {msg.role === 'bot' && msg.isNew ? <TypewriterText text={msg.text} /> : msg.text}
                  </div>
                  
                  {msg.candidates && (
                    <div className="candidates-list">
                      {msg.candidates.map((cand, idx) => (
                        <button 
                          key={idx} 
                          className="candidate-btn"
                          onClick={() => handleCandidateSelect(cand)}
                        >
                          <List size={14} style={{marginRight: '8px'}} />
                          <strong>{cand.label || cand.name}</strong> {cand.date ? `— ${cand.date}` : ''}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {msg.videoUrl && (
                    <div className="video-player-container">
                      <video 
                        className="video-player" 
                        controls 
                        src={msg.videoUrl.startsWith('http') ? msg.videoUrl : `https://tuc-backend-530507298858.us-central1.run.app${msg.videoUrl}`}
                      />
                      {msg.timeline && msg.timeline.length > 0 && (
                        <div className="timeline-track">
                          {msg.timeline.map((clip, idx) => (
                            <div 
                              key={idx} 
                              className={`timeline-block type-${(clip.type || clip.moment_type || 'moment').toLowerCase().replace(/\s+/g, '-')}`}
                              title={clip.reasoning || clip.details || ''}
                              onClick={() => {
                                const videoEl = document.querySelector('.video-player');
                                if (videoEl) videoEl.currentTime = clip.final_start || 0;
                              }}
                            >
                              <span className="block-time">{clip.minute ? `${clip.minute}'` : `${Math.floor((clip.start || 0) / 60)}:${String(Math.floor((clip.start || 0) % 60)).padStart(2, '0')}`}</span>
                              <span className="block-type">{clip.type || clip.moment_type || 'Moment'}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <div className="message-wrapper bot">
              <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-secondary)' }}>
                <div className="typing-indicator" style={{ display: 'inline-flex' }}>
                  <span></span><span></span><span></span>
                </div>
                <span style={{ fontSize: '0.9rem', fontStyle: 'italic' }}>Analyzing instructions & calculating timeline...</span>
              </div>
            </div>
          )}

          {isProcessing && (
            <div className="message-wrapper bot">
              <ProcessingMonitor stage={processingStage} project={activeProject} />
            </div>
          )}
          <div ref={messagesEndRef} />
        </main>

        <footer className="chat-input-area">
          {file && (
            <div className="file-preview">
              <FileVideo size={16} /> {file.name}
              <button type="button" onClick={() => setFile(null)} style={{background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1.2rem', marginLeft: 'auto'}}>×</button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="input-form">
            <button 
              type="button" 
              className="attachment-btn" 
              style={{cursor: 'pointer', color: 'var(--text-secondary)', background: 'transparent', border: 'none'}}
              onClick={() => { fetchLocalVideos(); setShowVideoModal(true); }}
            >
              <Paperclip size={24} />
            </button>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type your prompt or editing instructions..."
              className="text-input"
              style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '1rem' }}
            />
            <button type="submit" className="send-btn" disabled={!inputValue.trim() && !file}>
              <Send size={20} />
            </button>
          </form>

        </footer>

        {showVideoModal && (
          <div className="modal-overlay" onClick={() => setShowVideoModal(false)}>
            <div className="modal-content" onClick={e => e.stopPropagation()} style={{background: 'var(--bg-secondary)', padding: '2rem', borderRadius: '12px', maxWidth: '500px', width: '90%'}}>
              <h3 style={{color: 'var(--text-primary)', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem'}}>Select a Match Video</h3>
              {localVideos.length === 0 ? (
                <p style={{color: 'var(--text-secondary)'}}>No videos found in the backend uploads folder.</p>
              ) : (
                <div style={{display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto'}}>
                  {localVideos.map((vid, index) => (
                    <button 
                      key={index} 
                      className="btn" 
                      style={{textAlign: 'left', padding: '0.75rem', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)'}}
                      onClick={() => {
                        setFile({ name: vid.name || vid });
                        setShowVideoModal(false);
                      }}
                    >
                      <FileVideo size={16} style={{marginRight: '8px', verticalAlign: 'middle'}} />
                      {vid.name || vid}
                    </button>
                  ))}
                </div>
              )}
              <button 
                className="btn" 
                style={{marginTop: '1rem', width: '100%', background: 'transparent', border: '1px solid var(--border-color)'}}
                onClick={() => setShowVideoModal(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        {showUpgradeModal && (
          <div className="modal-overlay" onClick={() => setShowUpgradeModal(false)}>
            <div className="modal-content" onClick={e => e.stopPropagation()} style={{background: 'var(--bg-secondary)', padding: '2rem', borderRadius: '12px', maxWidth: '400px', width: '90%', textAlign: 'center'}}>
              <div style={{background: 'rgba(239, 68, 68, 0.1)', color: 'var(--error)', width: '48px', height: '48px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem auto'}}>
                <Lock size={24} />
              </div>
              <h3 style={{color: 'var(--text-primary)', marginBottom: '1rem', fontSize: '1.25rem'}}>Upgrade Required</h3>
              <p style={{color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: '1.5'}}>
                {upgradeReason === 'FREE_LIMIT_REACHED' 
                  ? "Your free trial is complete! To continue generating magical highlights, please upgrade your account." 
                  : upgradeReason === 'BASIC_PLAYER_LIMIT_REACHED' 
                  ? "You have reached your daily limit of 2 Player Highlights on the Basic Plan." 
                  : "You have reached your limit for this plan."}
              </p>
              <button 
                className="btn btn-primary" 
                style={{width: '100%', marginBottom: '0.75rem'}}
                onClick={() => {
                  setShowUpgradeModal(false);
                  setView('pricing');
                }}
              >
                View Plans
              </button>
              <button 
                className="btn" 
                style={{width: '100%', background: 'transparent', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)'}}
                onClick={() => setShowUpgradeModal(false)}
              >
                Not Now
              </button>
            </div>
          </div>
        )}

        {showHubModal && (
          <HubModal 
            user={user}
            localVideos={localVideos}
            totalStorageBytes={totalStorageBytes}
            sessions={sessionsList}
            onClose={() => setShowHubModal(false)}
            onSelectVideo={(vid) => {
              setFile({ name: vid });
              setShowHubModal(false);
            }}
            onSelectSession={(sid) => {
              loadSessionDetails(sid, user?.token);
              setShowHubModal(false);
            }}
            onLogout={handleLogout}
            onInitiatePayment={handleInitiatePayment}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
            uploadSpeed={uploadSpeed}
            timeRemaining={timeRemaining}
            uploadError={uploadError}
            onUpload={handleDirectUpload}
          />
        )}
      </div>
    </div>
  );
}

export default App;

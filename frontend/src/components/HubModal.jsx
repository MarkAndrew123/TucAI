import React, { useState } from 'react';
import { Video, FileVideo, Upload, Check, Lock, Zap, LogOut, MessageSquare, Film, Plus, Clock } from 'lucide-react';
import axios from 'axios';

const HubModal = ({ 
  user, 
  localVideos,
  totalStorageBytes,
  sessions, 
  onClose, 
  onSelectVideo, 
  onSelectSession, 
  onLogout,
  onInitiatePayment,
  isUploading,
  uploadProgress,
  uploadSpeed,
  timeRemaining,
  uploadError,
  onUpload
}) => {
  const [tab, setTab] = useState('uploads');
  const [videoErrorMsg, setVideoErrorMsg] = useState(null);
  const [isYearly, setIsYearly] = useState(false);

  // Storage calculation
  const storageBytesUsed = totalStorageBytes || localVideos.reduce((acc, vid) => acc + (vid.size || 0), 0);
  const storageGbUsed = (storageBytesUsed / (1024 ** 3)).toFixed(2);
  const storageLimitGb = user?.plan_tier === 'PRO' ? 100 : user?.plan_tier === 'BASIC' ? 25 : 2;
  const storagePercentage = Math.min((storageGbUsed / storageLimitGb) * 100, 100);

  const handleDirectUploadClick = () => {
    document.getElementById('hub-video-upload')?.click();
  };

  const getCleanFilename = (name) => {
    if (!name) return 'Unknown Video';
    const withoutFolder = name.includes('/') ? name.split('/').slice(1).join('/') : name;
    const cleanName = withoutFolder.replace(/^\d+_(.+)/, '$1');
    return cleanName.replace(/_/g, ' ');
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
      background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(10px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
    }}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-primary)', 
        width: '90%', maxWidth: '1200px', height: '85vh', 
        borderRadius: '16px', overflow: 'hidden', display: 'flex',
        border: '1px solid var(--border-color)',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
      }}>
        
        {/* Sidebar */}
        <div style={{ width: '280px', background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
            <h2 style={{ fontSize: '1.5rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ background: '#fff', color: '#000', padding: '2px 8px', borderRadius: '4px', fontWeight: 'bold' }}>T</div>
              Tuc AI
            </h2>
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.5rem' }}>&times;</button>
          </div>

          <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
            <button onClick={() => setTab('uploads')} style={{ 
              background: tab === 'uploads' ? 'var(--bg-primary)' : 'transparent',
              color: tab === 'uploads' ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: 'none', padding: '12px 16px', borderRadius: '8px', textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer',
              fontWeight: tab === 'uploads' ? 'bold' : 'normal',
              borderLeft: tab === 'uploads' ? '3px solid var(--accent)' : '3px solid transparent'
            }}>
              <Upload size={18} /> My Uploads
            </button>
            <button onClick={() => setTab('edits')} style={{ 
              background: tab === 'edits' ? 'var(--bg-primary)' : 'transparent',
              color: tab === 'edits' ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: 'none', padding: '12px 16px', borderRadius: '8px', textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer',
              fontWeight: tab === 'edits' ? 'bold' : 'normal',
              borderLeft: tab === 'edits' ? '3px solid var(--accent)' : '3px solid transparent'
            }}>
              <Video size={18} /> My Edits
            </button>
            <button onClick={() => setTab('billing')} style={{ 
              background: tab === 'billing' ? 'var(--bg-primary)' : 'transparent',
              color: tab === 'billing' ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: 'none', padding: '12px 16px', borderRadius: '8px', textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer',
              fontWeight: tab === 'billing' ? 'bold' : 'normal',
              borderLeft: tab === 'billing' ? '3px solid var(--accent)' : '3px solid transparent'
            }}>
              <Zap size={18} /> Billing
            </button>
          </nav>

          <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border-color)', paddingTop: '24px' }}>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                <span>Storage Used</span>
                <span>{storageGbUsed} / {storageLimitGb} GB</span>
              </div>
              <div style={{ width: '100%', height: '6px', background: 'var(--bg-primary)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${storagePercentage}%`, height: '100%', background: 'var(--accent)', borderRadius: '3px' }}></div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontWeight: '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{user?.plan_tier || 'FREE'} PLAN</div>
              </div>
            </div>

            <button onClick={onLogout} style={{ 
              width: '100%', display: 'flex', alignItems: 'center', gap: '8px', 
              background: 'transparent', border: '1px solid var(--border-color)', 
              color: 'var(--text-secondary)', padding: '10px', borderRadius: '8px', cursor: 'pointer',
              justifyContent: 'center'
            }}>
              <LogOut size={16} /> Logout
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div style={{ flex: 1, padding: '40px', overflowY: 'auto', background: 'var(--bg-primary)' }}>
          {tab === 'uploads' && (
            <div>
              <input 
                type="file" 
                id="hub-video-upload" 
                style={{ display: 'none' }} 
                accept="video/*" 
                onChange={(e) => {
                  if (e.target.files.length > 0) {
                    onUpload(e.target.files[0]);
                    e.target.value = ''; // Reset value to allow retrying the same file
                  }
                }} 
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                <h1 style={{ fontSize: '2rem', margin: 0 }}>My Uploads</h1>
                <button onClick={handleDirectUploadClick} style={{ 
                  background: 'var(--accent)', color: '#fff', border: 'none', padding: '10px 20px', 
                  borderRadius: '24px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
                  fontWeight: '500'
                }}>
                  <Plus size={18} /> Upload New Video
                </button>
              </div>

              {isUploading && (
                <div style={{ background: 'var(--bg-secondary)', padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem', border: '1px solid var(--accent)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                    <span style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>Uploading to Cloud Workspace...</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{uploadProgress}% ({uploadSpeed} MB/s) - {timeRemaining}s remaining</span>
                  </div>
                  <div style={{ height: '8px', background: 'var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${uploadProgress}%`, background: 'var(--accent)', transition: 'width 0.3s ease' }}></div>
                  </div>
                </div>
              )}

              {uploadError && (
                <div style={{ color: 'var(--error)', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', marginBottom: '2rem', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  {uploadError}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '24px' }}>
                {localVideos.length === 0 ? (
                  <div 
                    onClick={handleDirectUploadClick}
                    style={{ 
                      border: '2px dashed var(--border-color)', borderRadius: '16px', padding: '40px 20px',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)',
                      minHeight: '200px'
                    }}
                  >
                    <Upload size={32} style={{ marginBottom: '16px' }} />
                    <p style={{ margin: 0, fontWeight: '500', color: 'var(--text-primary)' }}>Upload New Video</p>
                    <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem' }}>Drag & drop or click to browse</p>
                  </div>
                ) : (
                  localVideos.map((vid, idx) => (
                    <div key={idx} style={{ 
                      background: 'var(--bg-secondary)', borderRadius: '16px', padding: '20px',
                      border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column'
                    }}>
                      <div style={{ 
                        width: '100%', height: '140px', 
                        background: 'linear-gradient(135deg, var(--bg-secondary) 0%, #1e293b 100%)', 
                        borderRadius: '8px', 
                        overflow: 'hidden', marginBottom: '16px', display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-color)',
                        position: 'relative', color: 'var(--text-secondary)', gap: '8px',
                        boxShadow: 'inset 0 0 20px rgba(0,0,0,0.5)'
                      }}>
                        <Video size={40} style={{ color: 'var(--accent)', filter: 'drop-shadow(0 0 8px var(--accent))', opacity: 0.8 }} />
                        <span style={{ fontSize: '0.75rem', fontWeight: '500', letterSpacing: '0.05em', textTransform: 'uppercase', opacity: 0.6 }}>Video Upload</span>
                      </div>
                      <h3 style={{ margin: '0 0 8px 0', fontSize: '1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {getCleanFilename(vid.name || vid)}
                      </h3>
                      <p style={{ margin: '0 0 16px 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {((vid.size || 0) / (1024*1024)).toFixed(1)} MB • {vid.created_at ? new Date(vid.created_at).toLocaleDateString() : 'N/A'}
                      </p>
                      <button 
                        onClick={() => onSelectVideo(vid.name || vid)}
                        style={{ 
                          marginTop: 'auto', width: '100%', background: 'transparent', border: '1px solid var(--accent)',
                          color: 'var(--accent)', padding: '10px', borderRadius: '8px', cursor: 'pointer',
                          fontWeight: '500'
                        }}
                      >
                        Start Edit Session
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {tab === 'edits' && (
            <div>
              <h1 style={{ fontSize: '2rem', margin: '0 0 32px 0' }}>Past Edits</h1>
              {sessions.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)' }}>No past edits found.</p>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
                  {sessions.map(s => {
                    const status = s.status || 'draft';
                    const isComplete = status === 'complete';
                    const isFailed = status === 'error' || status === 'failed';
                    const isProcessing = ['processing', 'queued', 'scanning', 'analyzing', 'calibrating', 'rendering', 'cutting'].includes(status);

                    const statusColor = isComplete ? '#22c55e' : isFailed ? '#ef4444' : isProcessing ? '#f59e0b' : 'var(--text-secondary)';
                    const statusLabel = isComplete ? 'Complete' : isFailed ? 'Failed' : isProcessing ? 'Processing' : 'Draft';
                    
                    const sessionDate = s.created_at || s.updated_at;
                    
                    return (
                    <div 
                      key={s.id} 
                      style={{ 
                        background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px',
                        border: '1px solid var(--border-color)',
                        transition: 'border-color 0.2s, transform 0.2s',
                        display: 'flex', flexDirection: 'column'
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-color)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                    >
                      <div 
                        onClick={() => onSelectSession(s.id)}
                        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}
                      >
                        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.05rem' }}>
                          <Film size={18} color="var(--accent)" /> {s.title || 'Untitled Session'}
                        </h4>
                        <span style={{
                          fontSize: '0.7rem', fontWeight: 600, padding: '3px 10px', borderRadius: '999px',
                          background: `${statusColor}22`, color: statusColor, textTransform: 'uppercase', letterSpacing: '0.5px'
                        }}>{statusLabel}</span>
                      </div>
                      <p 
                        onClick={() => onSelectSession(s.id)}
                        style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: s.videoUrl ? '16px' : '0' }}
                      >
                        {sessionDate ? new Date(sessionDate).toLocaleString() : 'N/A'}
                      </p>
                      
                      {s.videoUrl && (
                        <div style={{ marginTop: 'auto', borderRadius: '8px', overflow: 'hidden', background: '#000' }}>
                          <video 
                            src={s.videoUrl} 
                            controls 
                            playsInline
                            style={{ width: '100%', display: 'block', maxHeight: '200px', objectFit: 'contain' }}
                          />
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {tab === 'billing' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                <h1 style={{ fontSize: '2rem', margin: 0 }}>Pricing Plans</h1>
                
                {/* Billing Cycle Toggle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'var(--bg-secondary)', padding: '6px 16px', borderRadius: '20px', border: '1px solid var(--border-color)' }}>
                  <span style={{ fontSize: '0.9rem', color: !isYearly ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: !isYearly ? '600' : 'normal' }}>Monthly</span>
                  <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px', margin: 0 }}>
                    <input type="checkbox" checked={isYearly} onChange={() => setIsYearly(!isYearly)} style={{ opacity: 0, width: 0, height: 0 }} />
                    <span className="slider round" style={{ borderRadius: '20px' }}></span>
                  </label>
                  <span style={{ fontSize: '0.9rem', color: isYearly ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: isYearly ? '600' : 'normal', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    Yearly
                    <span style={{ background: 'var(--accent)', color: '#fff', fontSize: '0.7rem', padding: '1px 6px', borderRadius: '10px', fontWeight: 'bold' }}>-20%</span>
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                
                {/* Free Trial */}
                <div style={{ flex: '1', minWidth: '250px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '16px', padding: '32px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ margin: '0 0 16px 0', fontSize: '1.25rem' }}>7-Day Free Trial</h3>
                  <div style={{ fontSize: '2.5rem', fontWeight: 'bold', marginBottom: '24px' }}>$0<span style={{fontSize: '1rem', color: 'var(--text-secondary)'}}>/7 days</span></div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 32px 0', display: 'flex', flexDirection: 'column', gap: '12px', color: 'var(--text-secondary)' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 1 Video Generation Limit</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 2GB Storage</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 7-day video retention</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> Account expires after 7 days</li>
                  </ul>
                  <button disabled style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '8px' }}>
                    {(!user || user?.plan_tier === 'FREE') ? 'Current Plan' : 'Free Trial'}
                  </button>
                </div>

                {/* Basic */}
                <div style={{ flex: '1', minWidth: '250px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '16px', padding: '32px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ margin: '0 0 16px 0', fontSize: '1.25rem' }}>Basic</h3>
                  <div style={{ fontSize: '2.5rem', fontWeight: 'bold', marginBottom: '24px' }}>
                    ${isYearly ? '30' : '3'}
                    <span style={{fontSize: '1rem', color: 'var(--text-secondary)'}}>/{isYearly ? 'yr' : 'mo'}</span>
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 32px 0', display: 'flex', flexDirection: 'column', gap: '12px', color: 'var(--text-secondary)' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> Unlimited Match Highlights</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 2 Player Highlights/day</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 25GB Storage</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 30-day video retention</li>
                  </ul>
                  {user?.plan_tier === 'BASIC' ? (
                    <button disabled style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '8px' }}>
                      Current Plan
                    </button>
                  ) : user?.plan_tier === 'PRO' ? (
                    <button disabled style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '8px' }}>
                      Basic Plan
                    </button>
                  ) : (
                    <button onClick={() => onInitiatePayment('basic')} style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
                      Upgrade to Basic
                    </button>
                  )}
                </div>

                {/* Pro */}
                <div style={{ flex: '1', minWidth: '250px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '16px', padding: '32px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ margin: '0 0 16px 0', fontSize: '1.25rem' }}>Pro</h3>
                  <div style={{ fontSize: '2.5rem', fontWeight: 'bold', marginBottom: '24px' }}>
                    ${isYearly ? '75' : '7.50'}
                    <span style={{fontSize: '1rem', color: 'var(--text-secondary)'}}>/{isYearly ? 'yr' : 'mo'}</span>
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 32px 0', display: 'flex', flexDirection: 'column', gap: '12px', color: 'var(--text-secondary)' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> Unlimited Match Highlights</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> Unlimited Player Highlights</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> 100GB Storage</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="var(--accent)"/> Unlimited retention</li>
                  </ul>
                  {user?.plan_tier === 'PRO' ? (
                    <button disabled style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '8px' }}>
                      Current Plan
                    </button>
                  ) : (
                    <button onClick={() => onInitiatePayment('pro')} style={{ marginTop: 'auto', width: '100%', padding: '12px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
                      Upgrade to Pro
                    </button>
                  )}
                </div>

              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HubModal;

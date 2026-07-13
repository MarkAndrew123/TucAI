import React from 'react';
import { ArrowLeft } from 'lucide-react';

const Privacy = ({ onBack }) => {
  return (
    <div className="landing-layout" style={{ minHeight: '100vh', padding: '40px 20px' }}>
      <div style={{ maxWidth: '800px', margin: '0 auto', background: 'var(--bg-secondary)', padding: '40px', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
        <button className="btn btn-ghost" onClick={onBack} style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ArrowLeft size={18} /> Back to Home
        </button>
        
        <h1 style={{ fontSize: '2.5rem', marginBottom: '24px', color: 'var(--text-primary)' }}>Privacy Policy</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '32px' }}>Last updated: July 2026</p>

        <div style={{ color: 'var(--text-secondary)', lineHeight: '1.6', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>1. Information We Collect</h2>
            <p>When you use Tuc AI, we collect information that you provide directly to us. This includes your name, email address, and any videos or content you upload for processing. We also collect basic usage data and analytics to improve our service.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>2. How We Use Your Information</h2>
            <p>We use the information we collect to operate, maintain, and provide the features of Tuc AI. Your uploaded videos are processed securely by our AI pipelines solely for the purpose of generating the highlights and edits you request.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>3. Data Storage and Security</h2>
            <p>Your data is stored securely using industry-standard cloud providers (Google Cloud). We implement reasonable security measures to protect your personal information and uploaded media. Videos may be retained temporarily to provide the service and are subject to your account's retention limits.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>4. Google OAuth Data</h2>
            <p>If you choose to log in using Google, we access your basic profile information (name and email) purely for authentication and account creation purposes. We do not access your private emails, contacts, or Google Drive files.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>5. Contact Us</h2>
            <p>If you have any questions about this Privacy Policy, please contact us at: vicandyenoch@gmail.com</p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default Privacy;

import React from 'react';
import { ArrowLeft } from 'lucide-react';

const Terms = ({ onBack }) => {
  return (
    <div className="landing-layout" style={{ minHeight: '100vh', padding: '40px 20px' }}>
      <div style={{ maxWidth: '800px', margin: '0 auto', background: 'var(--bg-secondary)', padding: '40px', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
        <button className="btn btn-ghost" onClick={onBack} style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ArrowLeft size={18} /> Back to Home
        </button>
        
        <h1 style={{ fontSize: '2.5rem', marginBottom: '24px', color: 'var(--text-primary)' }}>Terms of Service</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '32px' }}>Last updated: July 2026</p>

        <div style={{ color: 'var(--text-secondary)', lineHeight: '1.6', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>1. Acceptance of Terms</h2>
            <p>By accessing or using Tuc AI ("the Service"), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the Service.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>2. Use of the Service</h2>
            <p>You agree to use the Service only for lawful purposes. You are responsible for any video content you upload and edit. You must ensure you have the necessary rights and permissions to process the video footage you upload.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>3. User Accounts</h2>
            <p>To use certain features, you must create an account. You are responsible for maintaining the confidentiality of your account credentials. The free tier and any associated quotas are subject to change at our discretion.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>4. Intellectual Property</h2>
            <p>Tuc AI claims no ownership rights over the video content you upload. However, the software, algorithms, and interface of Tuc AI are our exclusive property.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>5. Limitation of Liability</h2>
            <p>Tuc AI is provided "as is" without warranties of any kind. We are not liable for any lost data, disrupted services, or damages arising from your use of the platform.</p>
          </section>

          <section>
            <h2 style={{ color: 'var(--text-primary)', fontSize: '1.5rem', marginBottom: '12px' }}>6. Contact</h2>
            <p>For support or legal inquiries, contact us at: vicandyenoch@gmail.com</p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default Terms;

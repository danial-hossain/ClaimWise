import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="cw-site-footer">
      <div><p className="cw-footer-title"><ShieldCheck size={17} aria-hidden="true" />Policy guidance, grounded in your documents.</p><p>ClaimWise explains uploaded policy evidence. Information is for guidance and does not guarantee coverage, payment, or claim approval. Confirm requirements and decisions with your insurer.</p></div>
    </footer>
  );
}

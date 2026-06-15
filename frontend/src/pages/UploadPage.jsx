import { Link } from 'react-router-dom';
import Upload from '../components/Upload';

export default function UploadPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-slate-900">Upload Documents</h1>
        <p className="mt-2 text-slate-600">Upload up to 3 PDFs and ask questions about them.</p>
      </div>
      <Upload />
      <div className="mt-8 flex justify-center gap-4 text-sm text-indigo-600">
        <Link to="/documents" className="hover:underline">View Documents</Link>
        <span className="text-slate-300">|</span>
        <Link to="/chat" className="hover:underline">Start Chatting</Link>
      </div>
    </div>
  );
}

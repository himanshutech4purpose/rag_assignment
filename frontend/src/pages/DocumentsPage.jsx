import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Documents from '../components/Documents';
import { listDocuments, deleteDocument } from '../api';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);

  const load = async () => {
    const { data } = await listDocuments();
    setDocuments(data.documents);
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    await deleteDocument(id);
    await load();
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Your Documents</h1>
          <p className="text-slate-600">Manage uploaded PDFs.</p>
        </div>
        <Link
          to="/chat"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
        >
          Go to Chat
        </Link>
      </div>
      <Documents documents={documents} onDelete={handleDelete} />
    </div>
  );
}

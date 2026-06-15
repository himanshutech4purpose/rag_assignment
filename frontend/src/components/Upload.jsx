import { useState } from 'react';
import { uploadFiles } from '../api';

export default function Upload() {
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFiles = (selected) => {
    setError(null);
    setResult(null);
    const pdfFiles = Array.from(selected).filter((f) => f.type === 'application/pdf');
    if (pdfFiles.length !== selected.length) {
      setError('Only PDF files are supported.');
    }
    if (pdfFiles.length > 3) {
      setError('Please select a maximum of 3 PDFs.');
      setFiles(pdfFiles.slice(0, 3));
      return;
    }
    setFiles(pdfFiles);
  };

  const handleSubmit = async () => {
    if (files.length === 0) return;
    if (files.length > 3) {
      setError('Please select a maximum of 3 PDFs.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await uploadFiles(files);
      const totalChunks = data.documents.reduce((sum, d) => sum + d.chunks_inserted, 0);
      setResult(`${data.documents.length} documents indexed, ${totalChunks} chunks stored`);
      setFiles([]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process files. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-10 text-center transition ${
          dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white'
        }`}
      >
        <p className="text-slate-600 mb-4">Drag and drop PDFs here, or click to select</p>
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
          id="file-input"
        />
        <label
          htmlFor="file-input"
          className="inline-block px-5 py-2.5 bg-indigo-600 text-white rounded-lg cursor-pointer hover:bg-indigo-700 transition"
        >
          Select PDFs
        </label>
      </div>

      {files.length > 0 && (
        <div className="mt-6 space-y-2">
          {files.map((f) => (
            <div key={f.name} className="bg-white border rounded-lg px-4 py-3 flex justify-between">
              <span className="font-medium text-slate-700">{f.name}</span>
              <span className="text-slate-500 text-sm">{(f.size / 1024).toFixed(1)} KB</span>
            </div>
          ))}
        </div>
      )}

      {error && <p className="mt-4 text-red-600 text-sm">{error}</p>}
      {result && <p className="mt-4 text-green-600 text-sm">{result}</p>}

      <button
        onClick={handleSubmit}
        disabled={loading || files.length === 0}
        className="mt-6 w-full px-5 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        {loading ? 'Processing...' : 'Upload PDFs'}
      </button>
    </div>
  );
}

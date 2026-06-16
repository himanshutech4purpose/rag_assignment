import { useState } from 'react';
import { uploadFiles, getDocumentChunks } from '../api';

export default function Upload() {
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [chunksByDoc, setChunksByDoc] = useState({});
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [error, setError] = useState(null);

  const handleFiles = (selected) => {
    setError(null);
    setResult(null);
    setChunksByDoc({});
    setExpandedDoc(null);
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
    setChunksByDoc({});
    setExpandedDoc(null);
    try {
      const chunkSize = localStorage.getItem('rag_chunk_size')
        ? parseInt(localStorage.getItem('rag_chunk_size'), 10)
        : undefined;
      const chunkOverlap = localStorage.getItem('rag_chunk_overlap')
        ? parseInt(localStorage.getItem('rag_chunk_overlap'), 10)
        : undefined;
      const { data } = await uploadFiles(files, { chunkSize, chunkOverlap });

      const totalChunks = data.documents.reduce((sum, d) => sum + d.chunks_inserted, 0);
      const totalImages = data.documents.reduce((sum, d) => sum + (d.images_ignored || 0), 0);
      const imageNotice =
        totalImages > 0
          ? ` Found ${totalImages} image${totalImages === 1 ? '' : 's'} in PDF${
              data.documents.length === 1 ? '' : 's'
            } which ${totalImages === 1 ? 'was' : 'were'} ignored.`
          : '';
      setResult(
        `${data.documents.length} document${data.documents.length === 1 ? '' : 's'} indexed, ${totalChunks} chunk${totalChunks === 1 ? '' : 's'} stored.${imageNotice}`
      );

      const chunksMap = {};
      for (const doc of data.documents) {
        if (doc.chunks_inserted > 0) {
          const { data: chunks } = await getDocumentChunks(doc.id);
          chunksMap[doc.id] = { name: doc.name, chunks };
        }
      }
      setChunksByDoc(chunksMap);
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

      {Object.keys(chunksByDoc).length > 0 && (
        <div className="mt-8 space-y-4">
          <h3 className="text-lg font-semibold text-slate-800">Chunks</h3>
          {Object.entries(chunksByDoc).map(([docId, { name, chunks }]) => (
            <div key={docId} className="bg-white border rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedDoc(expandedDoc === docId ? null : docId)}
                className="w-full px-4 py-3 flex items-center justify-between bg-slate-50 hover:bg-slate-100 transition"
              >
                <span className="font-medium text-slate-700">{name}</span>
                <span className="text-sm text-slate-500">
                  {chunks.length} chunk{chunks.length === 1 ? '' : 's'}
                </span>
              </button>
              {expandedDoc === docId && (
                <div className="divide-y max-h-96 overflow-y-auto">
                  {chunks.map((chunk) => (
                    <div key={chunk.id} className="px-4 py-3 text-sm">
                      <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                        <span>Chunk {chunk.chunk_index}</span>
                        <span>•</span>
                        <span>Page {chunk.page_number ?? 'unknown'}</span>
                      </div>
                      <p className="text-slate-700 whitespace-pre-wrap">{chunk.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

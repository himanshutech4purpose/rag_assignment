import { useState } from 'react';
import { format } from '../utils';
import { getDocumentChunks } from '../api';

export default function Documents({ documents, onDelete }) {
  const [expandedDocId, setExpandedDocId] = useState(null);
  const [chunksByDoc, setChunksByDoc] = useState({});
  const [loadingDocId, setLoadingDocId] = useState(null);

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500">
        No documents uploaded yet.
      </div>
    );
  }

  const statusBadge = (status) => {
    const styles = {
      uploaded: 'bg-slate-100 text-slate-600',
      processing: 'bg-yellow-100 text-yellow-700',
      indexed: 'bg-green-100 text-green-700',
      error: 'bg-red-100 text-red-700',
    };
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.uploaded}`}>
        {status}
      </span>
    );
  };

  const handleToggleChunks = async (doc) => {
    if (expandedDocId === doc.id) {
      setExpandedDocId(null);
      return;
    }
    setExpandedDocId(doc.id);
    if (!chunksByDoc[doc.id]) {
      setLoadingDocId(doc.id);
      try {
        const { data } = await getDocumentChunks(doc.id);
        setChunksByDoc((prev) => ({ ...prev, [doc.id]: data }));
      } finally {
        setLoadingDocId(null);
      }
    }
  };

  return (
    <div className="space-y-3">
      <div className="overflow-hidden border border-slate-200 rounded-xl bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Size</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {documents.map((doc) => (
              <>
                <tr key={doc.id} className={expandedDocId === doc.id ? 'bg-indigo-50/40' : ''}>
                  <td className="px-6 py-4 text-sm font-medium text-slate-900">{doc.name}</td>
                  <td className="px-6 py-4 text-sm text-slate-500">{format.bytes(doc.size_bytes)}</td>
                  <td className="px-6 py-4">{statusBadge(doc.status)}</td>
                  <td className="px-6 py-4 text-sm text-slate-500">{format.date(doc.created_at)}</td>
                  <td className="px-6 py-4 text-right space-x-3">
                    {doc.status === 'indexed' && (
                      <button
                        onClick={() => handleToggleChunks(doc)}
                        className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                      >
                        {expandedDocId === doc.id ? 'Hide Chunks' : 'View Chunks'}
                      </button>
                    )}
                    <button
                      onClick={() => onDelete(doc.id)}
                      className="text-red-600 hover:text-red-800 text-sm font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {expandedDocId === doc.id && (
                  <tr key={`${doc.id}-chunks`}>
                    <td colSpan={5} className="px-0 py-0 bg-slate-50 border-t border-indigo-100">
                      <div className="px-6 py-4">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">
                            Chunks
                          </span>
                          {chunksByDoc[doc.id] && (
                            <span className="bg-indigo-100 text-indigo-700 text-xs font-medium px-2 py-0.5 rounded-full">
                              {chunksByDoc[doc.id].length}
                            </span>
                          )}
                        </div>
                        {loadingDocId === doc.id ? (
                          <p className="text-sm text-slate-500 py-2">Loading chunks…</p>
                        ) : (
                          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                            {(chunksByDoc[doc.id] || []).map((chunk) => (
                              <div
                                key={chunk.id}
                                className="bg-white border border-slate-200 rounded-lg p-3 text-sm"
                              >
                                <div className="flex items-center gap-3 mb-1.5 text-xs text-slate-500 font-medium">
                                  <span className="bg-slate-100 px-2 py-0.5 rounded">
                                    Chunk #{chunk.chunk_index}
                                  </span>
                                  <span>Page {chunk.page_number ?? 'unknown'}</span>
                                </div>
                                <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                                  {chunk.content}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

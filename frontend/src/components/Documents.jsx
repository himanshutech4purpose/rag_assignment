import { format } from '../utils';

export default function Documents({ documents, onDelete }) {
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

  return (
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
            <tr key={doc.id}>
              <td className="px-6 py-4 text-sm font-medium text-slate-900">{doc.name}</td>
              <td className="px-6 py-4 text-sm text-slate-500">{format.bytes(doc.size_bytes)}</td>
              <td className="px-6 py-4">{statusBadge(doc.status)}</td>
              <td className="px-6 py-4 text-sm text-slate-500">{format.date(doc.created_at)}</td>
              <td className="px-6 py-4 text-right">
                <button
                  onClick={() => onDelete(doc.id)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

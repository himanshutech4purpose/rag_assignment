import { useState } from 'react';

export default function Citation({ source }) {
  const [expanded, setExpanded] = useState(false);
  const content = source.content || '';

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-indigo-500" />
          <span className="font-semibold text-slate-700 text-sm">{source.document_name}</span>
        </div>
        <span className="text-xs text-slate-500">
          page {source.page_number || 'unknown'} • chunk {source.chunk_index} • score {source.score?.toFixed(2)}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        {expanded ? content : content.slice(0, 120)}
        {content.length > 120 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="ml-1 text-indigo-600 hover:underline text-xs"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </p>
    </div>
  );
}

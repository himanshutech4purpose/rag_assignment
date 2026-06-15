export const format = {
  bytes: (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  },
  date: (iso) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  },
};

const DATABASE_NAME = 'claimwise-policy-pdfs';
const STORE_NAME = 'originals';

interface CachedPdf {
  documentHash: string;
  file: Blob;
}

function openPdfDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'documentHash' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Could not open the PDF cache.'));
  });
}

export async function cachePolicyPdf(documentHash: string, file: Blob): Promise<void> {
  const database = await openPdfDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readwrite');
      transaction.objectStore(STORE_NAME).put({ documentHash, file } satisfies CachedPdf);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Could not save the PDF preview.'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Saving the PDF preview was interrupted.'));
    });
  } finally {
    database.close();
  }
}

export async function getCachedPolicyPdf(documentHash: string): Promise<Blob | null> {
  const database = await openPdfDatabase();
  try {
    return await new Promise<Blob | null>((resolve, reject) => {
      const request = database.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(documentHash);
      request.onsuccess = () => resolve((request.result as CachedPdf | undefined)?.file ?? null);
      request.onerror = () => reject(request.error ?? new Error('Could not read the PDF preview.'));
    });
  } finally {
    database.close();
  }
}

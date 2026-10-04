import { useEffect } from 'react';

/**
 * Custom hook to dynamically update page title and meta description per route.
 */
export const useDocumentTitle = (title: string, description?: string) => {
  useEffect(() => {
    const fullTitle = title.includes('ProctorAI') ? title : `${title} — ProctorAI`;
    document.title = fullTitle;

    if (description) {
      let metaDesc = document.querySelector<HTMLMetaElement>('meta[name="description"]');
      if (!metaDesc) {
        metaDesc = document.createElement('meta');
        metaDesc.name = 'description';
        document.head.appendChild(metaDesc);
      }
      metaDesc.content = description;
    }
  }, [title, description]);
};

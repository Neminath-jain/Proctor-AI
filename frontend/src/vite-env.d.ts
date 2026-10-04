/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_ML_SERVICE_URL: string;
  readonly VITE_JUDGE0_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEFAULT_STORE_ID?: string;
  readonly VITE_DEFAULT_TIMEZONE?: string;
  readonly VITE_STORE_NAME?: string;
  readonly VITE_STORE_ZONE_COUNT?: string;
  readonly VITE_OPENAI_MODEL?: string;
  readonly VITE_YOLO_MODEL?: string;
  readonly VITE_YOLO_CONFIDENCE?: string;
  readonly VITE_YOLO_IOU?: string;
  readonly VITE_REID_THRESHOLD?: string;
  readonly VITE_REID_REENTRY_WINDOW_MINUTES?: string;
  readonly VITE_STAFF_CONFIDENCE_THRESHOLD?: string;
  readonly VITE_API_PORT?: string;
  readonly VITE_ENVIRONMENT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

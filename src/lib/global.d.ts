export {};

declare global {
  interface Window {
    storage: {
      get: (key: string, sync?: boolean) => Promise<{ key: string; value: string }>;
      set: (key: string, value: string, sync?: boolean) => Promise<{ key: string; value: string }>;
    };
  }
}

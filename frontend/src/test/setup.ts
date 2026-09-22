import '@testing-library/jest-dom';

// jsdom doesn't implement ResizeObserver: stub it for Radix UI ScrollArea
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

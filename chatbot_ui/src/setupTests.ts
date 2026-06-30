import "@testing-library/jest-dom";

// use-stick-to-bottom uses ResizeObserver which jsdom doesn't implement
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
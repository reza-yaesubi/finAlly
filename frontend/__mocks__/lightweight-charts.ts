export const ColorType = { Solid: "solid" };

const mockSeries = {
  setData: jest.fn(),
  update: jest.fn(),
  applyOptions: jest.fn(),
};

const mockTimeScale = {
  scrollToRealTime: jest.fn(),
};

const mockChart = {
  addLineSeries: jest.fn(() => mockSeries),
  applyOptions: jest.fn(),
  timeScale: jest.fn(() => mockTimeScale),
  remove: jest.fn(),
};

export const createChart = jest.fn(() => mockChart);

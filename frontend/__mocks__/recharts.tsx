import React from "react";

export const Treemap = ({ children }: { children?: React.ReactNode }) => (
  <div data-testid="treemap">{children}</div>
);
export const ResponsiveContainer = ({
  children,
}: {
  children?: React.ReactNode;
}) => <div data-testid="responsive-container">{children}</div>;
export const LineChart = ({ children }: { children?: React.ReactNode }) => (
  <div data-testid="line-chart">{children}</div>
);
export const Line = () => <div />;
export const XAxis = () => <div />;
export const YAxis = () => <div />;
export const Tooltip = () => <div />;
export const CartesianGrid = () => <div />;

/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

const SHADOW_COLOR = '#044EF3';
export const ROLLUP_COLOR = '#F2F2F2';

export enum NodeColors {
  rollup = 'roll_up',
  type1 = 'python_source',
  type2 = 'python_sources',
  type3 = 'python_test',
  type4 = 'python_tests',
  type5 = 'python_requirement',
  type6 = 'pex_binary',
  type7 = 'python_distribution',
}

export const getNodeColor = (type: string) => {
  switch (type) {
    case NodeColors.rollup:
      return ROLLUP_COLOR;
    case NodeColors.type1:
    case NodeColors.type2:
      return '#F2C697';
    case NodeColors.type3:
    case NodeColors.type4:
      return '#84F3AA';
    case NodeColors.type5:
      return '#E88E8E';
    case NodeColors.type6:
      return '#E69DF1';
    case NodeColors.type7:
      return '#8886F4';
    default:
      return '#D1D1D1';
  }
};

export const paintCircle = (
  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  ctx: any,
  x: number,
  y: number,
  radius: number,
  color: string,
  isSelected: boolean,
  globalScale: number,
  isVisible: boolean
) => {
  ctx.beginPath();

  ctx.fillStyle = color;
  if (!isVisible) {
    ctx.globalAlpha = 0.2;
  }

  const maxRadius = 15;
  let calcRadius;

  if (globalScale > 3.5) {
    calcRadius = radius;
  } else {
    calcRadius = Math.min(
      isSelected ? (3.5 * radius) / globalScale : radius,
      maxRadius
    );
  }

  ctx.arc(x, y, calcRadius, 2 * Math.PI, false);

  if (isSelected) {
    ctx.shadowBlur = 30;
    ctx.shadowColor = SHADOW_COLOR;
  } else {
    ctx.shadowBlur = 0;
  }
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = '#000000';

  if (isSelected) {
    ctx.lineWidth = 0.4;
  } else {
    ctx.lineWidth = 0.2;
  }

  ctx.stroke();
  ctx.globalAlpha = 1;
};

export const paintRoundRectange = (
  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  ctx: any,
  x: number,
  y: number,
  borderRadius: number,
  size: number,
  color: string,
  isSelected: boolean,
  globalScale: number,
  isVisible: boolean
) => {
  const maxSize = 27;
  let calcSize;

  if (globalScale > 3.5) {
    calcSize = size;
  } else {
    calcSize = Math.min(
      isSelected ? (3.5 * size) / globalScale : size,
      maxSize
    );
  }

  const calcX = x - calcSize / 2;
  const calcY = y - calcSize / 2;

  ctx.fillStyle = color;

  if (!isVisible) {
    ctx.globalAlpha = 0.2;
  }

  ctx.beginPath();
  ctx.moveTo(calcX + borderRadius, calcY);
  ctx.lineTo(calcX + calcSize - borderRadius, calcY);
  ctx.quadraticCurveTo(
    calcX + calcSize,
    calcY,
    calcX + calcSize,
    calcY + borderRadius
  );
  ctx.lineTo(calcX + calcSize, calcY + calcSize - borderRadius);
  ctx.quadraticCurveTo(
    calcX + calcSize,
    calcY + calcSize,
    calcX + calcSize - borderRadius,
    calcY + calcSize
  );
  ctx.lineTo(calcX + borderRadius, calcY + calcSize);
  ctx.quadraticCurveTo(
    calcX,
    calcY + calcSize,
    calcX,
    calcY + calcSize - borderRadius
  );
  ctx.lineTo(calcX, calcY + borderRadius);
  ctx.quadraticCurveTo(calcX, calcY, calcX + borderRadius, calcY);
  ctx.closePath();

  if (isSelected) {
    ctx.shadowBlur = 10;
    ctx.shadowColor = SHADOW_COLOR;
    ctx.lineWidth = 0.4;
  } else {
    ctx.shadowBlur = 0;
    ctx.lineWidth = 0.2;
  }

  ctx.fill();
  ctx.strokeStyle = 'rgb(0, 0, 0)';
  ctx.stroke();
  ctx.globalAlpha = 1;
};

export const paintText = (
  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  ctx: any,
  x: number,
  y: number,
  globalScale: number,
  isSelected: boolean,
  isVisible: boolean,
  displayName?: string
) => {
  let fontSize = 5;
  if (globalScale > 10) {
    fontSize = 1.5;
  } else if (globalScale > 7) {
    fontSize = 2;
  } else if (globalScale > 5) {
    fontSize = 2.5;
  } else if (globalScale > 3.6) {
    fontSize = 3;
  } else if (globalScale > 3) {
    fontSize = 3.5;
  } else if (globalScale > 2.4) {
    fontSize = 5;
  }

  if (!isVisible) {
    ctx.globalAlpha = 0.2;
  }

  ctx.shadowBlur = 0;
  ctx.font = `${fontSize}px Sans-Serif`;

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  if (isSelected) {
    ctx.fillStyle = 'rgba(0,0,0,1)';
  } else {
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
  }

  ctx.fillText(displayName, x, y);
  ctx.globalAlpha = 1;
};

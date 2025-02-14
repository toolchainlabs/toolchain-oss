/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { NodeColors, getNodeColor, ROLLUP_COLOR } from './paint-node-utils';

describe('Paint node utils', () => {
  it('should return proper node color based on node type', () => {
    expect(getNodeColor(NodeColors.rollup)).toBe(ROLLUP_COLOR);
    expect(getNodeColor(NodeColors.type1)).toBe('#F2C697');
    expect(getNodeColor(NodeColors.type2)).toBe('#F2C697');
    expect(getNodeColor(NodeColors.type3)).toBe('#84F3AA');
    expect(getNodeColor(NodeColors.type4)).toBe('#84F3AA');
    expect(getNodeColor(NodeColors.type5)).toBe('#E88E8E');
    expect(getNodeColor(NodeColors.type6)).toBe('#E69DF1');
    expect(getNodeColor(NodeColors.type7)).toBe('#8886F4');
    expect(getNodeColor('')).toBe('#D1D1D1');
  });
});

/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { renderHook, act } from '@testing-library/react-hooks';
import useWindowSize from './useWindowSize';

describe('useWindowSize hook', () => {
  it('should return current window height and width', async () => {
    const { result } = renderHook(() => useWindowSize());

    global.innerWidth = 500;
    global.innerHeight = 700;

    act(() => {
      global.dispatchEvent(new Event('resize'));
    });

    expect(result.current.windowHeight).toBe(700);
    expect(result.current.windowWidth).toBe(500);

    global.innerWidth = 1200;
    global.innerHeight = 800;

    act(() => {
      global.dispatchEvent(new Event('resize'));
    });

    expect(result.current.windowHeight).toBe(800);
    expect(result.current.windowWidth).toBe(1200);
  });
});

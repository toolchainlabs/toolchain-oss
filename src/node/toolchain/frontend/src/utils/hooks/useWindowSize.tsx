/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState, useEffect } from 'react';

type WindowSizeType = {
  windowHeight?: number;
  windowWidth?: number;
};

const useWindowSize = () => {
  const [windowSize, setWindowSize] = useState<WindowSizeType>({
    windowHeight: window.innerHeight,
    windowWidth: window.innerWidth,
  });

  useEffect(() => {
    const resizeEvent = () => {
      setWindowSize({
        windowHeight: window.innerHeight,
        windowWidth: window.innerWidth,
      });
    };

    window.addEventListener('resize', resizeEvent);

    return () => window.removeEventListener('resize', resizeEvent);
  }, []);

  return windowSize;
};

export default useWindowSize;

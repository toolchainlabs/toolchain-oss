/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import mediaQuery from 'css-mediaquery';

// jsdom renders with no width (elements or in the window). This fixes the issues hidden elements encounter in tests.
// As per: https://material-ui.com/components/use-media-query/#testing
const createMatchMedia = (width: number) => {
  return (query: any) => ({
    matches: mediaQuery.match(query, { width }),
    addListener: () => {},
    removeListener: () => {},
  });
};

export default createMatchMedia;

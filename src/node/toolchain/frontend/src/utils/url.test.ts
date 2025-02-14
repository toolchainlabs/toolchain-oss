/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import generateUrl from 'utils/url';

describe('generateUrl', () => {
  it('should generate URL', () => {
    expect(
      generateUrl('/a/b/c/d/e', 'https://example.com/', {
        f: 1,
        g: ['lorem', 'ipsum'],
        h: true,
        j: 'test',
      })
    ).toBe('https://example.com/a/b/c/d/e?f=1&g=lorem,ipsum&h=true&j=test');
  });
});

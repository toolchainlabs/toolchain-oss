/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { findParentAddress, findSearchSegment, getAncestors } from './utils';

describe('Utils', () => {
  it('should compute ancestor labels', () => {
    expect(getAncestors('foo/bar/baz')).toEqual([
      'foo/bar/baz',
      'foo/bar',
      'foo',
    ]);
  });

  it('should find node parent address #1', () => {
    const parentAddress = 'src/python/toolchain';
    const childAddress = parentAddress + '/__init__.py';

    expect(findParentAddress(childAddress)).toBe(parentAddress);
  });

  it('should find node parent address #2', () => {
    const parentAddress = '';
    const childAddress = parentAddress + 'src';

    expect(findParentAddress(childAddress)).toBe(parentAddress);
  });

  it('should find case-sensitive search parameter segment ', () => {
    const someWord = 'abcABC';
    const searchParam = 'AB';

    const searchResults = findSearchSegment(someWord, searchParam);

    expect(searchResults[0]).toBe('abc');
    expect(searchResults[1]).toBe('AB');
    expect(searchResults[2]).toBe('C');
  });

  it('should find case-unsensitive search parameter segment ', () => {
    const someWord = 'abcABC';
    const searchParam = 'AB';

    const searchResults = findSearchSegment(someWord, searchParam, {
      caseUnsensitive: true,
    });

    expect(searchResults[0]).toBe('');
    expect(searchResults[1]).toBe('ab');
    expect(searchResults[2]).toBe('cABC');
  });

  it('should return no results if search parameter is not found', () => {
    const someWord = 'abcABC';
    const searchParam = '123';

    const searchResults = findSearchSegment(someWord, searchParam, {
      caseUnsensitive: true,
    });

    expect(searchResults[0]).toBe('');
    expect(searchResults[1]).toBe('');
    expect(searchResults[2]).toBe('');
  });
});

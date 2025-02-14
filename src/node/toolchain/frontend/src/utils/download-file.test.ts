/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { waitFor } from '@testing-library/react';
import downloadFile from 'utils/download-file';
import { traceData } from '../../tests/__fixtures__/download-file';

describe('download file', () => {
  it('should download file', async () => {
    const createObjectURL = jest.fn().mockReturnValue('file');
    Object.defineProperty(window.URL, 'createObjectURL', { value: createObjectURL });
    const link: any = {
      href: null,
      setAttribute: jest.fn(),
      click: jest.fn(),
    };
    jest.spyOn(document, 'createElement').mockReturnValue(link);
    jest.spyOn(document.body, 'appendChild').mockImplementation(jest.fn());
    jest.spyOn(document.body, 'removeChild').mockImplementation(jest.fn());
    const string = JSON.stringify(traceData);
    const bytes = new TextEncoder().encode(string);
    downloadFile(bytes, 'sample-name.json');

    expect(link.href).toBe('file');
    expect(link.click).toHaveBeenCalled();

    await waitFor(() => expect(document.body.removeChild).toHaveBeenCalled());
  });
});

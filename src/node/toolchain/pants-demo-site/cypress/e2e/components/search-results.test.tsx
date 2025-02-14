/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { nockResponse, defaultUrl } from '../utils';

describe('FileSystem ', () => {
  beforeEach(() => {
    nockResponse();
  });

  it('should find element by using search & select it', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('#search-box').type('src/python');
    cy.get('.search-result-item').first().click();

    cy.get('#description-display-name').contains(/^curator$/);
  });
});

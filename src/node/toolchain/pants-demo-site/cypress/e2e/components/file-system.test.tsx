/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { nockResponse, defaultUrl } from '../utils';

describe('FileSystem ', () => {
  beforeEach(() => {
    nockResponse();
  });

  it('should expand/collapse file-system tree on click', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div').contains(/^src$/);
    cy.get('div').contains('pytnon').should('not.exist');

    cy.get('div').get(`#chevron-src`).click({ force: true });
    cy.get('div').contains(/^python$/);
    cy.get('div').contains(/^curator$/);
    cy.get('div').contains(/^toolchain$/);

    cy.get('div').get('#chevron-src\\/python').click({ force: true });
    cy.get('div')
      .contains(/^curator$/)
      .should('not.exist');
    cy.get('div')
      .contains(/^toolchain$/)
      .should('not.exist');
  });
});

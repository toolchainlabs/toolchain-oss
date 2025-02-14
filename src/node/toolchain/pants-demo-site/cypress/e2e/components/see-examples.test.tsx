/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import {
  nockResponse,
  defaultUrl,
  processingInProgressResponse,
} from '../utils';

describe('FileSystem ', () => {
  beforeEach(() => {
    nockResponse(processingInProgressResponse);
  });

  it('should display examples screen on See Examples button click', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('button')
      .contains(/^see examples$/)
      .click({ force: true });
    cy.get('h3').contains(/^Example repos$/);
    cy.get('#examples-list');
  });

  it('should display eleven repo examples', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('button')
      .contains(/^see examples$/)
      .click({ force: true });
    cy.get('h3').contains(/^Example repos$/);
    cy.get('#examples-list').children().should('have.length', 11);
  });

  it('should go back to processing screen', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div').contains(/^Processing$/);

    cy.get('button')
      .contains(/^see examples$/)
      .click({ force: true });
    cy.get('h3').contains(/^Example repos$/);
    cy.get('div')
      .contains(/^Processing$/)
      .should('not.exist');

    cy.get('button')
      .contains(/go back/)
      .click({ force: true });
    cy.get('div').contains(/^Processing$/);
  });
});

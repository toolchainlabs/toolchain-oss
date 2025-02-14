/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { nockResponse, defaultUrl } from '../utils';

describe('Node Description ', () => {
  beforeEach(() => {
    nockResponse();
  });

  it('should display global types map on default', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div').contains('In this repo');
    cy.get('div').contains('type1');
    cy.get('div').contains('type2');
    cy.get('div').contains('Other target types');
  });

  it('should display node full name on filesystem click', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div')
      .contains(/^prod$/)
      .click({ force: true });
    cy.get('#description-display-name').contains(/^prod$/);

    cy.get('div').get(`#chevron-prod`).click({ force: true });

    cy.get('div')
      .contains(/^helm$/)
      .click();
    cy.get('#description-display-name').contains(/^helm$/);
  });

  it('should display dependencies list on rollup selection', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div')
      .contains(/^prod$/)
      .click({ force: true });

    cy.get('div').contains('Dependencies');
    cy.get('div').contains('In this repo').should('not.exist');
  });

  it('should display dependencies list on leaff selection', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('div').contains(/^six$/).click({ force: true });

    cy.get('div').contains('Dependencies');
    cy.get('div').contains('Type');
    cy.get('div').contains('In this repo').should('not.exist');
  });

  it('should display target types map on default', () => {
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.contains('prod').click();

    cy.get('div').contains('In this directory');
    cy.get('div').contains('Other target types');
  });
});

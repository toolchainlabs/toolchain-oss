// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

/// <reference types="cypress" />

context('Actions', () => {
  const baseLink = Cypress.env('INFOSITE_LINK');

  afterEach(() => {
    cy.clearCookies();
  });

  it('show home page', () => {
    cy.visit(baseLink);
    cy.get('input#acceptTermsButton').click();
    cy.get('h2 span.banner-large.h1')
      .should('be.visible')
      .should('have.text', 'The distributed software build system.');
  });
  it('Navigate to about us page', () => {
    cy.visit(baseLink);
    cy.get('input#acceptTermsButton').click();
    cy.get('a.about').click();
    cy.get('div.bio').should('have.length.least', 4);
  });
  it('Navigate to jobs', () => {
    cy.visit(baseLink);
    cy.get('input#acceptTermsButton').click();
    cy.get('a.jobs').click();
    cy.scrollTo(0, 200);
    cy.get('h2.section-title').should('be.visible').should('have.text', 'Careers');
  });
});

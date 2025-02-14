/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import {
  nockResponse,
  nockMailchimp,
  defaultUrl,
  DEFAULT_ACCOUNT_NAME,
  DEFAULT_REPO_NAME,
  processingFailedResponse,
  processingInProgressResponse,
} from '../utils';

describe('<Results />', () => {
  it('should display processing text and explanation', () => {
    nockResponse(processingInProgressResponse);

    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('h3').contains(/processing/i);
    cy.get('p').contains(/This takes a few minutes the first time/i);
  });

  it('should span links in footer amd detailed text', () => {
    nockResponse();
    cy.visit(defaultUrl);
    cy.wait('@results');
    cy.get('a').contains(/Terms of Use/i);
  });

  it('should show loader', () => {
    nockResponse();
    cy.visit(defaultUrl);
    cy.wait('@results');
    cy.get('span').should('be.visible');
  });

  it('should show results page link copied toaster', () => {
    nockResponse();
    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('[data-testid=ShareIcon]').trigger('click');

    cy.get('div').contains(
      /link copied. We invite you to share it on Twitter, LinkedIn, Reddit, Facebook, and more!/i
    );
  });

  it('should render processing failed page elements', () => {
    nockResponse(processingFailedResponse);

    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.contains(/ooops!/i);
    cy.contains(
      /We encountered a problem while processing this repo. We're looking/i
    );
    cy.contains(
      /into it. To receive an update when we have a solution, please/i
    );
    cy.contains(/subscribe to our newsletter./i);

    cy.contains(/notify me/i);
  });

  it('should render footer links on processing failed page', () => {
    nockResponse(processingFailedResponse);

    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.get('a').contains(/Terms of Use/i);
  });

  it('should set title on successful response', () => {
    nockResponse();

    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.title().should(
      'eq',
      `Graph of ${DEFAULT_ACCOUNT_NAME}/${DEFAULT_REPO_NAME}, powered by Pants`
    );
  });

  it('should open and close example repos on processing failed page', () => {
    const email = 'random@random.com';
    nockResponse(processingFailedResponse);
    nockMailchimp('random%40random.com');

    cy.visit(defaultUrl);
    cy.wait('@results');

    cy.contains(/ooops!/i);

    cy.get('input').type(email);

    cy.get('span')
      .contains(/notify me/i)
      .click();

    cy.wait('@nockMailchimp');

    cy.contains(/see example repos/i);

    cy.get('span')
      .contains(/see example repos/i)
      .click();

    cy.contains(/example repos/i);

    cy.get('button')
      .contains(/go back/i)
      .click();

    cy.contains(/thank you!/i);
  });
});

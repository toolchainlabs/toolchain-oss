# Testing

When testing we follow the **AAA** testing standard. We **ARRANGE** a test environment (mocking requests, other mocks, and rendering the component as well as waiting for the UI to achieve the required state for testing), then we **ACT** on that environment (manipulate the UI and await for renders...) and finally we **ASSERT** the environment for desired behavior.

We use [jest](https://jestjs.io/) and [jsdom](https://github.com/jsdom/jsdom) as our environment for tests. [Nock](https://github.com/nock/nock) is used to mock requests and [react-testing-library](https://testing-library.com/docs/react-testing-library/intro/) is our framework of choice for testing components. We mostly do unit tests and integration tests (sometimes cross-testing with multiple components). We do have some snapshot tests, mostly for simple behavior or simple components. The test files are usually located next to the component/file that they test and are named in the same fashion as the component/file followed by `.test` and ended with the file extension (`.ts` or `.tsx`).

## Setup

The `/tests/` folder holds some setup files for testing as well as fixtures and mocks. The root folder of the app contains a `jest.config.json` file with configuration for jest. There is also a `jest-global-setup.js` file in the root folder for jest setup.

## Test file structure

The test files are usually structured like so:

```typescript
// copyright comment
// Imports
import React from 'react';

// Local vars
const someVar = 'someValue'

// Mocks
const mock = jest.fn();

const renderComponent = (url, queryParams, ...rest) => {
  // renders providers and stuff as well as the component we are testing
}

// lifecycle methods (beforeEach, afterEach...)
beforeEach(() => {
  // some setup
})

afterAll(() => {
  // Some cleanup
})

describe('componentName', () => {
  it(() => {
    // test
  })
})
```

## Rendering components

We have a `custom-render.tsx` (inside `/tests/`) wrapper around RTL's render function. This wrapper takes care of rendering providers mostly (some of them) so that we do not repeat this in our test suites.

## Mocking request data

We mock requests in tests using nock and fixtures located in the `test/__fixtures__` folder. The nocks are scoped in each test so that we ensure that all mocked requests have been fulfilled.

Here's an example:

```typescript
it('should test something...', async () => {
  // Arrange
  const scope = nock(TESTING_HOST)
    // all the requests that are nocked chained together
    .get(url)
    .query(queryParams)
    .delay(100)
    .reply(200, body, headers);

  render();

  // Act
  
  // Assert

  // Call done as to fail the test suite if anything from the scope has not been fulfilled
  scope.done();
});
```

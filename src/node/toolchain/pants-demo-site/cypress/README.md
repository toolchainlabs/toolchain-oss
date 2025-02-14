## Testing

Since we use [react-force-graph](https://github.com/vasturiano/react-force-graph) (specifically react-force-graph-2d) to render the dependecy graph, and JSDOM has low support for the canvas element, we do integration tests using [cypress](https://www.cypress.io/). This way when running tests we get atleast a visual representation of the dependecy graph. The tests are simple and can be found in `/home/npervic/projects/test/toolchain/src/node/toolchain/pants-demo-site/cypress/e2e/components`.


The `src/pages/builds` contains multiple pages/component related to builds and these are the core of our APP. The main ones being: 

1. `list.tsx` page implements the `table.tsx` component in the most complex way and displays as well as gives the users a way to filter through builds. 
2. `build-details.tsx` is a page that displays selected builds in more detail as well as artifacts for the same (test-results, formating results, linting results...).
3. `artifact.tsx` maps artifacts to components responsible for rendering a specific artifact `content/type` and fetches the data required for the same.

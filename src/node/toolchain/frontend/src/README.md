# General info

This file contains general information about the architecture of the SPA application.

## Server-side pages

Our spa is rendered without a login page. The login page is a Django template that has a GitHub auth button and simply sets a `refreshToken` and redirects to the SPA. The spa uses the `refreshToken` token to get a fresh one and an access token to consume the Buildsense API. Multiple pages are decoupled from the SPA in the same way. You can find them in `src/python/toolchain/users`.

## UI library

The SPA uses the [MaterialUI](https://mui.com/material-ui/getting-started/overview/) library to build the interface and [Emotion](https://emotion.sh/docs/introduction) for styling. You can find a `theme.ts` file inside `src/utils` that sets a [theme](https://mui.com/material-ui/customization/theming/) for MUI.

## Typings

The `src/common` folder contains reusable enums and types for our project.

## Fetching data

We use [@tanstack/react-query](https://tanstack.com/query/latest/docs/react/overview) for data fetching, data state management, caching, and more. We have custom hooks for handling HTTP requests in `src/utils/hooks/query.ts`.
among other things

## Utils

The utils folder contains hooks (`src/utils/hooks`) and higher order (`src/utils/hoc`) components as well as helper functions for API URL generation, reading BE configuration from the DOM on initial load, constants and fetching the access-token and more.


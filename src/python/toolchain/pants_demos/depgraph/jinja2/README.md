# Dep graph server side pages

This folder contains templates that make up our server side pages for the pants-demo-site (`src/node/toolchain/pants-demo-site`) SPA.

## Base templates

A base template used to render all other templates. This template loads our fonts and static files (`src/python/toolchain/pants_demos/depgraph/static`), as well as google analitics.

## Index template

This template is similar to base in a sense that it renders html tags in general, but uses no other templates but renders the bundle of our SPA (`src/node/toolchain/pants-demo-site`).

## 404 template

404 template that renders a "GO TO HOMEPAGE" button.

## Error template

Error template containg a button to go back in browser history. Loads an error.js script (`src/python/toolchain/pants_demos/depgraph/static/pants-demo-site/js/error.js`)

## Footer template

Footer template containg links to the pants and toolchain site and some copy. Contains a link to the terms page.

## Header template

Header template conting the toolchain logo and gradients that make up the sites background

## Repo selection template

A simple template that renders a popular and fixed repo selection list of preprocesed repos so that people can try out GraphMyRepo in an easy way. Loads the select-repo.js script (`src/python/toolchain/pants_demos/depgraph/static/pants-demo-site/js/select-repo.js`)

## Terms template

Terms and services explanation

## Images and css

These are housed in our static folder together with our JS scripts (`src/python/toolchain/pants_demos/depgraph/static`).

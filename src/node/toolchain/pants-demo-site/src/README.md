# General info

This file contains general information about the architecture of the pants-demo-site application.

## Server-side pages

The app is rendered on a specific page, side by side with server side Django pages found in `src/python/toolchain/pants_demos/depgraph/jinja2` The app handles processing repositories and displaying the depgraph.

## UI library

The SPA uses the [MaterialUI](https://mui.com/material-ui/getting-started/overview/) library to build the interface and [Emotion](https://emotion.sh/docs/introduction) for styling. You can find a `theme.ts` file inside `src` that sets a [theme](https://mui.com/material-ui/customization/theming/) for MUI.

## Fetching data

Since there is one call to the api only you can find a simple function that uses fetch inside `src/node/toolchain/pants-demo-site/src/api-calls`. The typings for the data we recieve from the API are in the same file.

## Models

Inside of the `src/node/toolchain/pants-demo-site/src/models` folder you can find classes that are used to build our dependecy graph which is the core of the app.

Heres some extra info about theses classes:

### Node

The node classes (Node, LeafNode and RollupNode) are class representations of the nodes that we display in the graph. Leaf node are end nodes of a currently selected node. Rollup nodes are nodes that can be collapsed or expanded.

### Node set

The node set class represents a set of above mentioned nodes and has simple methods for adding getting deleting... A part from that we set the way these sets are iterated as well as a comparsion method (isEqualTo) to compare to other nodes.

### Hierarchical digraph 

The HierarchicalDigraph is the representation of nodes as a graph. It contains methods for easy counting of leaf types finding descendants, finding children (trivial or not) and getting node edges.

### Visible graph

The Visible graph class leverages the Hierarchical digraph to display nodes using the react-force-2d library. It contains methods to collapse or expand nodes and methods to check the visibility of nodes.

## Redux toolkit store

We use [reduxjs/toolkit](https://redux-toolkit.js.org/usage/usage-guide) to store the information about the graph and its class instances. The slices mostly contain data stored that is needed in more than one components such as zoom level of the graph, the current node adress, global types and the graphs themself (hierarchical and visible) class instances.

## Components

The `src/node/toolchain/pants-demo-site/src/components` folder is mostly components that make up our UI. The UI is made up of functional components that use Emotion for styling and MUI as a building block wherever possible. The `<Results />` component is our main component rendering the form to process a repo, different state of processing (loading, processed, processing failed) and the graph itself. Other critical components that make up displaying our graph are the target description that renders information about the currently selected target and file-system which renders the tree view users can browse collaps and expand nodes or search using an input. Some of these contain unit tests but most are covered using cypress and browser testing.
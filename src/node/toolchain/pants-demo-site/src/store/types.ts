/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import VisibleGraph from '../models/visible-graph';
import HierarchicalDigraph from '../models/hierarchical-digraph';

export type GlobalState = {
  visibleGraph: VG;
  hierarchicalDigraph: HD;
  node: Node;
  graphZoom: GraphZoom;
  globalTypes: GlobalTypes;
};

export type NodeAdress = string | undefined;

export type Node = {
  selectedNode: NodeAdress;
  focusedNode: NodeAdress;
  hoveredNode: NodeAdress;
};

export type VG = {
  graph: VisibleGraph | undefined;
};

export type HD = {
  graph: HierarchicalDigraph | undefined;
};

export type GraphZoom = {
  level: number;
};

export type TypesMap = Map<string, number>;

export type GlobalTypes = {
  map: TypesMap | undefined;
};

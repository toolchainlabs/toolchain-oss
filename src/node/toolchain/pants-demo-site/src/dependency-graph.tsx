/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState, useEffect, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { styled } from '@mui/material/styles';
import { useSelector, useDispatch } from 'react-redux';

import { convertEdges, convertNodes } from './data-structure-utils';
import { GlobalState, NodeAdress } from './store/types';
import { nodeFocused, nodeHovered, nodeSelected } from './store/nodeSlice';
import { visibleGraphExpanded } from './store/visibleGraphSlice';
import { graphZoomLevelSet } from './store/graphZoomSlice';
import OnGraphControls from './components/on-graph-controls';
import { sep } from './models/utils';
import {
  NodeColors,
  getNodeColor,
  paintCircle,
  paintRoundRectange,
  paintText,
} from './paint-node-utils';

export type GraphInputNodesType = Array<{
  id: string;
}>;

export type GraphInputLinksType = Array<LinkType>;

export type GraphDataType = {
  nodes: GraphInputNodesType;
  links: GraphInputLinksType;
};

type DependencyGraphType = {
  canvasWidth: number;
  canvasHeight: number;
};

type PaintNodeInfoType = {
  address: string;
  nodeType: string;
  x: number;
  y: number;
};

export type LinkType = {
  source: {
    id: string;
  };
  target: {
    id: string;
  };
};

const GraphWrapper = styled('div')(() => ({
  position: 'relative',
  width: '100%',
}));

const DependencyGraph = ({
  canvasWidth,
  canvasHeight,
}: DependencyGraphType) => {
  const [graphData, setGraphData] = useState<GraphDataType>();

  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const vg = useSelector((state: GlobalState) => state.visibleGraph.graph);

  const selectedNode: NodeAdress = useSelector(
    (state: GlobalState) => state.node.selectedNode
  );

  const hoveredNode: NodeAdress = useSelector(
    (state: GlobalState) => state.node.hoveredNode
  );

  const converetedGraphData = useMemo(() => {
    return {
      nodes: graphData?.nodes || [],
      links:
        graphData?.links.map(link => ({
          source: link.source.id,
          target: link.target.id,
        })) || [],
    };
  }, [graphData]);

  const zoomLevel = useSelector((state: GlobalState) => state.graphZoom.level);

  const isSelectedNodeVisible =
    selectedNode && graphData?.nodes.some(node => node.id === selectedNode);

  const graphRef = useRef();

  useEffect(() => {
    setGraphData({
      nodes: vg ? convertNodes(vg.visibleNodes) : [],
      links: vg ? convertEdges(vg.visibleEdges) : [],
    });
  }, [vg, convertNodes, convertEdges]);

  useEffect(() => {
    // eslint-disable-next-line  @typescript-eslint/no-explicit-any
    (graphRef.current as any)?.zoom(zoomLevel);
  }, [graphRef, zoomLevel]);

  const dispatch = useDispatch();

  const onNodeClick = (address: string | number | undefined) => {
    const convertedAddress = address?.toString() || '';
    if (convertedAddress === selectedNode) {
      dispatch(visibleGraphExpanded(convertedAddress));
    } else {
      dispatch(nodeSelected(convertedAddress));
    }
    dispatch(nodeFocused(convertedAddress));
  };

  const onNodeHover = (address: string | number | undefined) => {
    const convertedAddress = address?.toString() || '';

    dispatch(nodeHovered(convertedAddress));
  };

  const onBackgroundClickHandler = () => {
    if (selectedNode) {
      dispatch(nodeSelected(''));
    }
  };

  const paintNode = (
    { address, nodeType, x, y }: PaintNodeInfoType,
    // eslint-disable-next-line  @typescript-eslint/no-explicit-any
    ctx: any,
    globalScale: number
  ) => {
    //NODE SHAPE PAINT

    const isHighlighted = address === selectedNode || address === hoveredNode;

    let isVisible = false;

    if (!isSelectedNodeVisible) {
      isVisible = true;
    } else if (!graphData?.links) {
      isVisible = isHighlighted;
    } else {
      isVisible =
        isHighlighted ||
        graphData?.links.some(
          link =>
            (link.source.id === selectedNode && link.target.id === address) ||
            (link.source.id === address && link.target.id === selectedNode)
        );
    }

    const calcNodeType = nodeType || NodeColors.rollup;

    const myColor = getNodeColor(calcNodeType);
    const myRadius = 4;

    if (calcNodeType !== NodeColors.rollup) {
      paintCircle(
        ctx,
        x,
        y,
        myRadius,
        myColor,
        isHighlighted,
        globalScale,
        isVisible
      );
    } else {
      const borderRadius = 4;
      const rectandgleSize = 14;
      paintRoundRectange(
        ctx,
        x,
        y,
        borderRadius,
        rectandgleSize,
        myColor,
        isHighlighted,
        globalScale,
        isVisible
      );
    }

    //

    //TEXT PAINT
    const splittedAddress = address.split(sep);
    const lastIndex = splittedAddress.length - 1;
    const displayName = splittedAddress[lastIndex];

    paintText(ctx, x, y, globalScale, isHighlighted, isVisible, displayName);

    return null;
  };

  const findNode = (address: string) => {
    return hd?.allRolledUpNodes.get(address);
  };

  const getNodeVal = (address: string | number | undefined) => {
    const convertedAddress = address?.toString() || '';
    const node = findNode(convertedAddress);

    return node?.isLeaf() ? 2 : 4;
  };

  const getLinkWidth = (link: LinkType) => {
    if (link.source.id === selectedNode || link.target.id === selectedNode) {
      return 1.2;
    }

    return 1;
  };

  const getLinkColor = (link: LinkType) => {
    if (!isSelectedNodeVisible) {
      return 'rgba(0, 0, 0, 0.3)';
    }

    if (link.source.id === selectedNode || link.target.id === selectedNode) {
      return 'rgba(0, 0, 0, 0.8)';
    }

    return 'rgba(0, 0, 0, 0.1)';
  };

  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  const renderNode = (node: any, ctx: any, globalScale: number) => {
    const myNode = findNode(node.id);
    const fullNode = {
      x: node.x,
      y: node.y,
      ...myNode,
    } as PaintNodeInfoType;

    return paintNode(fullNode, ctx, globalScale);
  };

  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  const onZoomHandler = (e: any) => {
    dispatch(graphZoomLevelSet(e.k));
  };

  return (
    <GraphWrapper>
      <ForceGraph2D
        ref={graphRef}
        width={canvasWidth}
        height={canvasHeight}
        graphData={converetedGraphData}
        onNodeClick={node => onNodeClick(node.id)}
        onNodeHover={node => onNodeHover(node?.id)}
        nodeLabel={'id'}
        linkDirectionalArrowLength={2}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.5}
        linkWidth={link => getLinkWidth(link as LinkType)}
        linkColor={link => getLinkColor(link as LinkType)}
        enableNodeDrag={false}
        backgroundColor="#fff"
        nodeCanvasObjectMode={() => 'replace'}
        nodeVal={node => getNodeVal(node.id)}
        nodeCanvasObject={(node, ctx, gs) => renderNode(node, ctx, gs)}
        onBackgroundClick={onBackgroundClickHandler}
        onZoom={onZoomHandler}
      />
      <OnGraphControls />
    </GraphWrapper>
  );
};

export default DependencyGraph;

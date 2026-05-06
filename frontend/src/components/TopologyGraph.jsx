import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

export function TopologyGraph({ data, selectedId, onSelect }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!data.nodes?.length || !svgRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    svg.selectAll('*').remove();

    const g = svg.append('g');

    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const nodeCount = data.nodes.length;
    // Scale forces based on graph density to prevent large graphs from exploding
    const chargeStrength = Math.min(-150, Math.max(-800, -800 + (nodeCount * 15)));
    const linkDistance = Math.max(60, 180 - (nodeCount * 3));
    const collisionRadius = Math.max(35, 80 - nodeCount);

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.edges || []).id(d => d.id).distance(linkDistance))
      .force('charge', d3.forceManyBody().strength(chargeStrength))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(collisionRadius))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.05));

    // Compute node degrees to dynamically scale them or highlight hubs
    const degrees = {};
    (data.edges || []).forEach(e => {
      const s = typeof e.source === 'object' ? e.source.id : e.source;
      const t = typeof e.target === 'object' ? e.target.id : e.target;
      degrees[s] = (degrees[s] || 0) + 1;
      degrees[t] = (degrees[t] || 0) + 1;
    });

    const link = g.append('g')
      .selectAll('line')
      .data(data.edges || [])
      .join('line')
      .attr('stroke', d => d.type === 'causal' ? '#E7C59A' : '#333333')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => d.type === 'causal' ? 2 : 1)
      .attr('stroke-dasharray', d => d.type === 'causal' ? '0' : '4 4');

    const node = g.append('g')
      .selectAll('.node')
      .data(data.nodes)
      .join('g')
      .attr('class', 'cursor-pointer')
      .on('click', (e, d) => onSelect(d.id))
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Glow filter for critical nodes
    const defs = svg.append("defs");
    
    // Create soft radial gradients for premium feel
    const createGradient = (id, color1, color2) => {
      const grad = defs.append("radialGradient").attr("id", id).attr("cx", "30%").attr("cy", "30%");
      grad.append("stop").attr("offset", "0%").attr("stop-color", color1);
      grad.append("stop").attr("offset", "100%").attr("stop-color", color2);
    };
    createGradient("gradPod", "#2a2e38", "#121317");
    createGradient("gradSvc", "#382e20", "#17130b");
    createGradient("gradPvc", "#20382a", "#0b1712");
    createGradient("gradNs", "#333333", "#111111");

    const filter = defs.append("filter").attr("id", "glow").attr("x", "-20%").attr("y", "-20%").attr("width", "140%").attr("height", "140%");
    filter.append("feGaussianBlur").attr("stdDeviation", "8").attr("result", "coloredBlur");
    const feMerge = filter.append("feMerge");
    feMerge.append("feMergeNode").attr("in", "coloredBlur");
    feMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Main Circle
    node.append('circle')
      .attr('r', 24)
      .attr('fill', d => {
        if (d.kind === 'service') return 'url(#gradSvc)';
        if (d.kind === 'pod') return 'url(#gradPod)';
        if (d.kind === 'pvc') return 'url(#gradPvc)';
        return 'url(#gradNs)';
      })
      .attr('stroke', d => d.status === 'CRITICAL' ? '#ff4d4d' : d.id === selectedId ? '#F3F3F3' : '#333333')
      .attr('stroke-width', d => d.id === selectedId || d.status === 'CRITICAL' ? 2 : 1)
      .attr('filter', d => d.status === 'CRITICAL' || d.id === selectedId ? 'url(#glow)' : null);

    // Inner icon (letter)
    node.append('text')
      .attr('y', 5)
      .attr('text-anchor', 'middle')
      .attr('fill', d => {
        if (d.kind === 'service') return '#E7C59A';
        if (d.kind === 'pvc') return '#00AC5C';
        if (d.kind === 'namespace') return '#F3F3F3';
        return '#949494';
      })
      .attr('font-size', '14px')
      .attr('font-weight', '900')
      .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
      .text(d => d.kind ? d.kind.charAt(0).toUpperCase() : '');

    // Outer Label
    node.append('text')
      .attr('y', 42)
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.id === selectedId ? '#F3F3F3' : '#949494')
      .attr('font-size', '12px')
      .attr('font-weight', '600')
      .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
      .attr('class', 'pointer-events-none')
      .text(d => {
        // truncate extremely long labels
        return d.label && d.label.length > 20 ? d.label.substring(0, 18) + '...' : d.label;
      });

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => simulation.stop();
  }, [data, selectedId]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}

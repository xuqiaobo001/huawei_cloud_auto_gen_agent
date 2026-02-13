/**
 * 华为云服务依赖图 - D3.js 力导向图可视化
 */
(function () {
    'use strict';

    // ===== 颜色映射 =====
    const CATEGORY_COLORS = {
        compute:    '#0d6efd',
        network:    '#0dcaf0',
        storage:    '#fd7e14',
        database:   '#6f42c1',
        security:   '#dc3545',
        monitoring: '#198754',
        container:  '#20c997',
        middleware: '#d63384',
        application:'#ffc107',
        ai:         '#6610f2',
        big_data:   '#0b5ed7',
        media:      '#e83e8c',
        migration:  '#6c757d',
        management: '#495057',
    };

    const CATEGORY_LABELS = {
        compute: '计算', network: '网络', storage: '存储', database: '数据库',
        security: '安全', monitoring: '监控', container: '容器', middleware: '中间件',
        application: '应用', ai: 'AI', big_data: '大数据', media: '媒体',
        migration: '迁移', management: '管理',
    };

    const DEP_STYLES = {
        requires:   { color: '#0d6efd', dash: null,      width: 1.8 },
        optional:   { color: '#6c757d', dash: '6,3',     width: 1.2 },
        monitors:   { color: '#198754', dash: null,       width: 1.4 },
        integrates: { color: '#6f42c1', dash: '2,3',     width: 1.4 },
    };

    // ===== 状态 =====
    let graphData = { nodes: [], edges: [] };
    let simulation, svgGroup, linkGroup, nodeGroup;
    let zoom;
    let activeCategories = new Set();
    let selectedNode = null;

    // ===== 初始化 =====
    async function init() {
        await loadData();
        setupSVG();
        renderGraph();
        setupControls();
        updateStats();
    }

    async function loadData() {
        try {
            const resp = await fetch('/api/graph/services');
            const json = await resp.json();
            if (json.success) {
                graphData = json.data;
            }
        } catch (e) {
            console.error('加载图数据失败:', e);
        }
    }

    // ===== SVG 设置 =====
    function setupSVG() {
        const svg = d3.select('#graph-svg');
        const width = svg.node().clientWidth;
        const height = svg.node().clientHeight;

        // 箭头标记
        const defs = svg.append('defs');
        Object.entries(DEP_STYLES).forEach(([type, style]) => {
            defs.append('marker')
                .attr('id', 'arrow-' + type)
                .attr('viewBox', '0 -4 8 8')
                .attr('refX', 20)
                .attr('refY', 0)
                .attr('markerWidth', 6)
                .attr('markerHeight', 6)
                .attr('orient', 'auto')
                .append('path')
                .attr('d', 'M0,-4L8,0L0,4')
                .attr('fill', style.color)
                .attr('opacity', 0.6);
        });

        zoom = d3.zoom()
            .scaleExtent([0.2, 4])
            .on('zoom', (event) => {
                svgGroup.attr('transform', event.transform);
            });

        svg.call(zoom);

        svgGroup = svg.append('g');
        linkGroup = svgGroup.append('g').attr('class', 'links');
        nodeGroup = svgGroup.append('g').attr('class', 'nodes');

        // 初始居中
        svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85));
    }

    // ===== 渲染图 =====
    function renderGraph() {
        const svg = d3.select('#graph-svg');
        const width = svg.node().clientWidth;
        const height = svg.node().clientHeight;

        // 计算入度用于节点大小
        const inDegree = {};
        graphData.edges.forEach(e => {
            inDegree[e.target] = (inDegree[e.target] || 0) + 1;
        });

        const nodes = graphData.nodes.map(n => ({
            ...n,
            radius: Math.max(8, Math.min(22, 8 + (inDegree[n.id] || 0) * 1.5)),
        }));

        const nodeMap = {};
        nodes.forEach(n => nodeMap[n.id] = n);

        const edges = graphData.edges
            .filter(e => nodeMap[e.source] && nodeMap[e.target])
            .map(e => ({ ...e }));

        // 收集类别
        const categories = new Set(nodes.map(n => n.category));
        activeCategories = new Set(categories);
        buildCategoryFilter(categories);
        buildCategoryLegend(categories);

        // 力仿真
        simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges).id(d => d.id).distance(120))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(0, 0))
            .force('collision', d3.forceCollide().radius(d => d.radius + 6))
            .force('x', d3.forceX(0).strength(0.04))
            .force('y', d3.forceY(0).strength(0.04));

        // 边
        const links = linkGroup.selectAll('line')
            .data(edges)
            .join('line')
            .attr('stroke', d => (DEP_STYLES[d.type] || DEP_STYLES.optional).color)
            .attr('stroke-width', d => (DEP_STYLES[d.type] || DEP_STYLES.optional).width)
            .attr('stroke-dasharray', d => (DEP_STYLES[d.type] || DEP_STYLES.optional).dash)
            .attr('stroke-opacity', 0.5)
            .attr('marker-end', d => 'url(#arrow-' + d.type + ')');

        // 节点组
        const nodeGs = nodeGroup.selectAll('g.node')
            .data(nodes)
            .join('g')
            .attr('class', 'node')
            .style('cursor', 'pointer')
            .call(d3.drag()
                .on('start', dragStarted)
                .on('drag', dragged)
                .on('end', dragEnded));

        // 节点圆
        nodeGs.append('circle')
            .attr('r', d => d.radius)
            .attr('fill', d => CATEGORY_COLORS[d.category] || '#999')
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .attr('opacity', 0.9);

        // 节点标签
        nodeGs.append('text')
            .text(d => d.short)
            .attr('text-anchor', 'middle')
            .attr('dy', d => d.radius + 14)
            .attr('font-size', '10px')
            .attr('fill', '#333')
            .attr('pointer-events', 'none');

        // 交互
        nodeGs.on('mouseover', function (event, d) {
            showTooltip(event, d.label + ' (' + d.short + ')');
            highlightConnected(d, nodes, edges, links, nodeGs);
        }).on('mouseout', function () {
            hideTooltip();
            resetHighlight(links, nodeGs);
        }).on('click', function (event, d) {
            event.stopPropagation();
            selectNode(d);
        });

        // 点击空白取消选中
        d3.select('#graph-svg').on('click', () => {
            deselectNode();
        });

        // tick
        simulation.on('tick', () => {
            links
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            nodeGs.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // 存储引用
        window._graphRefs = { nodes, edges, links, nodeGs, nodeMap };
    }

    // ===== 拖拽 =====
    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    // ===== 高亮 =====
    function highlightConnected(d, nodes, edges, links, nodeGs) {
        const connected = new Set();
        connected.add(d.id);
        edges.forEach(e => {
            const src = typeof e.source === 'object' ? e.source.id : e.source;
            const tgt = typeof e.target === 'object' ? e.target.id : e.target;
            if (src === d.id) connected.add(tgt);
            if (tgt === d.id) connected.add(src);
        });

        nodeGs.select('circle').attr('opacity', n => connected.has(n.id) ? 1 : 0.15);
        nodeGs.select('text').attr('opacity', n => connected.has(n.id) ? 1 : 0.15);
        links.attr('stroke-opacity', e => {
            const src = typeof e.source === 'object' ? e.source.id : e.source;
            const tgt = typeof e.target === 'object' ? e.target.id : e.target;
            return (src === d.id || tgt === d.id) ? 0.8 : 0.05;
        });
    }

    function resetHighlight(links, nodeGs) {
        if (selectedNode) return; // 选中状态不重置
        nodeGs.select('circle').attr('opacity', 0.9);
        nodeGs.select('text').attr('opacity', 1);
        links.attr('stroke-opacity', 0.5);
    }

    // ===== Tooltip =====
    function showTooltip(event, text) {
        const tip = document.getElementById('node-tooltip');
        tip.textContent = text;
        tip.style.display = 'block';
        tip.style.left = (event.pageX + 12) + 'px';
        tip.style.top = (event.pageY - 28) + 'px';
    }
    function hideTooltip() {
        document.getElementById('node-tooltip').style.display = 'none';
    }

    // ===== 节点选中 & 详情面板 =====
    async function selectNode(d) {
        selectedNode = d;
        const panel = document.getElementById('detail-panel');
        panel.style.display = 'block';

        const color = CATEGORY_COLORS[d.category] || '#999';
        document.getElementById('detail-icon').style.background = color;
        document.getElementById('detail-icon').textContent = d.short;
        document.getElementById('detail-name').textContent = d.label;
        document.getElementById('detail-category').textContent = CATEGORY_LABELS[d.category] || d.category;
        document.getElementById('detail-id').textContent = 'ID: ' + d.id;

        // 加载依赖详情
        try {
            const resp = await fetch('/api/graph/service/' + d.id + '/dependencies');
            const json = await resp.json();
            if (json.success) {
                renderDepList('dep-on-list', 'dep-on-count', json.data.depends_on || []);
                renderDepList('dep-by-list', 'dep-by-count', json.data.depended_by || []);
            }
        } catch (e) {
            console.error('加载依赖详情失败:', e);
        }

        // 高亮
        const refs = window._graphRefs;
        if (refs) {
            highlightConnected(d, refs.nodes, refs.edges, refs.links, refs.nodeGs);
        }
    }

    function deselectNode() {
        selectedNode = null;
        document.getElementById('detail-panel').style.display = 'none';
        const refs = window._graphRefs;
        if (refs) {
            resetHighlightForce(refs.links, refs.nodeGs);
        }
    }

    function resetHighlightForce(links, nodeGs) {
        selectedNode = null;
        nodeGs.select('circle').attr('opacity', 0.9);
        nodeGs.select('text').attr('opacity', 1);
        links.attr('stroke-opacity', 0.5);
    }

    function renderDepList(listId, countId, items) {
        const ul = document.getElementById(listId);
        document.getElementById(countId).textContent = items.length;
        ul.innerHTML = '';
        items.forEach(item => {
            const li = document.createElement('li');
            const typeStyle = DEP_STYLES[item.type] || DEP_STYLES.optional;
            li.innerHTML = `
                <span class="dep-badge" style="background:${typeStyle.color}">${item.type}</span>
                <span style="font-weight:600">${item.short || item.service}</span>
                <span style="color:#888;font-size:0.7rem;flex:1">${item.label}</span>
            `;
            li.title = item.description || '';
            li.addEventListener('click', () => {
                // 点击跳转到该节点
                const refs = window._graphRefs;
                if (refs && refs.nodeMap[item.service]) {
                    const node = refs.nodeMap[item.service];
                    selectNode(node);
                    // 平移到该节点
                    const svg = d3.select('#graph-svg');
                    const t = d3.zoomTransform(svg.node());
                    svg.transition().duration(500).call(
                        zoom.transform,
                        d3.zoomIdentity.translate(
                            svg.node().clientWidth / 2 - node.x * t.k,
                            svg.node().clientHeight / 2 - node.y * t.k
                        ).scale(t.k)
                    );
                }
            });
            ul.appendChild(li);
        });
    }

    // ===== 类别筛选 =====
    function buildCategoryFilter(categories) {
        const container = document.getElementById('category-filter');
        container.innerHTML = '';

        // 全选按钮
        const allBtn = document.createElement('span');
        allBtn.className = 'cat-btn active';
        allBtn.style.background = '#333';
        allBtn.style.color = '#fff';
        allBtn.textContent = '全部';
        allBtn.addEventListener('click', () => {
            activeCategories = new Set(categories);
            applyFilter();
            container.querySelectorAll('.cat-btn').forEach(b => b.classList.add('active'));
        });
        container.appendChild(allBtn);

        categories.forEach(cat => {
            const btn = document.createElement('span');
            btn.className = 'cat-btn active';
            btn.style.background = CATEGORY_COLORS[cat] || '#999';
            btn.textContent = CATEGORY_LABELS[cat] || cat;
            btn.dataset.category = cat;
            btn.addEventListener('click', () => {
                if (activeCategories.has(cat)) {
                    activeCategories.delete(cat);
                    btn.classList.remove('active');
                    btn.style.background = '#fff';
                    btn.style.color = '#333';
                } else {
                    activeCategories.add(cat);
                    btn.classList.add('active');
                    btn.style.background = CATEGORY_COLORS[cat] || '#999';
                    btn.style.color = '#fff';
                }
                applyFilter();
            });
            container.appendChild(btn);
        });
    }

    function buildCategoryLegend(categories) {
        const container = document.getElementById('category-legend');
        container.innerHTML = '';
        categories.forEach(cat => {
            const div = document.createElement('div');
            div.className = 'legend-item';
            div.innerHTML = `<span class="legend-dot" style="background:${CATEGORY_COLORS[cat] || '#999'}"></span> ${CATEGORY_LABELS[cat] || cat}`;
            container.appendChild(div);
        });
    }

    function applyFilter() {
        const refs = window._graphRefs;
        if (!refs) return;

        refs.nodeGs.style('display', d => activeCategories.has(d.category) ? null : 'none');
        refs.links.style('display', d => {
            const src = typeof d.source === 'object' ? d.source : refs.nodeMap[d.source];
            const tgt = typeof d.target === 'object' ? d.target : refs.nodeMap[d.target];
            return (src && tgt && activeCategories.has(src.category) && activeCategories.has(tgt.category)) ? null : 'none';
        });
    }

    // ===== 搜索 =====
    function setupSearch() {
        const input = document.getElementById('search-input');
        input.addEventListener('input', () => {
            const q = input.value.trim().toLowerCase();
            const refs = window._graphRefs;
            if (!refs) return;

            if (!q) {
                refs.nodeGs.select('circle').attr('opacity', 0.9);
                refs.nodeGs.select('text').attr('opacity', 1);
                refs.links.attr('stroke-opacity', 0.5);
                return;
            }

            const matched = new Set();
            refs.nodes.forEach(n => {
                if (n.id.includes(q) || n.label.includes(q) || n.short.toLowerCase().includes(q)) {
                    matched.add(n.id);
                }
            });

            refs.nodeGs.select('circle').attr('opacity', n => matched.has(n.id) ? 1 : 0.1);
            refs.nodeGs.select('text').attr('opacity', n => matched.has(n.id) ? 1 : 0.1);
            refs.links.attr('stroke-opacity', 0.05);
        });
    }

    // ===== 控制按钮 =====
    function setupControls() {
        const svg = d3.select('#graph-svg');

        document.getElementById('btn-zoom-in').addEventListener('click', () => {
            svg.transition().duration(300).call(zoom.scaleBy, 1.3);
        });
        document.getElementById('btn-zoom-out').addEventListener('click', () => {
            svg.transition().duration(300).call(zoom.scaleBy, 0.7);
        });
        document.getElementById('btn-zoom-reset').addEventListener('click', () => {
            const w = svg.node().clientWidth;
            const h = svg.node().clientHeight;
            svg.transition().duration(500).call(
                zoom.transform,
                d3.zoomIdentity.translate(w / 2, h / 2).scale(0.85)
            );
        });

        document.getElementById('detail-close').addEventListener('click', deselectNode);

        document.getElementById('btn-refresh').addEventListener('click', async () => {
            const btn = document.getElementById('btn-refresh');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 刷新中...';
            try {
                await fetch('/api/graph/refresh', { method: 'POST' });
                await loadData();
                // 清除旧图重新渲染
                linkGroup.selectAll('*').remove();
                nodeGroup.selectAll('*').remove();
                if (simulation) simulation.stop();
                renderGraph();
                updateStats();
                deselectNode();
            } catch (e) {
                console.error('刷新失败:', e);
            }
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> 刷新数据';
        });

        setupSearch();
    }

    // ===== 统计 =====
    function updateStats() {
        document.getElementById('stat-nodes').textContent = graphData.nodes.length;
        document.getElementById('stat-edges').textContent = graphData.edges.length;
        const cats = new Set(graphData.nodes.map(n => n.category));
        document.getElementById('stat-categories').textContent = cats.size;
    }

    // ===== 启动 =====
    document.addEventListener('DOMContentLoaded', init);
})();

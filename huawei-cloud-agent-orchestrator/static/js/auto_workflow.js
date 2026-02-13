// AI工作流自动生成功能

let currentWorkflow = null;
let isGenerating = false;

// ===== 流程图拖拽状态 =====
var flowState = null;  // 存储当前图形的全部状态，供拖拽时重绘使用

// 拖拽引擎：为节点绑定拖拽事件
function enableNodeDrag(node, idx) {
    var dragging = false;
    var offsetX = 0, offsetY = 0;

    node.style.cursor = 'grab';

    node.addEventListener('mousedown', function(e) {
        if (!flowState) return;
        e.preventDefault();
        dragging = true;
        node.style.cursor = 'grabbing';
        node.style.zIndex = '10';
        var rect = flowState.canvas.getBoundingClientRect();
        offsetX = e.clientX - node.offsetLeft;
        offsetY = e.clientY - node.offsetTop;

        function onMove(ev) {
            if (!dragging) return;
            var nx = ev.clientX - offsetX;
            var ny = ev.clientY - offsetY;
            // 限制在画布范围内
            nx = Math.max(0, nx);
            ny = Math.max(0, ny);

            node.style.left = nx + 'px';
            node.style.top = ny + 'px';

            // 更新 pos
            var p = flowState.pos[idx];
            var w = flowState.nodeW, h = flowState.nodeH;
            p.x = nx; p.y = ny;
            p.cx = nx + w / 2;
            p.cy = ny + h / 2;
            p.top = ny;
            p.bottom = ny + h;
            p.left = nx;
            p.right = nx + w;

            redrawAllLines();
        }

        function onUp() {
            dragging = false;
            node.style.cursor = 'grab';
            node.style.zIndex = '2';
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });
}

// 为 Start/End 标记绑定拖拽
function enableMarkerDrag(markerDiv, markerKey) {
    var dragging = false;
    var offsetX = 0, offsetY = 0;

    markerDiv.style.cursor = 'grab';

    markerDiv.addEventListener('mousedown', function(e) {
        if (!flowState) return;
        e.preventDefault();
        dragging = true;
        markerDiv.style.cursor = 'grabbing';

        offsetX = e.clientX - markerDiv.offsetLeft;
        offsetY = e.clientY - markerDiv.offsetTop;

        function onMove(ev) {
            if (!dragging) return;
            var nx = Math.max(0, ev.clientX - offsetX);
            var ny = Math.max(0, ev.clientY - offsetY);
            markerDiv.style.left = nx + 'px';
            markerDiv.style.top = ny + 'px';

            var mw = flowState.markerW, mh = flowState.markerH;
            if (markerKey === 'start') {
                flowState.startCx = nx + mw / 2;
                flowState.startBottom = ny + mh;
            } else {
                flowState.endCx = nx + mw / 2;
                flowState.endTop = ny;
            }
            redrawAllLines();
        }

        function onUp() {
            dragging = false;
            markerDiv.style.cursor = 'grab';
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI工作流生成器已加载');

    // 绑定快速示例选择
    document.getElementById('quickExamples').addEventListener('change', loadExample);

    // 支持Ctrl+Enter快速生成
    document.getElementById('requirementInput').addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            generateWorkflow();
        }
    });

    // 从首页带过来的需求：自动填入并生成
    var saved = localStorage.getItem('autoRequirement');
    if (saved) {
        localStorage.removeItem('autoRequirement');
        document.getElementById('requirementInput').value = saved;
        generateWorkflow();
    }
});

// 加载示例
function loadExample() {
    const select = document.getElementById('quickExamples');
    const requirement = select.value;

    if (requirement) {
        document.getElementById('requirementInput').value = requirement;
        generateWorkflow();
    }
}

// 生成工作流
async function generateWorkflow() {
    const requirementInput = document.getElementById('requirementInput');
    const requirement = requirementInput.value.trim();

    if (!requirement) {
        showError('请输入部署需求');
        return;
    }

    if (isGenerating) {
        return;
    }

    isGenerating = true;
    showLoading(true);
    hideError();

    try {
        const autoExecute = document.getElementById('autoExecute').checked;
        const explainWorkflow = document.getElementById('explainWorkflow').checked;

        const response = await fetch('/api/auto/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                requirement: requirement,
                auto_execute: autoExecute,
                generate_explanation: explainWorkflow
            })
        });

        const result = await response.json();

        if (result.success) {
            currentWorkflow = result.workflow;
            displayWorkflow(currentWorkflow);

            if (result.explanation) {
                displayExplanation(result.explanation);
            }

            if (autoExecute && result.execution) {
                displayExecutionResult(result.execution);
            }

            showSuccess('工作流生成成功！');
        } else {
            showError(result.error || '生成失败');
        }

    } catch (error) {
        console.error('生成工作流失败:', error);
        showError('网络错误，请稍后重试: ' + error.message);
    } finally {
        showLoading(false);
        isGenerating = false;
    }
}

// 显示生成的工作流 — 流程图模式
function displayWorkflow(workflow) {
    document.getElementById('emptyState').classList.add('d-none');
    document.getElementById('workflowContainer').classList.remove('d-none');

    document.getElementById('workflowName').textContent = workflow.name || '未命名工作流';
    document.getElementById('workflowDescription').textContent = workflow.description || '无描述';

    var badge = document.getElementById('taskCountBadge');
    if (badge) {
        badge.textContent = workflow.tasks.length + ' 个任务';
        badge.classList.remove('d-none');
    }

    renderFlowDiagram(workflow);
}

// ===== 流程图渲染引擎 =====

// HTML转义
function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// 拓扑分层：按依赖深度将任务分配到不同层
function topoLayers(tasks) {
    var nameMap = {};
    tasks.forEach(function(t, i) { nameMap[t.name] = i; });

    // 计算每个任务的深度
    var depth = new Array(tasks.length).fill(-1);
    function getDepth(idx) {
        if (depth[idx] >= 0) return depth[idx];
        var t = tasks[idx];
        var deps = (t.depends_on || []).filter(function(d) { return nameMap[d] !== undefined; });
        if (deps.length === 0) { depth[idx] = 0; return 0; }
        var maxD = 0;
        deps.forEach(function(d) {
            var dd = getDepth(nameMap[d]);
            if (dd > maxD) maxD = dd;
        });
        depth[idx] = maxD + 1;
        return depth[idx];
    }
    tasks.forEach(function(_, i) { getDepth(i); });

    // 按深度分组
    var maxDepth = 0;
    depth.forEach(function(d) { if (d > maxDepth) maxDepth = d; });
    var layers = [];
    for (var l = 0; l <= maxDepth; l++) layers.push([]);
    tasks.forEach(function(t, i) { layers[depth[i]].push(i); });

    return { layers: layers, depth: depth, nameMap: nameMap };
}

// 主渲染函数：流程图
function renderFlowDiagram(workflow) {
    var canvas = document.getElementById('flowCanvas');
    canvas.innerHTML = '';

    var tasks = workflow.tasks || [];
    if (tasks.length === 0) {
        canvas.innerHTML = '<div class="text-center text-muted py-4">无任务</div>';
        return;
    }

    var topo = topoLayers(tasks);
    var layers = topo.layers;
    var nameMap = topo.nameMap;

    // 布局参数
    var nodeW = 210, nodeH = 110;
    var gapX = 60, gapY = 50;
    var padLeft = 50, padTop = 50;
    var markerH = 36, markerW = 72;

    // 计算每层最大宽度，确定画布尺寸
    var maxNodesInLayer = 1;
    layers.forEach(function(l) { if (l.length > maxNodesInLayer) maxNodesInLayer = l.length; });

    var totalW = padLeft * 2 + maxNodesInLayer * nodeW + (maxNodesInLayer - 1) * gapX;
    var totalH = padTop + markerH + gapY + layers.length * (nodeH + gapY) + markerH + gapY;

    // 尺寸设在 flowCanvas 上，外层 wrapper 负责滚动约束
    canvas.style.width = Math.max(totalW, 400) + 'px';
    canvas.style.height = totalH + 'px';

    // 节点位置记录 { idx: {x, y, cx, cy} }
    var pos = {};

    // 放置 Start 标记
    var startX = totalW / 2 - markerW / 2;
    var startY = padTop;
    var startDiv = document.createElement('div');
    startDiv.className = 'flow-marker start';
    startDiv.style.left = startX + 'px';
    startDiv.style.top = startY + 'px';
    startDiv.innerHTML = '<i class="fas fa-play me-1"></i>Start';
    canvas.appendChild(startDiv);

    // 放置任务节点（按层）
    var currentY = startY + markerH + gapY;
    layers.forEach(function(layer) {
        var layerW = layer.length * nodeW + (layer.length - 1) * gapX;
        var offsetX = (totalW - layerW) / 2;

        layer.forEach(function(idx, col) {
            var t = tasks[idx];
            var x = offsetX + col * (nodeW + gapX);
            var y = currentY;

            pos[idx] = {
                x: x, y: y,
                cx: x + nodeW / 2,
                cy: y + nodeH / 2,
                top: y,
                bottom: y + nodeH,
                left: x,
                right: x + nodeW
            };

            var node = document.createElement('div');
            node.className = 'flow-node';
            node.style.left = x + 'px';
            node.style.top = y + 'px';
            node.style.width = nodeW + 'px';

            var svcText = escHtml((t.service || '').toUpperCase());
            var opText = escHtml(t.operation || '');
            var descText = t.description ? '<div class="fn-desc">' + escHtml(t.description) + '</div>' : '';

            node.innerHTML =
                '<div class="flow-node-head">' +
                    '<span class="step-badge">' + (idx + 1) + '</span>' +
                    '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + svcText + '</span>' +
                '</div>' +
                '<div class="flow-node-body">' +
                    '<div class="fn-name">' + escHtml(t.name) + '</div>' +
                    '<div class="fn-svc"><i class="fas fa-cog me-1"></i>' + svcText + ' &rarr; ' + opText + '</div>' +
                    descText +
                '</div>';

            canvas.appendChild(node);
            enableNodeDrag(node, idx);
        });

        currentY += nodeH + gapY;
    });

    // 放置 End 标记
    var endX = totalW / 2 - markerW / 2;
    var endY = currentY;
    var endDiv = document.createElement('div');
    endDiv.className = 'flow-marker end';
    endDiv.style.left = endX + 'px';
    endDiv.style.top = endY + 'px';
    endDiv.innerHTML = 'End <i class="fas fa-stop ms-1"></i>';
    canvas.appendChild(endDiv);

    // 保存图形状态，供拖拽重绘使用
    flowState = {
        canvas: canvas, tasks: tasks, layers: layers,
        pos: pos, nameMap: nameMap,
        nodeW: nodeW, nodeH: nodeH,
        markerW: markerW, markerH: markerH,
        startCx: startX + markerW / 2,
        startBottom: startY + markerH,
        endCx: endX + markerW / 2,
        endTop: endY
    };

    // 绑定 Start / End 标记拖拽
    enableMarkerDrag(startDiv, 'start');
    enableMarkerDrag(endDiv, 'end');

    // 更新内层容器高度
    canvas.style.height = (endY + markerH + padTop) + 'px';

    // 绘制 SVG 连线（首次）
    redrawAllLines();
}

// 重绘所有连线（拖拽时调用）
function redrawAllLines() {
    if (!flowState) return;
    var s = flowState;
    // 移除旧 SVG
    var oldSvg = s.canvas.querySelector('svg.flow-lines');
    if (oldSvg) oldSvg.remove();
    // 计算 SVG 尺寸：取所有节点的最大边界
    var maxX = 400, maxY = 400;
    for (var k in s.pos) {
        var p = s.pos[k];
        if (p.right > maxX) maxX = p.right;
        if (p.bottom > maxY) maxY = p.bottom;
    }
    var svgW = maxX + 100;
    var svgH = maxY + 100;
    // 重绘
    drawFlowLines(s.canvas, s.tasks, s.layers, s.pos, s.nameMap,
        svgW, svgH, s.startCx, s.startBottom, s.endCx, s.endTop);
}

// 绘制 SVG 连线
function drawFlowLines(canvas, tasks, layers, pos, nameMap, svgW, svgH, startCx, startBottom, endCx, endTop) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'flow-lines');
    svg.setAttribute('width', svgW);
    svg.setAttribute('height', svgH);

    // 箭头 marker 定义
    var defs = document.createElementNS(ns, 'defs');
    var marker = document.createElementNS(ns, 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '8');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    var poly = document.createElementNS(ns, 'polygon');
    poly.setAttribute('points', '0 0, 8 3, 0 6');
    poly.setAttribute('fill', '#0d6efd');
    marker.appendChild(poly);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // 辅助：画一条带箭头的路径
    function drawLine(x1, y1, x2, y2, color) {
        var dx = x2 - x1;
        var dy = y2 - y1;
        var midY = y1 + dy * 0.5;
        var d = 'M ' + x1 + ' ' + y1 +
                ' C ' + x1 + ' ' + midY + ', ' + x2 + ' ' + midY + ', ' + x2 + ' ' + y2;
        var path = document.createElementNS(ns, 'path');
        path.setAttribute('d', d);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', color || '#0d6efd');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('marker-end', 'url(#arrowhead)');
        path.setAttribute('opacity', '0.6');
        svg.appendChild(path);
    }

    canvas.insertBefore(svg, canvas.firstChild);

    // 1) Start → 第一层所有节点
    layers[0].forEach(function(idx) {
        var p = pos[idx];
        drawLine(startCx, startBottom, p.cx, p.top);
    });

    // 2) 依赖连线：从上游节点底部 → 下游节点顶部
    tasks.forEach(function(t, idx) {
        var deps = (t.depends_on || []).filter(function(d) { return nameMap[d] !== undefined; });
        deps.forEach(function(depName) {
            var fromIdx = nameMap[depName];
            var from = pos[fromIdx];
            var to = pos[idx];
            if (from && to) {
                drawLine(from.cx, from.bottom, to.cx, to.top);
            }
        });
    });

    // 3) 最后一层所有节点 → End
    var lastLayer = layers[layers.length - 1];
    lastLayer.forEach(function(idx) {
        var p = pos[idx];
        drawLine(p.cx, p.bottom, endCx, endTop);
    });
}

// 显示解释
function displayExplanation(explanation) {
    const explanationDiv = document.getElementById('workflowExplanation');
    document.getElementById('explanationContent').textContent = explanation;
    explanationDiv.classList.remove('d-none');
}

// 显示执行结果
function displayExecutionResult(execution) {
    // 可以在这里添加执行结果的显示逻辑
    console.log('执行结果:', execution);
}

// 执行工作流
async function executeWorkflow() {
    if (!currentWorkflow) {
        showError('没有可执行的工作流');
        return;
    }

    try {
        const response = await fetch('/api/workflow/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(currentWorkflow)
        });

        const result = await response.json();

        if (result.success) {
            showSuccess('工作流执行成功！');
            if (result.data) {
                displayExecutionResult(result.data);
            }
        } else {
            showError('执行失败: ' + (result.error || '未知错误'));
        }

    } catch (error) {
        showError('执行失败: ' + error.message);
    }
}

// 显示JSON
function showJson() {
    if (!currentWorkflow) {
        showError('没有工作流');
        return;
    }

    document.getElementById('jsonContent').textContent =
        JSON.stringify(currentWorkflow, null, 2);

    const modal = new bootstrap.Modal(document.getElementById('jsonModal'));
    modal.show();
}

// 导出工作流
function exportWorkflow() {
    if (!currentWorkflow) {
        showError('没有工作流');
        return;
    }

    const dataStr = JSON.stringify(currentWorkflow, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `${currentWorkflow.name || 'workflow'}.json`;
    link.click();

    showSuccess('工作流已导出');
}

// UI辅助函数

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.remove('d-none');
    } else {
        overlay.classList.add('d-none');
    }
}

function showError(message) {
    const errorDiv = document.getElementById('errorState');
    document.getElementById('errorMessage').textContent = message;
    errorDiv.classList.remove('d-none');

    // 3秒后自动隐藏
    setTimeout(() => {
        hideError();
    }, 5000);
}

function hideError() {
    document.getElementById('errorState').classList.add('d-none');
}

function showSuccess(message) {
    // 创建临时成功提示
    const successDiv = document.createElement('div');
    successDiv.className = 'alert alert-success alert-dismissible fade show position-fixed top-0 end-0 m-3';
    successDiv.style.zIndex = '9999';
    successDiv.innerHTML = `
        <i class="fas fa-check-circle"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(successDiv);

    // 3秒后自动移除
    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}

// 清理函数
function clearWorkflow() {
    currentWorkflow = null;
    document.getElementById('workflowContainer').classList.add('d-none');
    document.getElementById('emptyState').classList.remove('d-none');
}

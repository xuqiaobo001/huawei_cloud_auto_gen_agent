/**
 * 工作流设计器JavaScript
 * 可视化的拖拽设计器和执行器
 */

// 全局变量
let workflow = {
    name: '',
    description: '',
    tasks: [],
    variables: {}
};

let selectedNode = null;
let nodeCounter = 0;
let selectedTask = null;
let currentOperations = [];
let currentServiceName = '';

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('工作流设计器已加载');

    // 加载已生成的工作流
    const generatedWorkflow = localStorage.getItem('generatedWorkflow');
    if (generatedWorkflow) {
        workflow = JSON.parse(generatedWorkflow);
        loadWorkflow(workflow);
        localStorage.removeItem('generatedWorkflow');
    }

    setupEventListeners();
    loadServices();
});

// 设置事件监听
function setupEventListeners() {
    // 服务选择
    document.getElementById('serviceSelect').addEventListener('change', loadOperations);

    // 服务搜索
    document.getElementById('serviceSearch').addEventListener('input', filterServices);

    // 操作搜索
    document.getElementById('operationSearch').addEventListener('input', filterOperations);

    // 键盘删除快捷键
    document.addEventListener('keydown', function(e) {
        if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNode) {
            // 避免在输入框中触发
            const tag = e.target.tagName.toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
            e.preventDefault();
            deleteNode(selectedNode.id);
        }
    });

    // 拖拽事件
    setupDragAndDrop();
}

// 加载服务列表
async function loadServices() {
    try {
        const response = await fetch('/api/services/list');
        const result = await response.json();

        if (result.success) {
            const serviceSelect = document.getElementById('serviceSelect');
            serviceSelect.innerHTML = '<option value="">选择服务...</option>';

            result.data.forEach(svc => {
                const option = document.createElement('option');
                option.value = svc.name;
                option.dataset.description = svc.description || '';
                option.textContent = `${svc.name} - ${svc.description || ''} (${svc.operations})`;
                serviceSelect.appendChild(option);
            });

            console.log('已加载', result.data.length, '个服务');
        }
    } catch (error) {
        console.error('加载服务失败:', error);
    }
}

// 加载操作列表
async function loadOperations() {
    const serviceSelect = document.getElementById('serviceSelect');
    const serviceName = serviceSelect.value;

    if (!serviceName) {
        document.getElementById('operationsPanel').style.display = 'none';
        currentOperations = [];
        currentServiceName = '';
        return;
    }

    try {
        const response = await fetch(`/api/services/${serviceName}/operations`);
        const result = await response.json();

        if (result.success) {
            currentOperations = result.data;
            currentServiceName = serviceName;

            // 清空搜索框
            document.getElementById('operationSearch').value = '';

            renderOperations(currentOperations);
            document.getElementById('operationsPanel').style.display = 'block';
        }
    } catch (error) {
        console.error('加载操作失败:', error);
    }
}

// 渲染操作列表
function renderOperations(operations) {
    const operationsList = document.getElementById('operationsList');
    operationsList.innerHTML = '';

    operations.forEach(op => {
        const item = document.createElement('div');
        item.className = 'list-group-item list-group-item-action operation-item';
        item.draggable = true;
        item.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${op.name}</h6>
                <small class="text-muted">${op.method}</small>
            </div>
            <p class="mb-1 text-muted small">${op.description}</p>
        `;

        item.dataset.service = currentServiceName;
        item.dataset.operation = op.name;
        item.dataset.description = op.description;

        operationsList.appendChild(item);
    });

    // 更新计数
    const countEl = document.getElementById('operationsCount');
    if (operations.length === currentOperations.length) {
        countEl.textContent = `(共 ${operations.length} 个)`;
    } else {
        countEl.textContent = `(${operations.length} / ${currentOperations.length})`;
    }

    setupDragAndDrop();
}

// 服务搜索过滤
function filterServices() {
    const keyword = document.getElementById('serviceSearch').value.toLowerCase();
    const serviceSelect = document.getElementById('serviceSelect');
    const options = serviceSelect.querySelectorAll('option');

    options.forEach(option => {
        if (!option.value) return; // 跳过占位符
        const name = option.value.toLowerCase();
        const desc = (option.dataset.description || '').toLowerCase();
        option.style.display = (name.includes(keyword) || desc.includes(keyword)) ? '' : 'none';
    });
}

// 操作搜索过滤
function filterOperations() {
    const keyword = document.getElementById('operationSearch').value.toLowerCase();
    if (!keyword) {
        renderOperations(currentOperations);
        return;
    }
    const filtered = currentOperations.filter(op =>
        op.name.toLowerCase().includes(keyword) ||
        (op.description || '').toLowerCase().includes(keyword)
    );
    renderOperations(filtered);
}

// 设置拖拽功能
function setupDragAndDrop() {
    const draggableItems = document.querySelectorAll('.task-template, .operation-item');
    const canvas = document.getElementById('workflowCanvas');

    // 拖拽开始
    draggableItems.forEach(item => {
        item.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('text/plain', JSON.stringify({
                type: this.dataset.type || 'api',
                service: this.dataset.service,
                operation: this.dataset.operation,
                description: this.dataset.description,
                name: this.textContent.trim()
            }));
        });
    });

    // 禁止默认拖拽行为
    canvas.addEventListener('dragover', function(e) {
        e.preventDefault();
    });

    // 放置
    canvas.addEventListener('drop', function(e) {
        e.preventDefault();

        try {
            const data = JSON.parse(e.dataTransfer.getData('text/plain'));
            const rect = canvas.getBoundingClientRect();

            // 计算放置位置
            const x = e.clientX - rect.left - 75; // 减去节点宽度的一半
            const y = e.clientY - rect.top - 30;  // 减去节点高度的一半

            addNode(data, x, y);
        } catch (error) {
            console.error('放置失败:', error);
        }
    });
}

// 添加节点到画布
function addNode(data, x, y) {
    const nodeId = 'node_' + (++nodeCounter);

    const node = document.createElement('div');
    node.className = 'task-node';
    node.id = nodeId;
    node.style.left = Math.max(0, x) + 'px';
    node.style.top = Math.max(0, y) + 'px';

    // 生成任务名称
    const taskName = data.operation || data.type + '_' + nodeCounter;

    node.innerHTML = `
        <button class="node-delete-btn" title="删除节点">&times;</button>
        <div class="task-title">${taskName}</div>
        <div class="task-service">${data.service || data.type}</div>
    `;

    // 添加点击事件
    node.addEventListener('click', function(e) {
        if (e.target.classList.contains('node-delete-btn')) return;
        selectNode(node, data);
    });

    // 删除按钮点击
    node.querySelector('.node-delete-btn').addEventListener('click', function(e) {
        e.stopPropagation();
        deleteNode(nodeId);
    });

    // 添加到画布
    const canvas = document.getElementById('workflowCanvas');
    canvas.appendChild(node);

    // 隐藏提示
    const placeholder = canvas.querySelector('.canvas-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    // 创建任务对象
    const task = {
        id: nodeId,
        name: taskName,
        type: 'huaweicloud_api',
        description: data.description || '',
        service: data.service,
        operation: data.operation,
        parameters: {},
        depends_on: [],
        x: x,
        y: y
    };

    workflow.tasks.push(task);

    // 自动选中
    selectNode(node, task);

    showMessage('已添加任务: ' + taskName, 'success');
}

// 选择节点
function selectNode(nodeElement, taskData) {
    // 移除之前的选中状态
    document.querySelectorAll('.task-node').forEach(n => {
        n.classList.remove('selected');
    });

    // 添加选中状态
    nodeElement.classList.add('selected');
    nodeElement.style.borderColor = '#28a745';
    selectedNode = nodeElement;
    selectedTask = taskData;

    // 显示属性面板
    showNodeProperties(taskData);
}

// 删除节点
function deleteNode(nodeId) {
    const node = document.getElementById(nodeId);
    if (!node) return;

    // 从workflow.tasks中移除
    const taskIndex = workflow.tasks.findIndex(t => t.id === nodeId);
    const taskName = taskIndex >= 0 ? workflow.tasks[taskIndex].name : '';
    if (taskIndex >= 0) {
        workflow.tasks.splice(taskIndex, 1);
    }

    // 清除其他任务对该节点的依赖
    workflow.tasks.forEach(t => {
        if (t.depends_on) {
            t.depends_on = t.depends_on.filter(dep => dep !== taskName);
        }
    });

    // 从画布移除DOM
    node.remove();

    // 如果删除的是当前选中节点，重置选中状态
    if (selectedNode && selectedNode.id === nodeId) {
        selectedNode = null;
        selectedTask = null;
        document.getElementById('nodePropertiesPanel').style.display = 'none';
        document.getElementById('noSelectionPanel').style.display = 'block';
    }

    // 如果画布为空，显示占位提示
    const canvas = document.getElementById('workflowCanvas');
    if (!canvas.querySelector('.task-node')) {
        const placeholder = canvas.querySelector('.canvas-placeholder');
        if (placeholder) placeholder.style.display = 'block';
    }

    showMessage('已删除任务: ' + (taskName || nodeId), 'info');
}

// 显示节点属性
function showNodeProperties(task) {
    document.getElementById('noSelectionPanel').style.display = 'none';
    document.getElementById('nodePropertiesPanel').style.display = 'block';

    const propertiesDiv = document.getElementById('nodeProperties');
    propertiesDiv.innerHTML = `
        <div class="form-group mb-3">
            <label class="form-label">任务名称</label>
            <input type="text" class="form-control" value="${task.name}" onchange="updateTaskProperty('name', this.value)">
        </div>
        <div class="form-group mb-3">
            <label class="form-label">服务</label>
            <input type="text" class="form-control" value="${task.service || ''}" readonly>
        </div>
        <div class="form-group mb-3">
            <label class="form-label">操作</label>
            <input type="text" class="form-control" value="${task.operation || ''}" readonly>
        </div>
        <div class="form-group mb-3">
            <label class="form-label">描述</label>
            <textarea class="form-control" rows="2" onchange="updateTaskProperty('description', this.value)">${task.description || ''}</textarea>
        </div>
        <div class="form-group mb-3">
            <label class="form-label">依赖任务</label>
            <select multiple class="form-select" onchange="updateDependencies(this.selectedOptions)">
                ${workflow.tasks.map(t => t.name).filter(name => name !== task.name).map(name =>
                    `<option value="${name}" ${task.depends_on && task.depends_on.includes(name) ? 'selected' : ''}>${name}</option>`
                ).join('')}
            </select>
            <small class="form-text text-muted">按住Ctrl键多选</small>
        </div>
        <div class="form-group mb-3">
            <label class="form-label">参数</label>
            <button class="btn btn-sm btn-outline-primary" onclick="editParameters()">编辑参数</button>
            <div class="mt-2">
                <pre class="form-control" style="height: 150px; font-size: 12px;">${JSON.stringify(task.parameters || {}, null, 2)}</pre>
            </div>
        </div>
        <hr>
        <button class="btn btn-sm btn-outline-danger w-100" onclick="deleteNode('${task.id}')">
            <i class="fas fa-trash-alt"></i> 删除此节点
        </button>
    `;
}

// 更新任务属性
function updateTaskProperty(property, value) {
    if (selectedTask) {
        selectedTask[property] = value;

        // 如果是名称，同步到画布显示
        if (property === 'name') {
            const titleElement = selectedNode.querySelector('.task-title');
            if (titleElement) {
                titleElement.textContent = value;
            }
        }
    }
}

// 更新依赖关系
function updateDependencies(selectedOptions) {
    if (selectedTask) {
        selectedTask.depends_on = Array.from(selectedOptions).map(opt => opt.value);
    }
}

// 编辑参数
function editParameters() {
    if (!selectedTask) return;

    const modal = new bootstrap.Modal(document.getElementById('paramsModal'));
    const editor = document.getElementById('paramsEditor');

    editor.value = JSON.stringify(selectedTask.parameters || {}, null, 2);
    modal.show();
}

// 保存参数
function saveParameters() {
    const editor = document.getElementById('paramsEditor');

    try {
        const params = JSON.parse(editor.value);
        selectedTask.parameters = params;

        // 关闭模态框
        bootstrap.Modal.getInstance(document.getElementById('paramsModal')).hide();

        // 刷新属性面板
        showNodeProperties(selectedTask);

        showMessage('参数保存成功', 'success');
    } catch (error) {
        showMessage('JSON格式错误，请检查', 'error');
    }
}

// 清空画布
function clearCanvas() {
    if (confirm('确定要清空画布吗？所有任务将被删除。')) {
        const canvas = document.getElementById('workflowCanvas');
        const nodes = canvas.querySelectorAll('.task-node');
        nodes.forEach(node => node.remove());

        // 显示提示
        const placeholder = canvas.querySelector('.canvas-placeholder');
        placeholder.style.display = 'block';

        workflow.tasks = [];
        selectedNode = null;
        selectedTask = null;

        showMessage('已清空画布', 'info');
    }
}

// 加载工作流到画布
function loadWorkflow(workflowData) {
    workflow = workflowData;

    // 设置工作流信息
    document.getElementById('workflowName').value = workflow.name || '';
    document.getElementById('workflowDescription').value = workflow.description || '';

    // 绘制任务节点
    if (workflow.tasks && workflow.tasks.length > 0) {
        workflow.tasks.forEach((task, index) => {
            // 设置默认位置
            task.x = task.x || (index * 200 + 50);
            task.y = task.y || 50;

            addNodeToCanvas(task);
        });
    }
}

// 添加节点到画布（从工作流数据）
function addNodeToCanvas(task) {
    const node = document.createElement('div');
    node.className = 'task-node';
    node.id = task.id;
    node.style.left = task.x + 'px';
    node.style.top = task.y + 'px';

    node.innerHTML = `
        <div class="task-title">${task.name}</div>
        <div class="task-service">${task.service || ''}</div>
    `;

    node.addEventListener('click', function() {
        selectNode(node, task);
    });

    const canvas = document.getElementById('workflowCanvas');
    canvas.appendChild(node);

    // 隐藏提示
    const placeholder = canvas.querySelector('.canvas-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
}

// 执行工作流
async function executeWorkflow() {
    if (workflow.tasks.length === 0) {
        showMessage('没有任务需要执行', 'warning');
        return;
    }

    // 更新工作流信息
    workflow.name = document.getElementById('workflowName').value || '未命名工作流';
    workflow.description = document.getElementById('workflowDescription').value || '';

    if (confirm(`确认执行工作流 "${workflow.name}" 吗？`)) {
        showLoading(true);

        try {
            const response = await fetch('/api/workflow/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(workflow)
            });

            const result = await response.json();

            if (result.success) {
                showMessage('工作流执行完成', 'success');
                showExecutionResult(result.data);
            } else {
                showMessage(`执行失败: ${result.error}`, 'error');
            }

        } catch (error) {
            console.error('执行失败:', error);
            showMessage('执行失败，请稍后重试', 'error');
        } finally {
            showLoading(false);
        }
    }
}

// 显示执行结果
function showExecutionResult(result) {
    const modal = new bootstrap.Modal(document.getElementById('messageModal'));
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    title.innerHTML = '<i class="fas fa-check-circle"></i> 执行结果';

    const statusColors = {
        success: 'success',
        failed: 'danger',
        running: 'info',
        partial_success: 'warning'
    };

    body.innerHTML = `
        <div class="alert alert-${statusColors[result.status] || 'info'}" role="alert">
            <h5>工作流: ${result.workflow_name}</h5>
            <p>状态: <strong>${getStatusText(result.status)}</strong></p>
            <p>
                任务: ${result.task_stats.success}/${result.task_stats.total} 成功
                ${result.duration ? `<br>耗时: ${formatDuration(result.duration)}` : ''}
            </p>
            ${result.errors && result.errors.length > 0 ? '<p>错误: ' + result.errors.length + ' 个</p>' : ''}
        </div>

        <h6>输出结果:</h6>
        <div class="json-viewer">
            <pre>${JSON.stringify(result.outputs || {}, null, 2)}</pre>
        </div>
    `;

    modal.show();
}

// 验证工作流
async function validateWorkflow() {
    showLoading(true);

    try {
        const response = await fetch('/api/workflow/validate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(workflow)
        });

        const result = await response.json();

        if (result.success) {
            if (result.data.valid) {
                showMessage('工作流验证通过，无错误', 'success');
            } else {
                const errors = result.data.errors.join('\n');
                showMessage('工作流验证发现错误:\n' + errors, 'error');
            }
        } else {
            showMessage(`验证失败: ${result.error}`, 'error');
        }

    } catch (error) {
        console.error('验证失败:', error);
        showMessage('验证失败，请稍后重试', 'error');
    } finally {
        showLoading(false);
    }
}

// 保存工作流
async function saveWorkflow() {
    try {
        const response = await fetch('/api/workflow/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(workflow)
        });

        const result = await response.json();

        if (result.success) {
            showMessage('工作流保存成功', 'success');
        } else {
            showMessage(`保存失败: ${result.error}`, 'error');
        }

    } catch (error) {
        console.error('保存失败:', error);
        showMessage('保存失败，请稍后重试', 'error');
    }
}

// 显示JSON
function showWorkflowJson() {
    const modal = new bootstrap.Modal(document.getElementById('messageModal'));
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    title.innerHTML = '<i class="fas fa-file-code"></i> 工作流JSON';
    body.innerHTML = `
        <div class="json-viewer">
            <pre>${JSON.stringify(workflow, null, 2)}</pre>
        </div>
    `;

    modal.show();
}

// 显示依赖关系
function showDependencies() {
    const modal = new bootstrap.Modal(document.getElementById('messageModal'));
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    title.innerHTML = '<i class="fas fa-sitemap"></i> 依赖关系';

    let depHtml = '<ul class="list-group">';
    workflow.tasks.forEach(task => {
        depHtml += `
            <li class="list-group-item">
                <strong>${task.name}</strong>
                ${task.depends_on && task.depends_on.length > 0 ?
                    '<br><small class="text-muted">依赖: ' + task.depends_on.join(', ') + '</small>'
                    : '<br><small class="text-muted">无依赖</small>'
                }
            </li>
        `;
    });
    depHtml += '</ul>';

    body.innerHTML = depHtml;
    modal.show();
}

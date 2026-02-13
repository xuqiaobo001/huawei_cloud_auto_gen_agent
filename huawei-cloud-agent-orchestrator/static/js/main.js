/**
 * 主页面JavaScript
 * 处理工作流生成、模板加载等功能
 */

// 全局变量
let currentWorkflow = null;
let isLoading = false;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('华为云Agent编排系统已加载');
    loadExecutionHistory();
    setupEventListeners();
});

// 设置事件监听
function setupEventListeners() {
    // 生成工作流按钮
    const generateBtn = document.getElementById('generateBtn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateWorkflow);
    }

    // 手动设计按钮
    const designBtn = document.getElementById('designBtn');
    if (designBtn) {
        designBtn.addEventListener('click', () => {
            window.location.href = '/designer';
        });
    }

    // 支持回车键生成
    const requirementInput = document.getElementById('requirementInput');
    if (requirementInput) {
        requirementInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) {
                generateWorkflow();
            }
        });
    }
}

// 生成工作流 — 携带需求跳转到AI自动生成页面
function generateWorkflow() {
    const requirementInput = document.getElementById('requirementInput');
    const requirement = requirementInput.value.trim();

    if (!requirement) {
        showMessage('请输入部署需求', 'warning');
        return;
    }

    localStorage.setItem('autoRequirement', requirement);
    window.location.href = '/auto';
}

// 加载模板
function loadTemplate(templateType) {
    let templateText = '';

    switch (templateType) {
        case 'web':
            templateText = '部署一个完整的Web应用，包括VPC网络、ECS服务器和RDS数据库';
            break;
        case 'ecs':
            templateText = '创建一台ECS服务器，规格2核4G';
            break;
        case 'database':
            templateText = '创建一个MySQL 8.0数据库实例';
            break;
        default:
            return;
    }

    document.getElementById('requirementInput').value = templateText;
    showMessage(`已加载${templateType === 'web' ? 'Web应用' : templateType === 'ecs' ? 'ECS' : '数据库'}模板`, 'info');
}

// 加载执行历史
async function loadExecutionHistory() {
    try {
        const response = await fetch('/api/executions/list?limit=5');
        const result = await response.json();

        if (result.success && result.data.length > 0) {
            const historyContainer = document.getElementById('executionHistory');
            historyContainer.innerHTML = renderExecutionHistory(result.data);
        }
    } catch (error) {
        console.error('加载执行历史失败:', error);
    }
}

// 渲染执行历史
function renderExecutionHistory(executions) {
    if (!executions || executions.length === 0) {
        return '<p class="text-muted text-center">暂无执行记录</p>';
    }

    return executions.map(execution => `
        <div class="execution-item">
            <div class="execution-title">${execution.workflow_name}</div>
            <div class="execution-time">${formatDateTime(execution.start_time)}</div>
            <div class="execution-status">
                <span class="status-badge badge-${execution.status}">
                    ${getStatusText(execution.status)}
                </span>
            </div>
            <div class="clearfix"></div>
            <div class="mt-2">
                <small class="text-muted">
                    任务: ${execution.task_stats.success}/${execution.task_stats.total} 成功
                    ${execution.duration ? ` | 耗时: ${formatDuration(execution.duration)}` : ''}
                </small>
            </div>
        </div>
    `).join('');
}

// 工具函数

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.toggle('d-none', !show);
    }
    isLoading = show;
}

function showMessage(message, type = 'info') {
    const modal = new bootstrap.Modal(document.getElementById('messageModal'));
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    const typeConfig = {
        success: { title: '成功', class: 'text-success', icon: 'fa-check-circle' },
        error: { title: '错误', class: 'text-danger', icon: 'fa-times-circle' },
        warning: { title: '警告', class: 'text-warning', icon: 'fa-exclamation-triangle' },
        info: { title: '提示', class: 'text-info', icon: 'fa-info-circle' }
    };

    const config = typeConfig[type] || typeConfig.info;

    title.innerHTML = `<i class="fas ${config.icon}"></i> ${config.title}`;
    body.innerHTML = `<p class="${config.class}">${message}</p>`;

    modal.show();
}

function formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}秒`;
    } else if (seconds < 3600) {
        return `${Math.round(seconds / 60)}分钟`;
    } else {
        return `${Math.round(seconds / 3600)}小时`;
    }
}

function getStatusText(status) {
    const statusMap = {
        success: '成功',
        running: '运行中',
        failed: '失败',
        pending: '待执行',
        partial_success: '部分成功'
    };
    return statusMap[status] || status;
}

// 控制台信息
console.log('%c华为云Agent编排系统已启动', 'color: #007bff; font-size: 18px; font-weight: bold;');
console.log('%c支持使用自然语言描述自动生成工作流', 'color: #28a745; font-size: 14px;');

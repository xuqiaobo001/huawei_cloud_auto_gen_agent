// 工作流历史记录页面

let currentDetail = null;

document.addEventListener('DOMContentLoaded', loadRecords);

async function loadRecords() {
    try {
        const resp = await fetch('/api/workflows/history?limit=50&offset=0');
        const result = await resp.json();

        const tbody = document.getElementById('recordsBody');
        const emptyState = document.getElementById('emptyState');
        const totalCount = document.getElementById('totalCount');

        if (!result.success) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-3">加载失败: ' + (result.error || '') + '</td></tr>';
            return;
        }

        const records = result.data.records || [];
        const total = result.data.total || 0;
        totalCount.textContent = '共 ' + total + ' 条记录';

        if (records.length === 0) {
            tbody.innerHTML = '';
            emptyState.classList.remove('d-none');
            return;
        }

        tbody.innerHTML = '';
        records.forEach(function(r, i) {
            var tr = document.createElement('tr');
            tr.className = 'record-row';
            tr.onclick = function() { viewDetail(r.id); };

            var services = (r.services_used || '').split(', ').filter(Boolean);
            var badges = services.map(function(s) {
                return '<span class="badge bg-info svc-badge me-1">' + escHtml(s) + '</span>';
            }).join('');

            var timeStr = r.created_at ? formatTime(r.created_at) : '-';

            tr.innerHTML =
                '<td class="text-muted">' + (i + 1) + '</td>' +
                '<td class="fw-semibold">' + escHtml(r.workflow_name || '未命名') + '</td>' +
                '<td class="text-truncate" style="max-width:300px" title="' + escAttr(r.requirement) + '">' + escHtml(r.requirement) + '</td>' +
                '<td>' + badges + '</td>' +
                '<td><span class="badge bg-primary">' + r.task_count + '</span></td>' +
                '<td class="text-muted small">' + timeStr + '</td>' +
                '<td>' +
                    '<button class="btn btn-outline-danger btn-sm" onclick="event.stopPropagation(); deleteRecord(\'' + r.id + '\')">' +
                        '<i class="fas fa-trash-alt"></i>' +
                    '</button>' +
                '</td>';

            tbody.appendChild(tr);
        });

    } catch (err) {
        document.getElementById('recordsBody').innerHTML =
            '<tr><td colspan="7" class="text-center text-danger py-3">网络错误: ' + err.message + '</td></tr>';
    }
}

async function viewDetail(recordId) {
    try {
        const resp = await fetch('/api/workflows/history/' + recordId);
        const result = await resp.json();
        if (!result.success) { alert('加载失败: ' + (result.error || '')); return; }

        currentDetail = result.data;
        document.getElementById('detailTitle').textContent = currentDetail.workflow_name || '工作流详情';
        document.getElementById('detailRequirement').textContent = currentDetail.requirement || '';
        document.getElementById('detailDesc').textContent = currentDetail.workflow_description || '';
        document.getElementById('detailJson').textContent = JSON.stringify(currentDetail.workflow_json, null, 2);

        // Reset to flow tab
        switchDetailTab('flow');

        // Render flow diagram
        if (currentDetail.workflow_json && typeof FlowRenderer !== 'undefined') {
            FlowRenderer.render('detailFlowCanvas', currentDetail.workflow_json);
        }

        var modal = new bootstrap.Modal(document.getElementById('detailModal'));
        modal.show();
    } catch (err) {
        alert('加载详情失败: ' + err.message);
    }
}

async function deleteRecord(recordId) {
    if (!confirm('确定删除此记录？')) return;
    try {
        const resp = await fetch('/api/workflows/history/' + recordId, { method: 'DELETE' });
        const result = await resp.json();
        if (result.success) {
            loadRecords();
        } else {
            alert('删除失败: ' + (result.error || ''));
        }
    } catch (err) {
        alert('删除失败: ' + err.message);
    }
}

function exportDetail() {
    if (!currentDetail || !currentDetail.workflow_json) return;
    var blob = new Blob([JSON.stringify(currentDetail.workflow_json, null, 2)], { type: 'application/json' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = (currentDetail.workflow_name || 'workflow') + '.json';
    link.click();
}

function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

function escAttr(s) {
    return (s || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function switchDetailTab(tab, event) {
    if (event) event.preventDefault();
    var tabs = document.querySelectorAll('#detailTabs .nav-link');
    tabs.forEach(function(t) { t.classList.toggle('active', t.getAttribute('data-tab') === tab); });
    document.getElementById('detailFlowTab').style.display = tab === 'flow' ? '' : 'none';
    document.getElementById('detailJsonTab').style.display = tab === 'json' ? '' : 'none';
}

function formatTime(iso) {
    try {
        var d = new Date(iso);
        var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
               ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    } catch (e) {
        return iso;
    }
}

/**
 * DataTables — project_list (UF)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('project-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterEstado = document.getElementById('filter-estado');
    const filterRol = document.getElementById('filter-rol');
    let estadoValue = '';
    let rolValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'project-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (estadoValue && row.dataset.estado !== estadoValue) {
            return false;
        }
        if (rolValue && row.dataset.rol !== rolValue) {
            return false;
        }
        return true;
    });

    const table = new DataTable('#project-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay proyectos en tu alcance.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[6, 'desc']],
        columnDefs: [
            { orderable: false, searchable: false, targets: -1, className: 'col-actions' },
        ],
    });

    tableEl.dataset.dtInit = 'true';

    if (filterEstado) {
        filterEstado.addEventListener('change', function () {
            estadoValue = this.value;
            table.draw();
        });
    }

    if (filterRol) {
        filterRol.addEventListener('change', function () {
            rolValue = this.value;
            table.draw();
        });
    }
});

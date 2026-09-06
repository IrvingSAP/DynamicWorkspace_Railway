document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-dw-delete]").forEach(function (trigger) {
        trigger.addEventListener("click", function (e) {
            e.preventDefault();
            var form = trigger.closest("form");
            var message = trigger.dataset.dwDeleteMessage
                || "¿Confirma esta acción?";
            if (typeof window.dwConfirmWarning === "function") {
                window.dwConfirmWarning(message, function () {
                    if (form) form.submit();
                }, { title: "Confirmar", okLabel: "Revocar" });
            } else if (form) {
                form.submit();
            }
        });
    });

    if (typeof DataTable === "undefined") {
        return;
    }
    var auditEl = document.getElementById("api-audit-table");
    if (auditEl && auditEl.dataset.dtInit !== "true") {
        new DataTable("#api-audit-table", {
            language: DW_DATATABLES_ES,
            layout: DW_DATATABLES_LAYOUT,
            pageLength: 25,
            order: [[0, "desc"]],
            columnDefs: [{ orderable: false, searchable: false, targets: -1 }],
        });
        auditEl.dataset.dtInit = "true";
    }
    var tableEl = document.getElementById("api-client-table");
    if (!tableEl || tableEl.dataset.dtInit === "true") {
        return;
    }
    var filterStatus = document.getElementById("filter-status");
    var statusValue = "";
    DataTable.ext.search.push(function (settings, _data, dataIndex) {
        if (!settings.nTable || settings.nTable.id !== "api-client-table") {
            return true;
        }
        if (!statusValue) return true;
        var row = new DataTable.Api(settings).row(dataIndex).node();
        return row && row.dataset.status === statusValue;
    });
    var table = new DataTable("#api-client-table", {
        language: DW_DATATABLES_ES,
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[0, "asc"]],
        columnDefs: [{ orderable: false, searchable: false, targets: -1 }],
    });
    tableEl.dataset.dtInit = "true";
    if (filterStatus) {
        filterStatus.addEventListener("change", function () {
            statusValue = this.value;
            table.draw();
        });
    }
});

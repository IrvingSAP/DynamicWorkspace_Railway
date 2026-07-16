/**
 * FilePipe submenu toggle — UF sidebar
 */
(function () {
    if (document.documentElement.dataset.sidebarUfBound === "1") return;
    document.documentElement.dataset.sidebarUfBound = "1";

    document.querySelectorAll(".sidebar-nav-group-toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var group = btn.closest(".sidebar-nav-group");
            if (!group) return;
            var open = group.classList.toggle("is-open");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });
})();

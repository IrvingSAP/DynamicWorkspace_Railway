/**
 * FilePipe / UF sidebar — group toggles + expand when icons-only
 */
(function () {
    if (document.documentElement.dataset.sidebarUfBound === "1") return;
    document.documentElement.dataset.sidebarUfBound = "1";

    document.querySelectorAll(".sidebar-nav-group-toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var group = btn.closest(".sidebar-nav-group");
            if (!group) return;

            var iconsMode = document.documentElement.classList.contains("sidebar-icons");
            var mobile = window.matchMedia && window.matchMedia("(max-width: 768px)").matches;

            if (iconsMode && !mobile) {
                if (window.dwSidebarCollapse) {
                    window.dwSidebarCollapse.expand();
                }
                group.classList.add("is-open");
                btn.setAttribute("aria-expanded", "true");
                return;
            }

            var open = group.classList.toggle("is-open");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });
})();

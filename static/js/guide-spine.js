/**
 * Resalta el flujo activo en guías con índice lateral (pública y UF).
 */
(function () {
    "use strict";

    function bindSpine(navSelector, sectionSelector, topOffset) {
        var links = document.querySelectorAll(navSelector);
        var sections = Array.from(document.querySelectorAll(sectionSelector));
        if (!links.length || !sections.length) {
            return;
        }

        function setActive() {
            var current = sections[0];
            sections.forEach(function (section) {
                if (section.getBoundingClientRect().top <= topOffset) {
                    current = section;
                }
            });
            links.forEach(function (link) {
                link.classList.toggle(
                    "is-active",
                    link.getAttribute("href") === "#" + current.id
                );
            });
        }

        window.addEventListener("scroll", setActive, { passive: true });
        setActive();
    }

    bindSpine(".pub-guide-nav nav a", ".pub-flow-card[id]", 140);
    bindSpine(".guide-spine nav a", ".flow-card[id]", 120);
})();

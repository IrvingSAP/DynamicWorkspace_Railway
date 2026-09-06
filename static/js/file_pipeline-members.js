(function () {
  var root = document.querySelector("[data-fp-member-search]");
  if (!root) return;
  var url = root.getAttribute("data-fp-member-search");
  var q = document.getElementById("invite-q");
  var hidden = document.getElementById("invite-user");
  var hits = document.getElementById("invite-hits");
  if (!q || !hidden || !hits || !url) return;

  function hide() {
    hits.hidden = true;
    hits.innerHTML = "";
  }

  function render(results) {
    hits.innerHTML = "";
    if (!results.length) {
      var empty = document.createElement("li");
      empty.className = "fp-user-picker-empty";
      empty.textContent = "Sin coincidencias en esta compañía.";
      hits.appendChild(empty);
    } else {
      results.forEach(function (u) {
        var li = document.createElement("li");
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = u.label;
        b.addEventListener("click", function () {
          hidden.value = u.id;
          q.value = u.label;
          hide();
        });
        li.appendChild(b);
        hits.appendChild(li);
      });
    }
    hits.hidden = false;
  }

  var timer = null;
  q.addEventListener("input", function () {
    hidden.value = "";
    var term = q.value.trim();
    if (term.length < 2) {
      hide();
      return;
    }
    clearTimeout(timer);
    timer = setTimeout(function () {
      fetch(url + "?q=" + encodeURIComponent(term), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          render(data.results || []);
        })
        .catch(function () {
          hide();
        });
    }, 220);
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".fp-user-picker")) hide();
  });
})();

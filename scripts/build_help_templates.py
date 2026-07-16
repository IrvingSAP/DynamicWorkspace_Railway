from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

proto_pub = (ROOT / "prototype/public/public_help.html").read_text(encoding="utf-8")
start = proto_pub.index('<section class="pub-page-hero">')
end = proto_pub.index("</main>")
body = proto_pub[start:end]
body = body.replace('href="public_contact.html"', 'href="{% url \'public:contact\' %}"')
body = body.replace('style="padding-top: 0;"', 'class="pub-section-tight-top"')

pub_tpl = """{% extends "public/base.html" %}
{% load static %}

{% block title %}Guía del sistema — DynamicWorkspace{% endblock %}

{% block extra_head %}
<script src=\"{% static 'js/guide-spine.js' %}\" defer></script>
{% endblock %}

{% block content %}
""" + body + """
<section class="pub-section">
    <div class="pub-container">
        <div class="pub-cta">
            <h2>¿Quieres verlo con datos de tu equipo?</h2>
            <p>Las cuentas se habilitan por administración. Cuéntanos tu caso y te mostramos cómo quedaría tu primer proyecto.</p>
            <a href="{% url 'public:contact' %}" class="btn btn-primary">Solicitar información</a>
        </div>
    </div>
</section>
{% endblock %}
"""
(ROOT / "templates/public/help.html").write_text(pub_tpl, encoding="utf-8")

proto_uf = (ROOT / "prototype/help/uf_guide.html").read_text(encoding="utf-8")
start = proto_uf.index('<nav class="breadcrumb"')
end = proto_uf.index("<script>")
body = proto_uf[start:end]

body = body.replace('href="../dashboard/dashboard_uf_home.html"', 'href="{% url \'dashboard:home\' %}"')
body = body.replace('href="../projects/project_list.html"', 'href="{% url \'projects:list\' %}"')
body = body.replace('href="uf_guide.html"', 'href="{% url \'help:uf_guide\' %}"')
body = body.replace('<span class="cell-badge">inventario-2026</span>', '<span class="cell-badge">{{ company.name_short }}</span>')
body = body.replace('<span class="cell-badge cell-badge--sm">ACME</span>', "")
body = body.replace("(<span class=\"cell-badge cell-badge--sm\">ACME</span>)", "({{ company.name_short }})")
body = body.replace("jperez.uf", "{{ request.user.username }}")
body = body.replace("Juan", "{{ request.user.first_name|default:request.user.username }}")

def slug_href(url_name: str) -> str:
    return (
        '{% if example_project %}href="{% url \''
        + url_name
        + '\' slug=example_project.slug %}"{% else %}href="{% url \'projects:list\' %}"{% endif %}'
    )

body = body.replace('href="../projects/project_create.html"', 'href="{% url \'projects:create\' %}"')
body = body.replace('href="../projects/project_detail.html"', slug_href("projects:detail"))
body = body.replace('href="../fields/field_list.html"', slug_href("fields:list"))
body = body.replace('href="../fields/field_create.html"', slug_href("fields:create"))
body = body.replace('href="../projects/project_members.html"', slug_href("projects:members"))
body = body.replace('href="../records/record_list.html"', slug_href("records:list"))
body = body.replace('href="../records/record_create.html"', slug_href("records:create"))
body = body.replace('href="../records/record_expand.html"', slug_href("records:expand"))
body = body.replace('href="../records/record_expand_display.html"', slug_href("records:expand_display"))

uf_tpl = """{% extends "app_base.html" %}
{% load static %}

{% block title %}Ayuda — Guía de trabajo{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href=\"{% static 'css/help.css' %}\">
{% endblock %}

{% block sidebar_nav %}
{% include "includes/sidebar_uf.html" %}
{% endblock %}

{% block main_class %}app-main--wide{% endblock %}

{% block content %}
""" + body + """{% endblock %}

{% block extra_js %}
<script src=\"{% static 'js/guide-spine.js' %}\" defer></script>
{% endblock %}
"""
(ROOT / "templates/help").mkdir(exist_ok=True)
(ROOT / "templates/help/uf_guide.html").write_text(uf_tpl, encoding="utf-8")
print("OK")

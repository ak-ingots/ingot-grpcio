{#-
Compact Markdown template for towncrier.

Adapted from towncrier's shipped `default.md`, with the blank line after the
version heading and after each category heading removed, so generated sections
match the handwritten history in CHANGELOG.md:

    ## [0.9.0] - 2025-11-02
    ### Changed
    - Some change.

    ## [0.8.0] - 2025-09-13

Categories stay separated by a single blank line. Categories with
`showcontent = false` (misc) are internal and never rendered.
-#}
{%- macro heading(level) -%}
    {{- "#" * ( header_prefix | length + level - 1 ) }}
{%- endmacro -%}
{%- set newline = "\n" -%}
{%- if render_title %}
    {%- if versiondata.name %}
        {{- heading(1) ~ " " ~ versiondata.name ~ " " ~ versiondata.version ~ " (" ~ versiondata.date ~ ")" ~ newline }}
    {%- else %}
        {{- heading(1) ~ " " ~ versiondata.version ~ " (" ~ versiondata.date ~ ")" ~ newline }}
    {%- endif %}
{%- endif %}
{%- for section, _ in sections.items() %}
    {%- if section %}
        {{- newline }}
        {{- heading(2) ~ " " ~ section ~ newline }}
    {%- endif %}
    {%- if sections[section] %}
        {%- set ns = namespace(first=true) %}
        {%- for category, val in definitions.items() if category in sections[section] and val["showcontent"] %}
            {#- One blank line between categories, none after the heading. -#}
            {%- if not ns.first %}{{- newline }}{%- endif %}
            {%- set ns.first = false %}
            {{- heading(3 if section else 2) ~ " " ~ definitions[category]['name'] ~ newline }}
            {%- for text, values in sections[section][category].items() %}
                {%- set issue_pks = [] %}
                {%- for v_issue in values %}
                    {%- set _ = issue_pks.append(v_issue.split(": ", 1)[0]) %}
                {%- endfor %}
                {%- set issues_list = issue_pks | join(", ") %}
                {%- set text_has_sublist = (("\n  - " in text) or ("\n  * " in text)) %}
                {%- if not text and issues_list %}
                    {{- "- " ~ issues_list ~ newline }}
                {%- elif text and issues_list %}
                    {%- if text_has_sublist %}
                        {{- "- " ~ text ~ newline ~ newline ~ "  (" ~ issues_list ~ ")" ~ newline }}
                    {%- else %}
                        {{- "- " ~ text ~ " (" ~ issues_list ~ ")" ~ newline }}
                    {%- endif %}
                {%- elif text %}
                    {{- "- " ~ text ~ newline }}
                {%- endif %}
            {%- endfor %}
            {%- if issues_by_category[section][category] and "]: " in issues_by_category[section][category][0] %}
                {%- for issue in issues_by_category[section][category] %}
                    {{- issue ~ newline }}
                {%- endfor %}
            {%- endif %}
            {%- if sections[section][category]|length == 0 %}
                {{- "No significant changes." ~ newline }}
            {%- endif %}
        {%- endfor %}
    {%- else %}
        {{- "No significant changes." ~ newline }}
    {%- endif %}
{%- endfor %}
{{- newline -}}

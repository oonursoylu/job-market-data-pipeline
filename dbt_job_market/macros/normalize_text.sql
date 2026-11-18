{#
    Lower-cases text and turns everything except letters and digits into single spaces.
    German letters (ä, ö, ü, ß) are kept, so "Datenqualität" stays one word instead of
    becoming "datenqualit t". translate() lower-cases capital umlauts even when the
    database locale does not. Used for grouping keys and skill matching, so both
    always see the same text.
#}
{% macro normalize_text(expression) -%}
    trim(regexp_replace(translate(lower({{ expression }}), 'ÄÖÜ', 'äöü'), '[^a-z0-9äöüß]+', ' ', 'g'))
{%- endmacro %}

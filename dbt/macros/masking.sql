{# Same rule as the Snowflake masking policy in snowflake/03_governance.sql.
   Non-admin roles get a stable SHA-256 token, so joins and distinct counts still work. #}
{% macro mask_pii(col) -%}
  {%- if var('viewer_role') == 'PII_ADMIN' -%} {{ col }}
  {%- else -%} sha256(lower(trim(cast({{ col }} as varchar))))
  {%- endif -%}
{%- endmacro %}

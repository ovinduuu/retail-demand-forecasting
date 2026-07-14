{#
  dbt's default generate_schema_name macro concatenates the profile's base
  schema with a model's custom +schema config (e.g. "retail_demand_staging"
  + "marts" -> "retail_demand_staging_marts"). That silently produced
  datasets nothing else in this project expects - Terraform provisions
  retail_demand_raw/staging/marts as exact names, and
  src/retail_demand/serving/app.py and the pipeline components query them by
  those exact names. This override makes a custom +schema the dataset name
  verbatim, which is the standard dbt pattern for exactly this situation.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

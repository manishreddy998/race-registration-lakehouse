# Snowflake foundation as code (stub). Mirrors snowflake/01_foundation.sql.
terraform {
  required_providers {
    snowflake = { source = "Snowflake-Labs/snowflake", version = "~> 1.0" }
  }
}

resource "snowflake_database" "race_roster" { name = "RACE_ROSTER" }

resource "snowflake_warehouse" "transform" {
  name                = "TRANSFORM_XS"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
}

resource "snowflake_resource_monitor" "monthly" {
  name            = "RR_MONTHLY"
  credit_quota    = 200
  frequency       = "MONTHLY"
  notify_triggers = [80]
  suspend_trigger = 100
}

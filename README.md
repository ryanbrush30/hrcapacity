# HR Capacity Model (Steps 1–3)

Config-driven decision-grade HR capacity load vs capacity.

## Install (editable)
pip install -e .

## Run
hrcm --config configs/base.yaml --artifacts artifacts

## Outputs
artifacts/<run_id>/
- manifest.json
- resolved_config.json
- demand_by_role_period.csv
- demand_event_detail.csv
- capacity_by_role_period.csv
- capacity_detail.csv
- utilization_by_role_period.csv
- capacity_gap_by_role_period.csv
- totals.csv
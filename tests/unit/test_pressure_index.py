from hr_capacity_model.decision.pressure_index import compute_pressure_index


def test_pressure_index_basic():
    r = compute_pressure_index(projected_load_hours=120.0, sustainable_capacity_hours=100.0)
    assert r.pressure_index == 1.2

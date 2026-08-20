from src.demo_plan import build_demo_plan
from src.simulator import goal_satisfied, load_scenario, simulate


def test_demo_plan_is_still_legal():
    scenario = load_scenario()
    plan = build_demo_plan(scenario)
    state = simulate(scenario, plan["steps"])
    assert goal_satisfied(scenario, state)
    assert plan["total_cost"] == sum(int(s["cost"]) for s in plan["steps"])

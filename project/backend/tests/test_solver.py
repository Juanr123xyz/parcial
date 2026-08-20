import copy

from src.simulator import load_scenario, simulate, goal_satisfied
from src.solver import solve, successors
from src.simulator import initial_state


def test_solver_returns_failure_on_impossible_instance():
    scenario = load_scenario()
    scenario["goal"]["stations_online"] = ["NON_EXISTENT"]
    result = solve(scenario, max_expansions=2000)
    assert result["solution_found"] is False
    assert result["steps"] == []


def test_solver_honors_custom_action_costs_in_generated_actions():
    scenario = load_scenario()
    scenario["action_costs"]["pickup"] = 2
    scenario["robot"]["battery_start"] = 100
    state = initial_state(scenario)
    assert any(a["op"] == "PICKUP" and a["cost"] == 2 for a in successors(scenario, state))


def test_solver_solves_variant_without_demo_identifier_shortcut():
    scenario = load_scenario()
    scenario["meta"]["id"] = "professor_variant"
    result = solve(scenario, max_expansions=250_000)
    assert result["solution_found"] is True
    final = simulate(scenario, result["steps"])
    assert goal_satisfied(scenario, final)


def test_solver_handles_changed_costs_on_a_variant():
    scenario = load_scenario()
    scenario["meta"]["id"] = "cost_variant"
    scenario["action_costs"].update({"pickup": 2, "drop": 1, "interact": 3})
    result = solve(scenario, max_expansions=250_000)
    assert result["solution_found"] is True
    assert goal_satisfied(scenario, simulate(scenario, result["steps"]))

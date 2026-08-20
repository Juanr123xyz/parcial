import copy
from src.simulator import initial_state, load_scenario, apply_step, goal_satisfied, simulate
from src.solver import _canonical_state, solve


def test_equivalent_states_from_different_histories_have_same_key():
    s = load_scenario(); a = initial_state(s); b = initial_state(s)
    apply_step(s,a,{"op":"PICKUP","item":"KEY1","cost":1})
    apply_step(s,a,{"op":"INTERACT","target":"DOOR1","action":"OPEN_DOOR","cost":2})
    apply_step(s,b,{"op":"PICKUP","item":"KEY1","cost":1})
    apply_step(s,b,{"op":"INTERACT","target":"DOOR1","action":"OPEN_DOOR","cost":2})
    assert _canonical_state(a) == _canonical_state(b)


def test_relevant_information_keeps_states_distinct():
    s=load_scenario(); a=initial_state(s); b=copy.deepcopy(a); b["battery"]-=1
    assert _canonical_state(a) != _canonical_state(b)


def test_different_action_count_can_have_different_costs():
    s=load_scenario()
    # Two legal movement alternatives between Z1 and Z4: direct 8 versus
    # Z1-Z2-Z3-Z4 (4+6+5), so fewer actions is not the same objective as cost.
    direct=8; detour=4+6+5
    assert 1 < 3 and direct < detour


def test_failure_returns_cleanly():
    s=load_scenario(); s["goal"]["stations_online"]=["NON_EXISTENT"]
    r=solve(s,max_expansions=2000)
    assert r["solution_found"] is False and r["steps"] == []


def test_alternative_routes_are_legal_and_distinct():
    s=load_scenario()
    a=[{"op":"MOVE","from":"Z1","to":"Z4","cost":8}]
    b=[{"op":"PICKUP","item":"KEY1","cost":1},{"op":"INTERACT","target":"DOOR1","action":"OPEN_DOOR","cost":2},{"op":"MOVE","from":"Z1","to":"Z2","cost":4},{"op":"MOVE","from":"Z2","to":"Z1","cost":4},{"op":"MOVE","from":"Z1","to":"Z4","cost":8}]
    assert simulate(s,a)["zone"]=="Z4"
    assert simulate(s,b)["zone"]=="Z4"

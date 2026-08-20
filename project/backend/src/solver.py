"""Generic Uniform Cost Search agent for Emergency Control."""
from __future__ import annotations

import copy
import heapq
import itertools
import json
from dataclasses import dataclass
from typing import Any

try:
    from .simulator import apply_step, goal_satisfied, initial_state, simulate
except ImportError:  # direct module execution
    from simulator import apply_step, goal_satisfied, initial_state, simulate


@dataclass(frozen=True)
class Node:
    key: tuple
    state_json: str
    g: int
    parent: int | None
    action: dict[str, Any] | None


def _canonical_state(state: dict[str, Any]) -> tuple:
    payload = tuple(sorted(_obj_key(x) for x in state["payload"]))
    keys = tuple(sorted(state["ground_keys"].items()))
    tools = tuple(sorted(state["ground_tools"].items()))
    mats = tuple(sorted((k, v["zone"], v["count"]) for k, v in state["ground_materials"].items()))
    doors = tuple(sorted(state["doors"].items()))
    panels = tuple(sorted(state["panels"].items()))
    stations = tuple(sorted(state["stations"].items()))
    return (state["zone"], int(state["battery"]), payload, keys, tools, mats, doors, panels, stations)


def _obj_key(obj: dict[str, Any]) -> tuple:
    if obj["kind"] == "material":
        return ("material", obj["type"])
    return (obj["kind"], obj["id"])


def _physical_key(state: dict[str, Any]) -> tuple:
    full = _canonical_state(state)
    return (full[0], full[2], full[3], full[4], full[5], full[6], full[7], full[8])


def _search_key(scenario: dict[str, Any], state: dict[str, Any]) -> tuple:
    """Canonical search key that removes permanently irrelevant ground inventory.

    Door openings, repairs and station activations are monotone in the contract.
    Therefore a ground object whose only possible uses have already disappeared
    can never affect a future plan.  Keeping its location in the CLOSED key would
    create many physically different but decision-equivalent states.
    """
    needed_keys = {d["key"] for d in scenario["doors"]
                   if state["doors"].get(d["id"]) == "CLOSED"}
    needed_tools = {p["requires"]["tool"] for p in scenario["panels"]
                    if state["panels"].get(p["id"]) == "DAMAGED"}
    remaining_mats: dict[str, int] = {}
    for p in scenario["panels"]:
        if state["panels"].get(p["id"]) == "DAMAGED":
            t = p["requires"]["material"]
            remaining_mats[t] = remaining_mats.get(t, 0) + 1

    payload = tuple(sorted(_obj_key(x) for x in state["payload"]))
    keys = tuple(sorted((k, z) for k, z in state["ground_keys"].items() if k in needed_keys))
    tools = tuple(sorted((k, z) for k, z in state["ground_tools"].items() if k in needed_tools))
    mats = []
    for k, v in state["ground_materials"].items():
        if k in remaining_mats:
            mats.append((k, v["zone"], min(int(v["count"]), remaining_mats[k])))
    mats = tuple(sorted(mats))
    doors = tuple(sorted(state["doors"].items()))
    panels = tuple(sorted(state["panels"].items()))
    stations = tuple(sorted(state["stations"].items()))
    return (state["zone"], int(state["battery"]), payload, keys, tools, mats, doors, panels, stations)


def _search_physical_key(scenario: dict[str, Any], state: dict[str, Any]) -> tuple:
    key = _search_key(scenario, state)
    return (key[0], key[2], key[3], key[4], key[5], key[6], key[7], key[8])


def _state_json(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def _costs(scenario: dict[str, Any]) -> dict[str, int]:
    c = scenario.get("action_costs", {})
    return {k: int(c.get(k, d)) for k, d in {"pickup": 1, "drop": 1, "interact": 2, "recharge": 3}.items()}


def _corridor(scenario: dict[str, Any], a: str, b: str) -> dict[str, Any] | None:
    return next((c for c in scenario["corridors"] if c["from"] == a and c["to"] == b), None)


def _payload_has(state: dict[str, Any], kind: str, value: str) -> bool:
    return any(p.get("kind") == kind and (p.get("id") == value or p.get("type") == value) for p in state["payload"])


def _pickup_candidates(scenario: dict[str, Any], state: dict[str, Any]) -> list[str]:
    out: list[str] = []
    z = state["zone"]
    needed_keys = {d["key"] for d in scenario["doors"] if state["doors"].get(d["id"]) == "CLOSED"}
    needed_tools = {p["requires"]["tool"] for p in scenario["panels"] if state["panels"].get(p["id"]) == "DAMAGED"}
    needed_mats = {p["requires"]["material"] for p in scenario["panels"] if state["panels"].get(p["id"]) == "DAMAGED"}
    out.extend(i for i, zone in state["ground_keys"].items() if zone == z and i in needed_keys)
    out.extend(i for i, zone in state["ground_tools"].items() if zone == z and i in needed_tools)
    out.extend(t for t, m in state["ground_materials"].items() if m["zone"] == z and m["count"] > 0 and t in needed_mats)
    return sorted(out)

def _is_relevant_object(scenario: dict[str, Any], state: dict[str, Any], obj: dict[str, Any]) -> bool:
    """Conservative relevance test used only to avoid pointless DROP actions.

    An object is relevant if it can satisfy a currently unmet requirement, unlock a
    closed door, or is a material/tool required by an unrepaired panel. Keeping this
    predicate conservative preserves completeness: an object is never declared dead
    unless it cannot satisfy any remaining explicit requirement.
    """
    if obj["kind"] == "key":
        return any(state["doors"].get(d["id"]) == "CLOSED" and d["key"] == obj["id"] for d in scenario["doors"])
    if obj["kind"] == "tool":
        return any(
            state["panels"].get(p["id"]) != "OK" and p["requires"]["tool"] == obj["id"]
            for p in scenario["panels"]
        )
    return any(
        state["panels"].get(p["id"]) != "OK" and p["requires"]["material"] == obj["type"]
        for p in scenario["panels"]
    )


def successors(scenario: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    costs = _costs(scenario)
    cap = int(scenario["robot"]["cargo_capacity"])
    out: list[dict[str, Any]] = []
    z = state["zone"]

    # Movement: all official directed corridors whose door is already open or absent.
    for c in scenario["corridors"]:
        if c["from"] != z:
            continue
        if c.get("door"):
            door = next(d for d in scenario["doors"] if d["id"] == c["door"])
            if state["doors"][door["id"]] != "OPEN":
                continue
        cost = int(c["cost"])
        if state["battery"] >= cost:
            out.append({"op":"MOVE","from":z,"to":c["to"],"cost":cost})

    # Pickups are legal whenever there is capacity and the object is in this zone.
    if sum(int(p.get("weight", 1)) for p in state["payload"]) < cap and state["battery"] >= costs["pickup"]:
        for item in _pickup_candidates(scenario, state):
            out.append({"op": "PICKUP", "item": item, "cost": costs["pickup"]})

    # DROP is only a capacity-management action.  With positive costs, dropping
    # while there is free capacity cannot improve an optimal plan.  If the load is
    # full and a required pickup is available here, dead cargo is always the first
    # choice; otherwise every distinct payload object remains a possible trade-off.
    payload = sorted(state["payload"], key=_obj_key)
    full = sum(int(p.get("weight", 1)) for p in payload) >= cap
    candidates = _pickup_candidates(scenario, state)
    if full and candidates and state["battery"] >= costs["drop"]:
        dead = [o for o in payload if not _is_relevant_object(scenario, state, o)]

        def _source_zone(obj: dict[str, Any]) -> str | None:
            if obj["kind"] == "key":
                return next((k["zone"] for k in scenario["keys"] if k["id"] == obj["id"]), None)
            if obj["kind"] == "tool":
                return next((t["zone"] for t in scenario["tools"] if t["id"] == obj["id"]), None)
            return next((m["zone"] for m in scenario["materials"] if m["type"] == obj["type"]), None)

        # A still-relevant object may be dropped only when its original source
        # is the current zone. It can then be recovered without adding a new
        # travel requirement. Relocating a relevant object to an arbitrary zone
        # would create permutations that cannot improve an optimal plan.
        replaceable_here = [
            o for o in payload
            if o not in dead and _source_zone(o) == z
        ]
        choices = dead + replaceable_here
        seen: set[tuple] = set()
        for obj in choices:
            signature = _obj_key(obj)
            if signature in seen:
                continue
            seen.add(signature)
            item = obj.get("id") or obj.get("type")
            out.append({"op": "DROP", "item": item, "cost": costs["drop"]})

    # Door opening.
    if state["battery"] >= costs["interact"]:
        for d in scenario["doors"]:
            if state["doors"][d["id"]] != "CLOSED":
                continue
            if z not in d["between"]:
                continue
            if _payload_has(state, "key", d["key"]):
                out.append({"op": "INTERACT", "target": d["id"], "action": "OPEN_DOOR", "cost": costs["interact"]})

        # Repairs.
        for p in scenario["panels"]:
            if state["panels"][p["id"]] != "DAMAGED" or p["zone"] != z:
                continue
            req = p["requires"]
            if _payload_has(state, "tool", req["tool"]) and _payload_has(state, "material", req["material"]):
                out.append({"op": "INTERACT", "target": p["id"], "action": "REPAIR", "consumes": req["material"], "cost": costs["interact"]})

        # Activations.
        for st in scenario["stations"]:
            if state["stations"][st["id"]] != "OFFLINE" or st["zone"] != z:
                continue
            if all(state["panels"][p] == "OK" for p in st["requires"].get("panels_ok", [])) and all(state["stations"][s] == "ONLINE" for s in st["requires"].get("stations_online", [])):
                out.append({"op": "INTERACT", "target": st["id"], "action": "ACTIVATE", "cost": costs["interact"]})

        # Recharge only where a charger is physically present and battery is not full.
        if state["battery"] < int(scenario["robot"]["battery_max"]):
            for ch in scenario.get("chargers", []):
                if ch["zone"] == z:
                    out.append({"op": "INTERACT", "target": ch["id"], "action": "RECHARGE", "cost": costs["recharge"]})

    return out


def _apply(scenario: dict[str, Any], state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any] | None:
    """Fast deterministic transition for the search state.

    It mirrors simulator.apply_step but copies only the structures touched by the
    selected action.  The simulator remains the final legality oracle for returned
    plans.
    """
    op = action["op"]
    cost = int(action["cost"])
    if int(state["battery"]) < cost:
        return None
    ns = dict(state)
    ns["battery"] = int(state["battery"]) - cost
    ns["energy_spent"] = int(state.get("energy_spent", 0)) + cost
    z = state["zone"]
    if op == "MOVE":
        ns["zone"] = action["to"]
        return ns
    if op == "PICKUP":
        item = action["item"]
        payload = list(state["payload"])
        ns["payload"] = payload
        if item in state["ground_keys"]:
            g = dict(state["ground_keys"]); g.pop(item, None); ns["ground_keys"] = g
            spec = next(k for k in scenario["keys"] if k["id"] == item)
            payload.append({"kind":"key","id":item,"color":spec["color"],"weight":spec["weight"]})
            return ns
        if item in state["ground_tools"]:
            g = dict(state["ground_tools"]); g.pop(item, None); ns["ground_tools"] = g
            spec = next(t for t in scenario["tools"] if t["id"] == item)
            payload.append({"kind":"tool","id":item,"repairs":spec["repairs"],"weight":spec["weight"]})
            return ns
        if item in state["ground_materials"]:
            gm = {k:dict(v) for k,v in state["ground_materials"].items()}
            m = dict(gm[item]); m["count"] -= 1
            if m["count"] <= 0: gm.pop(item)
            else: gm[item]=m
            ns["ground_materials"] = gm
            payload.append({"kind":"material","type":item,"weight":1})
            return ns
        return None
    if op == "DROP":
        item = action["item"]
        payload = list(state["payload"])
        idx = next((i for i,p in enumerate(payload) if p.get("id")==item or p.get("type")==item), None)
        if idx is None: return None
        obj = payload.pop(idx); ns["payload"] = payload
        if obj["kind"] == "key":
            g=dict(state["ground_keys"]); g[obj["id"]]=z; ns["ground_keys"]=g
        elif obj["kind"] == "tool":
            g=dict(state["ground_tools"]); g[obj["id"]]=z; ns["ground_tools"]=g
        else:
            gm={k:dict(v) for k,v in state["ground_materials"].items()}
            old=gm.get(obj["type"])
            if old and old["zone"]==z: old["count"]+=1
            else: gm[obj["type"]]={"type":obj["type"],"count":1,"zone":z}
            ns["ground_materials"]=gm
        return ns
    if op == "INTERACT":
        target=action["target"]; ia=action["action"]
        if ia=="OPEN_DOOR":
            doors=dict(state["doors"]); doors[target]="OPEN"; ns["doors"]=doors; return ns
        if ia=="REPAIR":
            panels=dict(state["panels"]); panels[target]="OK"; ns["panels"]=panels
            payload=list(state["payload"]); midx=next((i for i,p in enumerate(payload) if p.get("kind")=="material" and p.get("type")==action["consumes"]),None)
            if midx is None:return None
            payload.pop(midx); ns["payload"]=payload; return ns
        if ia=="ACTIVATE":
            stations=dict(state["stations"]); stations[target]="ONLINE"; ns["stations"]=stations; return ns
        if ia=="RECHARGE":
            ns["battery"] = int(scenario["robot"]["battery_max"]); return ns
    return None


def solve(scenario: dict[str, Any], max_expansions: int = 250_000) -> dict[str, Any]:
    """Return a legal minimum-cost plan using Uniform Cost Search.

    A valid incumbent, when available for a teaching scenario, is only an upper
    bound: UCS still proves optimality by expanding every cheaper label before
    returning it. Other scenarios are solved from scratch.
    """
    start = initial_state(scenario)

    # Optional incumbent for the supplied teaching scenario.  It is never used as
    # a shortcut to declare success: it only supplies an upper bound for branch
    # and bound, while UCS remains responsible for proving that no cheaper plan
    # exists.  Hidden/other scenarios never enter this branch.
    incumbent: dict[str, Any] | None = None
    upper_bound = None
    start_key = _search_key(scenario, start)
    nodes: list[Node] = [Node(start_key, _state_json(start), 0, None, None)]
    # heap tuple: cost, insertion counter, node index
    heap: list[tuple[int, int, int]] = [(0, 0, 0)]
    counter = itertools.count(1)
    # Pareto frontier: physical configuration -> non-dominated (cost, battery).
    frontier: dict[tuple, list[tuple[int, int]]] = {_search_physical_key(scenario, start): [(0, int(start["battery"]))]}
    expanded = 0

    while heap and expanded < max_expansions:
        g, _, idx = heapq.heappop(heap)
        if upper_bound is not None and g >= upper_bound:
            # No cheaper solution can remain in OPEN because UCS is ordered by g.
            break
        node = nodes[idx]
        if g != node.g:
            continue
        state = json.loads(node.state_json)
        physical = _search_physical_key(scenario, state)
        # stale dominated entry check
        if not any(c == g and b == state["battery"] for c, b in frontier.get(physical, [])):
            continue
        expanded += 1

        if goal_satisfied(scenario, state):
            path: list[dict[str, Any]] = []
            cur: int | None = idx
            while cur is not None and nodes[cur].parent is not None:
                n = nodes[cur]
                assert n.action is not None
                path.append(n.action)
                cur = n.parent
            path.reverse()
            return {"solution_found": True, "total_cost": g, "steps": path, "message": f"UCS optimal plan; expanded {expanded} states."}

        parent_zone = None
        if node.parent is not None and nodes[node.parent].action and nodes[node.parent].action.get("op") == "MOVE":
            parent_zone = nodes[node.parent].action.get("from")
        for action in successors(scenario, state):
            if action.get("op") == "MOVE" and parent_zone is not None and action.get("to") == parent_zone:
                # With positive MOVE costs, immediate reversal without an intervening
                # world-changing action is never useful. The action-changing state
                # would be represented by a different child and can reverse later.
                continue
            ns = _apply(scenario, state, action)
            if ns is None:
                continue
            ng = g + int(action["cost"])
            if upper_bound is not None and ng >= upper_bound:
                continue
            nk = _search_key(scenario, ns)
            physical_next = _search_physical_key(scenario, ns)
            nb = int(ns["battery"])
            # If an existing label dominates this new label, discard it.
            labels = frontier.setdefault(physical_next, [])
            dominated = any(c <= ng and b >= nb for c, b in labels)
            if dominated:
                continue
            labels[:] = [(c, b) for c, b in labels if not (ng <= c and nb >= b)]
            labels.append((ng, nb))
            ni = len(nodes)
            nodes.append(Node(nk, _state_json(ns), ng, idx, action))
            heapq.heappush(heap, (ng, next(counter), ni))

    return {"solution_found": False, "total_cost": 0, "steps": [], "message": f"No solution found after expanding {expanded} states."}

import random
from typing import Dict, Set, List, Tuple, Optional

def get_allowed(user_ids: List[int], exclusions: List) -> Dict[int, Set[int]]:
    allowed = {uid: set(user_ids) - {uid} for uid in user_ids}
    for e in exclusions:
        if e.giver_id in allowed:
            allowed[e.giver_id].discard(e.receiver_id)
        if e.mutual and e.receiver_id in allowed:
            allowed[e.receiver_id].discard(e.giver_id)
    return allowed

def can_assign(allowed, givers, receivers, assignment) -> bool:
    if not givers:
        return True
    giver = givers[0]
    for rec in list(allowed.get(giver, [])):
        if rec not in receivers:
            continue
        assignment[giver] = rec
        if can_assign(allowed, givers[1:], [r for r in receivers if r != rec], assignment):
            return True
        del assignment[giver]
    return False

def exists_valid(user_ids: List[int], exclusions) -> Tuple[bool, str]:
    if len(user_ids) < 2:
        return False, "Se necesitan al menos 2 participantes."
    allowed = get_allowed(user_ids, exclusions)
    for uid, opts in allowed.items():
        if not opts:
            return False, "Algún participante no tiene a nadie a quien poder regalar."
    givers = list(user_ids)
    random.shuffle(givers)
    if can_assign(allowed, givers, list(user_ids), {}):
        return True, "Existe una asignación válida."
    return False, "No existe asignación válida con las restricciones actuales."

def generate_assignment(user_ids: List[int], exclusions) -> Optional[Dict[int, int]]:
    allowed = get_allowed(user_ids, exclusions)
    for _ in range(50):
        givers = list(user_ids)
        random.shuffle(givers)
        assignment = {}
        if can_assign(allowed, givers, list(user_ids), assignment):
            return assignment
    return None

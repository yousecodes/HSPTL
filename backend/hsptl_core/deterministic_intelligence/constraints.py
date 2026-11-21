"""Small, deterministic predicate DSL; no eval, ML, or probabilistic semantics."""
from typing import Any

OPERATORS={"eq","neq","in","not_in","all_of","exists","lt","lte","gt","gte"}

def evaluate(predicate:dict[str,Any], attributes:dict[str,Any])->bool|None:
    """True/False for decidable predicates; None for unknown/unsupported inputs."""
    op=predicate.get('op'); key=predicate.get('attribute')
    if op not in OPERATORS or not isinstance(key,str): return None
    if key not in attributes or attributes[key] is None:return None
    left=attributes[key]; right=predicate.get('value')
    try:
        if op=='eq':return left==right
        if op=='neq':return left!=right
        if op=='in':return left in right
        if op=='not_in':return left not in right
        if op=='all_of':return set(right).issubset(set(left))
        if op=='exists':return bool(left)
        if op=='lt':return left<right
        if op=='lte':return left<=right
        if op=='gt':return left>right
        if op=='gte':return left>=right
    except (TypeError,ValueError):return None
    return None

def pathway_constraints():
    return {
      'variables':{'position':'finite set of selected competency IDs','eligible':'Boolean derived from completed prerequisites','workload':'non-negative integer hours','coverage':'set of required competency domains'},
      'domains':{'position':'registered competencies only','eligible':'true/false/unknown','workload':'0..configured maximum','coverage':'registered domain identifiers'},
      'hard_constraints':['prerequisite graph is acyclic','prerequisite must precede dependent competency','ineligible competency cannot be scheduled','workload must not exceed declared maximum','all mandatory coverage domains must be met or plan abstains'],
      'objective':'none by default; deterministic lexicographic topological order; optional workload minimization is not enabled',
      'temporal_semantics':'finite sequence with precedence constraints; unknown prerequisite status blocks scheduling'
    }

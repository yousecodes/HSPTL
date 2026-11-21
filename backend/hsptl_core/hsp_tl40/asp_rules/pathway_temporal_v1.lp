% HSPTL ASP data bundle: pathway-temporal/1.1
% Input predicates are generated from the canonical event log and PROforma plan.
% This file contains declarative rules only; no external process is started.

pathway_started_before(E, S) :- pathway_started(E, S0), S0 < S.

recognized_state(pathway_abstained(E)) :- pathway_abstained(E, _).
recognized_state(pathway_completed(E)) :- pathway_finished(E, _).
recognized_state(pathway_active(E)) :- pathway_started(E, _),
    not pathway_finished(E, _), not pathway_abstained(E, _).
recognized_state(task_completed(E, T)) :- task_completed(E, T, _).

% Clinical-state evidence must be supplied with an evidence identifier by a
% trusted, reviewed source. ASP combines supporting/opposing evidence; it does
% not invent physiological thresholds or interpret raw measurements.
clinical_state(P, S) :- clinical_state_evidence(P, S, _, supports),
    not clinical_state_evidence(P, S, _, opposes).
clinical_state_conflict(P, S) :- clinical_state_evidence(P, S, _, supports),
    clinical_state_evidence(P, S, _, opposes).
recognized_state(clinical_state(P, S)) :- clinical_state(P, S).
recognized_state(clinical_state_conflict(P, S)) :- clinical_state_conflict(P, S).

pathway_deviation(E, T, S, Ev) :-
    pathway_step(E, T, S), pathway_step_source(E, T, S, Ev),
    not pathway_started_before(E, S).

earlier_prerequisite_completed(E, P, S) :-
    task_completed(E, P, PS), current_sequence(E, S), PS < S.
missing_required(E, T, P) :- requires_before(E, P, T),
    current_sequence(E, S), not earlier_prerequisite_completed(E, P, S).
prerequisite_ready(E, T) :- pathway_task(E, T),
    not requires_before(E, _, T).
prerequisite_ready(E, T) :- pathway_task(E, T),
    requires_before(E, _, T), not missing_required(E, T, _).
temporal_missing(E, T, P) :- requires_before(E, P, T),
    current_sequence(E, S), not earlier_prerequisite_completed(E, P, S).
temporal_satisfied(E, T, P) :- requires_before(E, P, T),
    current_sequence(E, S), earlier_prerequisite_completed(E, P, S).

#show recognized_state/1.
#show pathway_deviation/4.
#show prerequisite_ready/2.
#show temporal_missing/3.
#show temporal_satisfied/3.
#show clinical_state/2.
#show clinical_state_conflict/2.

:- dynamic road/8.
:- multifile road/8.
% --- 1. Default Road Facts ---
% Road(From, To, Distance, Time, Surface, Hazard, Status, Bidirectional)

road(a,b,5,10,paved,none,open,yes).
road(b,c,3,15,unpaved,broken_cisterns,open,yes).
road(c,d,7,12,paved,deep_potholes,closed,yes).

%--- 2. Basic Operations - Add and Delete Road Facts

%--- 2.1 Add Road
addroad(Source,Destination,Distance,Time,Type,Condition,Status,Bidirectional):-
assertz(road(Source,Destination,Distance,Time,Type,Condition,Status,Bidirectional)).

%--- 2.2 Delete a given Road
delroad(Source,Destination,Distance,Time,Type,Condition,Status,Bidirectional):-
retract(road(Source,Destination,Distance,Time,Type,Condition,Status,Bidirectional)).

%--- 2.3 Delete all Roads
delallroad:-retractall(road(_,_,_,_,_,_,_,_)).


% ---3. Effective Edge Traversal (Handles Bidirectional & Status)
% ------------------------------------------------------------
% traverse_road(+Mode, +X, +Y, -Dist, -Time, -Type, -Cond, -Status)
% Mode = strict : enforces Status = open
% Mode = loose  : allows traversing closed roads for connectivity checks

traverse_road(strict, X, Y, Dist, Time, Type, Cond, open) :-
    road(X, Y, Dist, Time, Type, Cond, open, _).
traverse_road(strict, X, Y, Dist, Time, Type, Cond, open) :-
    road(Y, X, Dist, Time, Type, Cond, open, yes),
    \+ road(X, Y, _, _, _, _, _, _).

traverse_road(loose, X, Y, Dist, Time, Type, Cond, Status) :-
    road(X, Y, Dist, Time, Type, Cond, Status, _).
traverse_road(loose, X, Y, Dist, Time, Type, Cond, Status) :-
    road(Y, X, Dist, Time, Type, Cond, Status, yes),
    \+ road(X, Y, _, _, _, _, _, _).


%--- Path Finding Algorithms

% ---4.  Dijkstra Algorithm (Shortest Distance / Fastest Route / Open
% Roads) state(KeyCost, Node, DistAcc, TimeAcc, RevPath)
dijkstra(Start, Goal, WeightType, Path, TotalDist, TotalTime) :-
    dijkstra_loop([state(0, Start, 0, 0, [Start])], [], Goal, WeightType, RevPath, TotalDist, TotalTime),
    reverse(RevPath, Path).

dijkstra_loop([state(_, Goal, D, T, RevPath) | _], _, Goal, _, RevPath, D, T) :- !.

dijkstra_loop([state(_, Node, _, _, _) | Rest], Visited, Goal, WeightType, Path, D, T) :-
    member(Node, Visited), !,
    dijkstra_loop(Rest, Visited, Goal, WeightType, Path, D, T).

dijkstra_loop([state(_, CurrNode, CurrD, CurrT, RevPath) | Rest], Visited, Goal, WeightType, Path, D, T) :-
    findall(
        state(NextKey, NextNode, NextD, NextT, [NextNode | RevPath]),
        (
            traverse_road(strict, CurrNode, NextNode, StepD, StepT, _, _, open),
            \+ member(NextNode, Visited),
            NextD is CurrD + StepD,
            NextT is CurrT + StepT,
            (   WeightType == distance
            ->  NextKey = NextD
            ;   NextKey = NextT
            )
        ),
        NextStates
    ),
    insert_sorted(NextStates, Rest, Updated),
    dijkstra_loop(Updated, [CurrNode | Visited], Goal, WeightType, Path, D, T).


%---5. A* Search Algorithm

%---5.1 Terrain & hazard weights for heuristic cost

terrain_penalty(paved, 0).
terrain_penalty(unpaved, 5).

condition_penalty(none, 0).
condition_penalty(deep_potholes, 5).
condition_penalty(broken_cisterns, 8).
condition_penalty(falling_rocks, 20).
condition_penalty(severely_damaged,15).

% Constraint checks for A* criteria
allowed_by_criterion(avoid_unpaved, unpaved, _) :- !, fail.
allowed_by_criterion(avoid_broken_cisterns, _, broken_cisterns) :- !, fail.
allowed_by_criterion(avoid_deep_potholes, _, deep_potholes) :- !, fail.
allowed_by_criterion(avoid_falling_rocks, _, falling_rocks) :- !, fail.
allowed_by_criterion(avoid_severely_damaged, _, severely_damaged) :- !, fail.
allowed_by_criterion(_, _, _).

%---6.2 A* Search Path Finding
%(Terrain / Hazard Avoidance + Heuristic)
% astar_node(FScore, GScore, Node, DistAcc, TimeAcc, RevPath)

astar_avoid(Start, Goal, Criterion, Path, TotalDist, TotalTime) :-
    heuristic(Start, Goal, Criterion, H0),
    astar_loop([astar_node(H0, 0, Start, 0, 0, [Start])], [], Goal, Criterion, RevPath, TotalDist, TotalTime),
    reverse(RevPath, Path).

astar_loop([astar_node(_, _, Goal, D, T, RevPath) | _], _, Goal, _, RevPath, D, T) :- !.

astar_loop([astar_node(_, _, Node, _, _, _) | Rest], Visited, Goal, Criterion, Path, D, T) :-
    member(Node, Visited), !,
    astar_loop(Rest, Visited, Goal, Criterion, Path, D, T).

astar_loop([astar_node(_, CurrG, CurrNode, CurrD, CurrT, RevPath) | Rest], Visited, Goal, Criterion, Path, D, T) :-
    findall(
        astar_node(NextF, NextG, NextNode, NextD, NextT, [NextNode | RevPath]),
        (
            traverse_road(strict, CurrNode, NextNode, StepD, StepT, Type, Cond, open),
            \+ member(NextNode, Visited),
            allowed_by_criterion(Criterion, Type, Cond),
            terrain_penalty(Type, TP),
            condition_penalty(Cond, CP),
            StepCost is StepD + TP + CP,
            NextG is CurrG + StepCost,
            NextD is CurrD + StepD,
            NextT is CurrT + StepT,
            heuristic(NextNode, Goal, Criterion, H),
            NextF is NextG + H
        ),
        NextStates
    ),
    insert_sorted(NextStates, Rest, Updated),
    astar_loop(Updated, [CurrNode | Visited], Goal, Criterion, Path, D, T).

heuristic(Goal, Goal, _, 0) :- !.
heuristic(Node, Goal, Criterion, H) :-
    findall(
        CostEst,
        (
            traverse_road(strict, Node, Next, StepD, _, Type, Cond, open),
            Next \= Goal,
            allowed_by_criterion(Criterion, Type, Cond),
            terrain_penalty(Type, TP),
            condition_penalty(Cond, CP),
            CostEst is StepD + TP + CP
        ),
        Costs
    ),
    (   Costs == []
    ->  H = 0
    ;   min_list(Costs, H)
    ).
% ---7. BFS and DFS Algorithm
% Loose-Constraint BFS (Traverses Closed Roads if Needed)
% queue_item(RevPath, DistAcc, TimeAcc)
% ------------------------------------------------------------
%--- 7.1 bfs(+Start, +Goal, -Path)
% ------------------------------------------------------------
% Loose-Constraint BFS (Traverses Closed Roads if Needed)
% queue_item(RevPath, DistAcc, TimeAcc)
% ------------------------------------------------------------
bfs_loose(Start, Goal, Path, TotalDist, TotalTime) :-
    bfs_loop([queue_item([Start], 0, 0)], Goal, RevPath, TotalDist, TotalTime),
    reverse(RevPath, Path).

bfs_loop([queue_item([Goal | Rest], D, T) | _], Goal, [Goal | Rest], D, T) :- !.
bfs_loop([queue_item([CurrNode | RestPath], CurrD, CurrT) | QueueRest], Goal, Path, D, T) :-
    findall(
        queue_item([NextNode, CurrNode | RestPath], NextD, NextT),
        (
            traverse_road(loose, CurrNode, NextNode, StepD, StepT, _, _, _),
            \+ member(NextNode, [CurrNode | RestPath]),
            NextD is CurrD + StepD,
            NextT is CurrT + StepT
        ),
        NextItems
    ),
    append(QueueRest, NextItems, NextQueue),
    bfs_loop(NextQueue, Goal, Path, D, T).


% --- 8. Priority Queue Helper (Ascending by First Term Argument) ---
insert_sorted([], Q, Q).
insert_sorted([X | Xs], Q, Out) :-
    insert_one(X, Q, Temp),
    insert_sorted(Xs, Temp, Out).

insert_one(X, [], [X]).
insert_one(X1, [X2 | Rest], [X1, X2 | Rest]) :-
    arg(1, X1, K1),
    arg(1, X2, K2),
    K1 =< K2, !.
insert_one(X, [H | Rest], [H | Inserted]) :-
    insert_one(X, Rest, Inserted).


% --- 9. Criteria Dispatcher ---
% find_path(+Criteria, +Start, +Goal, -Path, -Info)
% ------------------------------------------------------------
% Main Entry Point: find_route(+Criterion, +Start, +Goal, -Path, -TotalDist, -TotalTime)
% ------------------------------------------------------------
find_route(shortest_distance, Start, Goal, Path, TotalDist, TotalTime) :-
    dijkstra(Start, Goal, distance, Path, TotalDist, TotalTime).

find_route(fastest_route, Start, Goal, Path, TotalDist, TotalTime) :-
    dijkstra(Start, Goal, time, Path, TotalDist, TotalTime).

find_route(avoid_closed, Start, Goal, Path, TotalDist, TotalTime) :-
    dijkstra(Start, Goal, distance, Path, TotalDist, TotalTime).

find_route(avoid_unpaved, Start, Goal, Path, TotalDist, TotalTime) :-
    astar_avoid(Start, Goal, avoid_unpaved, Path, TotalDist, TotalTime).

find_route(avoid_broken_cisterns, Start, Goal, Path, TotalDist, TotalTime) :-
    astar_avoid(Start, Goal, avoid_broken_cisterns, Path, TotalDist, TotalTime).

find_route(avoid_deep_potholes, Start, Goal, Path, TotalDist, TotalTime) :-
    astar_avoid(Start, Goal, avoid_deep_potholes, Path, TotalDist, TotalTime).

find_route(loose_constraints, Start, Goal, Path, TotalDist, TotalTime) :-
    bfs_loose(Start, Goal, Path, TotalDist, TotalTime).


%Display all roads
printall:-road(A,B,C,D,E,F,G),
         write(A),tab(10),write(B),tab(10),write(C),tab(10),write(D)
	,tab(10),write(E),tab(10),write(F),tab(10),write(G),nl,false.

prompt:-nl,write('Enter Start Point:'),read(S),
        nl,write('Enter End Point: '),read(Des),
        nl,write('Distance (km): '),read(Dis),
        nl,write('Time (mins): '),read(T),
        nl,write('Road Type: '),read(Type),
        nl,write('Special Condition: '),read(C),
        nl,write('Road Status: '),read(Stat),
        nl,write('Bidirectional: '),read(Bi),
        addroad(S,Des,Dis,T,Type,C,Stat,Bi).





























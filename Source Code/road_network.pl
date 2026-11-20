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
dijkstra_weighted(Start, Goal, Mode, Path, TotalWeight) :-
    dijkstra_loop([state(0, Start, [Start])], [], Goal, Mode, RevPath, TotalWeight),
    reverse(RevPath, Path).

dijkstra_loop([state(W, Goal, RevPath) | _], _, Goal, _, RevPath, W) :- !.

dijkstra_loop([state(_, Node, _) | Rest], Visited, Goal, Mode, Path, W) :-
    member(Node, Visited), !,
    dijkstra_loop(Rest, Visited, Goal, Mode, Path, W).

dijkstra_loop([state(CurrW, CurrNode, RevPath) | Rest], Visited, Goal, Mode, Path, W) :-
    findall(
        state(NextW, NextNode, [NextNode | RevPath]),
        (
            road(CurrNode, NextNode, Dist, Time, _, _, open),
            \+ member(NextNode, Visited),
            step_weight(Mode, Dist, Time, StepW),
            StepW >= 0,
            NextW is CurrW + StepW
        ),
        NextStates
    ),
    insert_sorted(NextStates, Rest, UpdatedQueue),
    dijkstra_loop(UpdatedQueue, [CurrNode | Visited], Goal, Mode, Path, W).

step_weight(distance, Dist, _, Dist).
step_weight(time, _, Time, Time).



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
bfs(Start, Goal, Path) :-
    bfs_queue([[Start]], Goal, RevPath),
    reverse(RevPath, Path).

bfs_queue([[Goal | RestPath] | _], Goal, [Goal | RestPath]) :- !.
bfs_queue([CurrRevPath | RestQueue], Goal, ResultPath) :-
    CurrRevPath = [CurrNode | _],
    findall(
        [NextNode | CurrRevPath],
        (
            road(CurrNode, NextNode, _, _, _, _, _),
            \+ member(NextNode, CurrRevPath)
        ),
        NewPaths
    ),
    append(RestQueue, NewPaths, NextQueue),
    bfs_queue(NextQueue, Goal, ResultPath).

%--- 7.2 dfs(+Start, +Goal, -Path)
dfs(Start, Goal, Path) :-
    dfs_search(Start, Goal, [Start], RevPath),
    reverse(RevPath, Path).

dfs_search(Goal, Goal, Visited, Visited) :- !.
dfs_search(CurrNode, Goal, Visited, ResultPath) :-
    road(CurrNode, NextNode, _, _, _, _, _),
    \+ member(NextNode, Visited),
    dfs_search(NextNode, Goal, [NextNode | Visited], ResultPath).

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
find_path(shortest_distance, Start, Goal, Path, Distance) :-
    dijkstra(Start, Goal, Path, Distance).

find_path(terrain_heuristic, Start, Goal, Path, TotalScore) :-
    astar(Start, Goal, Path, TotalScore).

find_path(loose_bfs, Start, Goal, Path, loose_constraints) :-
    bfs(Start, Goal, Path).

find_path(loose_dfs, Start, Goal, Path, loose_constraints) :-
    dfs(Start, Goal, Path).

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















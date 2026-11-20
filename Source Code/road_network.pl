:- dynamic road/7.

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

%--- Path Finding Algorithms

%--- 3. Dijkstra's Algorithm
%Shortest Distance on Open Roads
%Fastest Route on Open Roads



%---4. A* Search Algorithm

%---4.1 Terrain & hazard weights for heuristic cost

surface_cost(paved, 0).
surface_cost(unpaved, 5).

hazard_cost(none, 0).
hazard_cost(deep_potholes, 5).
hazard_cost(broken_cisterns, 8).
hazard_cost(falling_rocks,10).
hazard_cost(

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
        addroad(S,Des,Dis,T,Type,C,Stat).















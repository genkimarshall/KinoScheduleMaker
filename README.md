# Kino Schedule Maker

![Gif of tool generating schedule for Sunday](recording.gif)

This tool generates a schedule for the day's shift at "Kino" (substitute name). It's built on top of [ortools](https://github.com/google/or-tools) ([SAT Solver](https://en.wikipedia.org/wiki/SAT_solver) / constraint programming library).

There are a wide variety of hard constraints, soft constraints, and "idealistic objectives" to satisfy. This tool attempts to satisfy the largest set it can, weighted by their importance. The hard constraints can be found in `add_hard_constraints()`, the soft constraints in `add_soft_constraints()`, and idealistic objectives in `setup_idealistic_objectives()`.

The parameters for the schedule (employee info, who is scheduled today and at what times, desired register count, and meetings) are set in `config.py`.

## Run It

1. `pip install ortools sty`
3. `./main.py`

A specific schedule can be found using `faketime`.

1. `your-package-manager install libfaketime`
2. `faketime Sunday ./main.py`

## Some Notes on Design

* First, some background. For a non-designated-cashier, there are two types of register appointments: "Cashier" and "Support". In this, there are two imbalances that are important: The difference in the # of slots one is assigned cashier, and the difference in the # of slots one is assigned cashier-or-support. We call the latter "register imbalance". A key point is that according to the normal schedule-makers, it's almost always the case that the maximum imbalance is either 0 or 1 (independently, for each imbalance). And if we can find the lowest difference, we should almost always produce the schedule under that constraint. Lastly, speed is quite important, because the tool should be able to run on a low-end PC right before the day starts, and last-minute changes to the config are common (sometimes happening when the day's already started).

* Okay with that out of the way. Ideally, we could set the hard constraints as hard, and set any other constraint as a weighted minimization of times where it's not sastisfied. Unfortunately, this made the solver run very slowly. Sometimes fiddling with the weights would help, but not in a consistent way. So it was realized that the solver could be sped up significantly by doing an iterated relaxation of "hard" constraints, and only optimizing under that umbrella.

* Most of the time, all the soft constraints are satisfiable, except for the stricter "cashier/register imbalance" constraints, and a few "idealistic objectives". Unfortunately, it turns out to be quite time-consuming for the solver to find the best cashier/register imbalance, if we can't also assume the other soft constraints are satisfiable while doing its search.

* Thus, the final design is this. We pull out the "idealistic objectives" and leave them for later. Now, at the start, we assume all the soft constraints are true, and attempt to find a valid (if not optimized) result. If we can't, we iteratively relax the stricter "cashier/register imbalance" constraints, up to a difference of [2 cashier, 2 register]. One of the crucial reasons this approach works is that it was found that if it's feasible to find a result under an imbalance constraint, it seems to always be found in 1-2 seconds, or at the very worst, 5. Whereas if not, it can take up to 60 seconds or longer. (Also note: When the solver is asked to simply minimize the imbalances, even when given upper caps of 3-4, it was found to take a very inconsistent amount of time, so setting a low/reasonable timeout was tricky). So, we set a timeout of 15 seconds on each iteration.

* However, if we get to the end and still haven't found a result, then either the imbalance has to be quite high, or there is another soft constraint that is impossible to satisfy. As noted, it is them much more likely to be the latter. Either way, we assume nothing, increase the timeout, and simply optimize the number of constraints we can enable, weighted by their importance. Experimentally, this seems to run quite quickly, because the solver seems speedy at finding a small handful of individual non-imbalance soft constraints that are impossible to satisfy. (Note: Unlike how it seems to struggle, relatively speaking, proving that all soft constraints are possible to satisfy, or whether to kick one of them out or vs. kick out the cashier/register imbalances, in the *general* case).

* At the end, we always take the best basic schedule we can find, and optimize the "idealistic objectives".

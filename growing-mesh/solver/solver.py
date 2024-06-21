#!/bin/python3

import precice
import numpy as np
import math
import sys

# x is partitioned per rank and doesn't change
nx = 501
x = 0.0, 1.0
ny = 501
y = 0.0, 1.0

# y grows over time
newNodesPerEvent = 2
eventFrequency = 3 # time windows
dz = 0.1

def requiresEvent(tw):
    return tw % eventFrequency == 0

assert not requiresEvent(eventFrequency-1)
assert requiresEvent(eventFrequency)
assert not requiresEvent(eventFrequency+1)

def eventsAt(tw):
    # First event block at tw=0, second at eventFrequency
    return 1+math.floor(tw/eventFrequency)

assert eventsAt(0) == 1
assert eventsAt(eventFrequency-1) == 1
assert eventsAt(eventFrequency) == 2
assert eventsAt(eventFrequency+1) == 2

def getMeshAtTimeWindow(tw):
    znodes = eventsAt(tw) * newNodesPerEvent

    xs = np.linspace(x[0], x[1], nx)
    ys = np.linspace(y[0], y[1], ny)
    zs = np.array(range(znodes)) * dz

    return np.reshape([ (x, y, z) for z in zs for y in ys for x in xs ], (-1, 3))


participant_name = sys.argv[1]
participant = precice.Participant(participant_name, "../precice-config.xml", 0, 1)

mesh_name = participant_name+"-Mesh"
data_name = "Data"

coords = getMeshAtTimeWindow(0)
vertex_ids = participant.set_mesh_vertices(mesh_name, coords)
participant.initialize()

tw = 1
while participant.is_coupling_ongoing():
    dt = participant.get_max_time_step_size()

    if participant_name == "Right":
        data = participant.read_data(mesh_name, data_name, vertex_ids, dt)
        print(data)

    if requiresEvent(tw):
        oldCount = len(coords)
        coords = getMeshAtTimeWindow(tw)
        print(f"Event grows mesh from {oldCount} to {len(coords)}")
        participant.reset_mesh(mesh_name)
        vertex_ids = participant.set_mesh_vertices(mesh_name, coords)

    if participant_name == "Left":
        data = np.full(len(coords), tw)
        participant.write_data(mesh_name, data_name, vertex_ids, data)

    participant.advance(dt)
    tw += 1

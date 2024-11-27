#!/bin/python3

import precice
import numpy as np
import math
import sys
from mpi4py import MPI

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("participant", choices=["Left", "Right"])
parser.add_argument("--config", "-c", default="../precice-config.xml")
parser.add_argument("--no-remesh", dest="remesh", action="store_false")
args = parser.parse_args()

participant_name = args.participant
remote_name = "Left" if participant_name == "Right" else "Right"

# x is partitioned per rank and doesn't change
nx = 256 * 3
x = 0.0, 1.0
ny = 256 * 3
y = 0.0, 1.0

# y grows over time
newNodesPerEvent = 2
eventFrequency = 3  # time windows
dz = 0.1


# Handle partitioning
world = MPI.COMM_WORLD
size: int = world.size
rank: int = world.rank

parts: int = int(math.sqrt(size))
assert parts**2 == size, "size must be a square value"
assert math.remainder(nx, parts) == 0, f"{nx=} must be dividable by {parts=}"

# current parition in x, y
px = rank % parts
py = rank // parts

# nodes per parition
nxp = nx // parts
nyp = ny // parts

# node slide per partition
nxps = slice(nxp * px, nxp * (px + 1))
nyps = slice(nyp * py, nyp * (py + 1))

print(f"{rank=} {nxps=} {nyps=}")


def requiresEvent(tw):
    return tw % eventFrequency == 0


assert not requiresEvent(eventFrequency - 1)
assert requiresEvent(eventFrequency)
assert not requiresEvent(eventFrequency + 1)


def eventsAt(tw):
    # First event block at tw=0, second at eventFrequency
    return 1 + math.floor(tw / eventFrequency)


assert eventsAt(0) == 1
assert eventsAt(eventFrequency - 1) == 1
assert eventsAt(eventFrequency) == 2
assert eventsAt(eventFrequency + 1) == 2


def getMeshAtTimeWindow(tw):
    znodes = eventsAt(tw) * newNodesPerEvent

    xs = np.linspace(x[0], x[1], nx)[nxps]
    ys = np.linspace(y[0], y[1], ny)[nyps]
    zs = np.array(range(znodes)) * dz

    return np.reshape([(x, y, z) for z in zs for y in ys for x in xs], (-1, 3))


participant = precice.Participant(participant_name, args.config, rank, size)

mesh_name = participant_name + "-Mesh"
read_data_name = "Data-" + remote_name
write_data_name = "Data-" + participant_name

coords = getMeshAtTimeWindow(0)
vertex_ids = participant.set_mesh_vertices(mesh_name, coords)
participant.initialize()

tw = 1
while participant.is_coupling_ongoing():
    dt = participant.get_max_time_step_size()

    data = participant.read_data(mesh_name, read_data_name, vertex_ids, dt)
    if rank == 0:
        print(data)

    if args.remesh and requiresEvent(tw):
        oldCount = len(coords)
        coords = getMeshAtTimeWindow(tw)
        if rank == 0:
            print(
                f"Event grows local mesh from {oldCount} to {
                    len(coords)} and global mesh from {
                    oldCount *
                    size} to {
                    len(coords) *
                    size}")
        participant.reset_mesh(mesh_name)
        vertex_ids = participant.set_mesh_vertices(mesh_name, coords)

    data = np.full(len(coords), tw)
    participant.write_data(mesh_name, write_data_name, vertex_ids, data)

    participant.advance(dt)
    tw += 1

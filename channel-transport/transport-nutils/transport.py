#! /usr/bin/env python3

#
# Advection-Diffusion equation for a single species with a velocity field read from preCICE on the complete volume.
#

from nutils import function, mesh, cli, solver, export
import treelog as log
import numpy as np
import precice
from mpi4py import MPI


def reinitialize_namespace(domain):
    domain = domain.withboundary(inflow="left", outflow="right", wall="top,bottom") - domain[
        step_start:step_end, :step_hight
    ].withboundary(wall="left,top,right")

    # cloud of Gauss points
    gauss = domain.sample("gauss", degree=2)

    # Nutils namespace
    ns = function.Namespace(fallback_length=2)
    ns.x = geom
    ns.basis = domain.basis("std", degree=1)  # linear finite elements
    ns.u = "basis_n ?lhs_n"  # solution
    ns.u = "u_,i"  # gradient of solution
    ns.dudt = "basis_n (?lhs_n - ?lhs0_n) / ?dt"  # time derivative
    ns.vbasis = gauss.basis()
    ns.velocity_i = "vbasis_n ?velocity_ni"
    ns.k = 0.1  # diffusivity
    ns.xblob = 1, 1
    ns.uinit = ".5 - .5 tanh(((x_i - xblob_i) (x_i - xblob_i) - .5) / .1)"  # blob

    # define the weak form
    res = gauss.integral("(basis_n (dudt + (velocity_i u)_,i) + k basis_n,i u_,i) d:x" @ ns)

    # define Dirichlet boundary condition
    sqr = domain.boundary["inflow"].integral("u^2 d:x" @ ns, degree=2)
    cons = solver.optimize("lhs", sqr, droptol=1e-15)

    return ns, res, cons


def refine_mesh(ns, domain_coarse, domain_nm1, solu_nm1):
    """
    At the time of the calling of this function a predicted solution exists in ns.phi
    """
    # ----- Refine the coarse mesh according to the projected solution to get a predicted refined topology ----
    domain_ref = domain_coarse
    for level in range(3):
        print("refinement level = {}".format(level))
        domain_union1 = domain_nm1 & domain_ref
        smpl = domain_union1.sample('uniform', 5)
        ielem, criterion = smpl.eval([domain.f_index, abs(ns.phi - .5) < .4], lhs=solu_nm1)

        # Refine the elements for which at least one point tests true.
        domain_ref = domain_ref.refined_by(np.unique(ielem[criterion]))
        # ----------------------------------------------------------------------------------------------------

    # Create a new projection mesh which is the union of the previous refined mesh and the predicted mesh
    domain_union = domain_nm1 & domain_ref

    # ----- Project the solution of the last time step on the projection mesh -----
    ns.projectedu = function.dotarg('projectedsolu', domain_ref.basis('h-std', degree=1))
    sqru = domain_union.integral((ns.projectedu - ns.u) ** 2, degree=2)
    solu = solver.optimize('projectedsolu', sqru, droptol=1E-12, arguments=dict(solu=solu_nm1))

    return domain, solu


def main():

    print("Running Nutils")

    # define the Nutils mesh
    nx = 120
    ny = 32
    step_start = nx // 3
    step_end = nx // 2
    step_hight = ny // 2

    grid = np.linspace(0, 6, nx + 1), np.linspace(0, 2, ny + 1)
    domain, geom = mesh.rectilinear(grid)
    domain = domain.withboundary(inflow="left", outflow="right", wall="top,bottom") - domain[
        step_start:step_end, :step_hight
    ].withboundary(wall="left,top,right")
    domain_coarse = domain

    ns, res, cons = reinitialize_namespace(domain)

    # preCICE setup
    participant = precice.Participant("Transport", "../precice-config.xml", 0, 1)

    # define coupling mesh
    mesh_name = "Transport-Mesh"
    vertices = gauss.eval(ns.x)
    vertex_ids = participant.set_mesh_vertices(mesh_name, vertices)

    # coupling data
    data_name = "Velocity"

    participant.initialize()

    timestep = 0
    solver_dt = 0.005
    precice_dt = participant.get_max_time_step_size()
    dt = min(precice_dt, solver_dt)

    # set blob as initial condition
    sqr = domain.integral("(u - uinit)^2" @ ns, degree=2)
    lhs0 = solver.optimize("lhs", sqr)

    for level in range(3):
        print("refinement level = {}".format(level))
        smpl = domain.sample('uniform', 5)
        ielem, criterion = smpl.eval([domain.f_index, abs(ns.du) > 1.0], lhs=lhs0)

        # Refine the elements for which at least one point tests true.
        domain = domain.refined_by(np.unique(ielem[criterion]))

        reinitialize_namespace(topo)

        # set blob as initial condition
        sqr = domain.integral("(u - uinit)^2" @ ns, degree=2)
        lhs0 = solver.optimize("lhs", sqr)

    # initialize the velocity values
    velocity_values = np.zeros_like(vertices)

    while participant.is_coupling_ongoing():

        if timestep % 1 == 0:  # visualize
            bezier = domain.sample("bezier", 2)
            x, u = bezier.eval(["x_i", "u"] @ ns, lhs=lhs0)
            with log.add(log.DataLog()):
                export.vtk("Transport_" + str(timestep), bezier.tri, x, T=u)

        precice_dt = participant.get_max_time_step_size()

        # potentially adjust non-matching timestep sizes
        dt = min(solver_dt, precice_dt)

        # read velocity values from participant
        velocity_values = participant.read_data(mesh_name, data_name, vertex_ids, dt)

        # solve nutils timestep
        lhs = solver.solve_linear(
            "lhs", res, constrain=cons, arguments=dict(lhs0=lhs0, dt=dt, velocity=velocity_values)
        )

        # do the coupling
        participant.advance(dt)

        # advance variables
        timestep += 1
        lhs0 = lhs

    participant.finalize()


if __name__ == "__main__":
    cli.run(main)

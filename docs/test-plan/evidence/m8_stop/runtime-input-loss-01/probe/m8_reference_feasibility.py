"""Pre-launch nominal inertial-capacity guard; no dynamic feasibility claim."""
import math


def ramp_feasible(start,end,duration,mass=1696.,radius=.355,propulsion=300.,braking=1500.):
    if not all(math.isfinite(x) for x in (start,end,duration,mass,radius,propulsion,braking)):
        return False
    if not (0<=start<=40/3.6 and 0<=end<=40/3.6 and duration>0 and mass>0 and radius>0 and propulsion>=0 and braking>=0):
        return False
    torque=mass*radius*((end-start)/duration)
    return math.isfinite(torque) and -braking<=torque<=propulsion


def assess_route(route):
    combined=route.get('scenario')=='S03'
    startup=10 if combined and route['schema']=='m8-reference-v1' else 20
    phases=[(0.,30/3.6,startup)]
    phases+= [(30/3.6,20/3.6,6),(20/3.6,0.,8)] if combined else [(30/3.6,0.,15)]
    rows=[dict(from_mps=a,to_mps=b,duration_s=t,required_inertial_torque_nm=1696*.355*((b-a)/t),accepted=ramp_feasible(a,b,t)) for a,b,t in phases]
    return dict(status='PASS_NECESSARY_INERTIAL_BOUNDS' if all(r['accepted'] for r in rows) else 'REJECT_INFEASIBLE_RAMP',
        mass_kg=1696,wheel_radius_m=.355,propulsion_limit_nm=300,braking_limit_nm=1500,ramps=rows,
        tracking_guaranteed=False)


def require_feasible_route(route):
    result=assess_route(route)
    if result['status'].startswith('REJECT'):raise ValueError('reference exceeds configured inertial torque capacity')
    return result

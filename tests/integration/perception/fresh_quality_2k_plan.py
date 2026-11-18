"""Select fresh native 2K evaluation sites using only recorded Town04 geometry."""
import argparse
import hashlib
import json
from pathlib import Path

from quality_plan_v4 import build as build_poses, validate_plan
from quality_sites_v9 import select_fresh

ROOT = Path(__file__).resolve().parents[3]
SURVEY = ROOT/'docs/test-plan/evidence/m10_quality_v9/survey-selected.json'
TEMPLATE = ROOT/'profiles/perception-quality-template-v9.json'
PRIORS = tuple(ROOT/'profiles'/f'perception-road-evaluation-{version}.json'
               for version in ('v8','v8b','v9'))


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plans():
    survey = read(SURVEY)
    if survey['status'] != 'PASS' or len(survey['sites']) != 372:
        raise ValueError('Incomplete Town04 road survey')
    sites = {site['spawn_point_index']:site for site in survey['sites']}
    if set(sites) != set(range(372)):
        raise ValueError('Duplicate or missing map spawn index')
    used_sites = set()
    for path in PRIORS:
        plan = read(path)
        if plan['map'] != 'Town04_Opt' or plan['xodr_sha256'] != survey['xodr_sha256']:
            raise ValueError(f'Road coordinate system changed in {path}')
        used_sites.update(p['spawn_point_index'] for p in plan['partitions'].values())
    used = dict(schema='m10-used-map-roads-v9',map='Town04_Opt',
                route_origins=[sites[i]['nodes']['0']['pose']['location'] for i in sorted(used_sites)],
                route_road_ids=sorted({n['road_id'] for i in used_sites for n in sites[i]['nodes'].values()}))
    selected = select_fresh(survey['sites'],used)
    chosen = [s['spawn_point_index'] for s in selected]
    selection = dict(schema='m10-fresh-2k-route-selection-v1', map=survey['map'],
        xodr_sha256=survey['xodr_sha256'], survey_sha256=digest(SURVEY),
        template_sha256=digest(TEMPLATE), used_plans={str(p.relative_to(ROOT)):digest(p) for p in PRIORS},
        used_sites=sorted(used_sites), used_road_ids=used['route_road_ids'],
        selected={part:dict(spawn_index=site['spawn_point_index'],
            road_ids=sorted({n['road_id'] for n in site['nodes'].values()}))
            for part,site in zip(('development','holdout'),selected)},
        method='First two complete eligible routes sorted by spawn index, disjoint road IDs, at least 50 m between camera origins and from previous sites',
        rgb_captured=False, model_evaluated=False)
    site_survey=dict(survey,selected_sites=chosen)
    template = read(TEMPLATE)
    # At spawn 101 the original blocker covered the walker below the fixed
    # inclusion limit. The model-free preparation mask supports a 20 cm shift.
    for case in template['partitions']['holdout']['cases']:
        if case['stratum'] == 'occluded' and case['target_class'] == 0:
            blocker, = [a for a in case['actors'] if a['role'] == 'occluder']
            if blocker['right_m'] != -0.4:
                raise ValueError('unexpected original holdout blocker')
            blocker['right_m'] = -0.6
    evaluation,preparation=build_poses(site_survey,digest(SURVEY),template,digest(TEMPLATE))
    for plan in (evaluation,preparation):
        for part in plan['partitions'].values():
            for case in part['cases']:
                for key in ('id','reference_for'):
                    if key in case:
                        case[key]=case[key].replace('v4-', 'fresh-2k-', 1)
        validate_plan(plan)
        plan.update(schema='m10-fresh-2k-road-plan-v1',camera=dict(width=2560,height=1536,horizontal_fov=90),
                    canonical_evaluation=[640,384], placement_revision='fresh-2k-v1',
                    inherited_pose_recipe=TEMPLATE.name, survey_source=str(SURVEY.relative_to(ROOT)))
        plan.update(sensor_tick_seconds=.1, alignment_ticks=35, readback_ticks=3,
                    frame_selection='First scheduled 10Hz exposure after 40 settling ticks; determine sensor phase from paired startup frames before placing actors')
        del plan['selected_capture_tick']
        del plan['created_date']
    return selection,evaluation,preparation


def validate_retained(directory):
    expected=plans()
    for name,data in zip(('sites','evaluation','preparation'),expected):
        if read(directory/(name+'.json')) != data:
            raise ValueError(f'Fresh quality {name} changed')
    return expected[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if not args.check:
        selection,evaluation,preparation=plans()
        args.output.mkdir(parents=True,exist_ok=False)
        for name,data in zip(('sites','evaluation','preparation'),(selection,evaluation,preparation)):
            (args.output/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps(validate_retained(args.output)['selected']))

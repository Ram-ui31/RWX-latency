"""Cost evidence authorizes computation only, never a test omission."""
import math

def gate(gain,remaining,record):
    if not record or record.get('status')!='observed_pass':return {'allowed':False,'reason':'uncalibrated_or_invalid_cost'}
    cost=record.get('total_cpu_seconds')
    if type(cost) not in (int,float) or not math.isfinite(cost) or cost<0:return {'allowed':False,'reason':'invalid_cost'}
    estimate=1.25*cost+0.25
    return {'allowed':estimate<gain and estimate<remaining,'reason':'cost_evidence' if estimate<gain and estimate<remaining else 'cost_exceeds_saving_or_budget','estimated_cpu':estimate,'saving_ceiling':gain}

from datetime import datetime,timezone,timedelta
from core.validate import require_row
TABLES=('locations','facilities','inspections','incidents','repairs','jobs')
CATEGORIES=('Sumur','Pompa','Reservoir','Jaringan Distribusi')
UNITS=('Liter','Liter/detik','m³','m³/hari')

def today():
    return datetime.now(timezone(timedelta(hours=7))).date().isoformat()

def find(db,kind,id):
    return require_row(db,kind,id,TABLES)

def rows(db,sql,args=()):
    return [dict(r) for r in db.execute(sql,args)]

def incidents(db):
    result=rows(db,'''SELECT i.*,f.name facility,l.name location,
    (SELECT progress FROM repairs r WHERE r.incident_id=i.id ORDER BY r.on_date DESC,r.id DESC LIMIT 1) progress,
    (SELECT on_date FROM repairs r WHERE r.incident_id=i.id ORDER BY r.on_date DESC,r.id DESC LIMIT 1) repaired_on
    FROM incidents i JOIN facilities f ON f.id=i.facility_id JOIN locations l ON l.id=f.location_id ORDER BY i.on_date DESC,i.id DESC''')
    for r in result:
        r['status']='Terbuka' if r['progress'] is None else 'Selesai' if r['progress']==100 else 'Dalam Perbaikan'
    return result

def state(db,f):
    archive=1 if f.get('archived')=='1' else 0
    q=str(f.get('q','')).lower().strip()[:120]
    all_incidents=incidents(db)
    facilities=rows(db,'''SELECT f.*,l.name location,
    (SELECT condition FROM inspections i WHERE i.facility_id=f.id ORDER BY i.on_date DESC,i.id DESC LIMIT 1) condition,
    (SELECT on_date FROM inspections i WHERE i.facility_id=f.id ORDER BY i.on_date DESC,i.id DESC LIMIT 1) inspected_on
    FROM facilities f JOIN locations l ON l.id=f.location_id WHERE f.archived=? AND l.archived=0 ORDER BY l.name,f.name''',(archive,))
    for r in facilities:
        r['open_incidents']=sum(i['facility_id']==r['id'] and i['status']!='Selesai' for i in all_incidents)
    facilities=[r for r in facilities if (not q or any(q in r[k].lower() for k in ('name','code','location'))) and (not f.get('location_id') or str(r['location_id'])==str(f['location_id'])) and (not f.get('category') or r['category']==f['category']) and (not f.get('condition') or (r['condition'] or 'Belum Diperiksa')==f['condition']) and (f.get('open_only')!='1' or r['open_incidents'])]
    return {'facilities':facilities,'locations':rows(db,'SELECT * FROM locations WHERE archived=? ORDER BY name',(archive,)),'allLocations':rows(db,'SELECT id,name FROM locations WHERE archived=0 ORDER BY name'),'allFacilities':rows(db,"SELECT f.id,l.name||' / '||f.name name FROM facilities f JOIN locations l ON l.id=f.location_id WHERE f.archived=0 AND l.archived=0 ORDER BY l.name,f.name"),'incidents':all_incidents,'jobs':rows(db,'SELECT j.*,f.name facility,l.name location FROM jobs j JOIN facilities f ON f.id=j.facility_id JOIN locations l ON l.id=f.location_id ORDER BY j.starts_on DESC,j.id DESC'),'categories':CATEGORIES,'units':UNITS,'summary':{'total':len(facilities),'operating':sum(r['condition']=='Beroperasi' for r in facilities),'unknown':sum(r['condition'] is None for r in facilities),'open':sum(r['open_incidents'] for r in facilities)}}

def history(db,id):
    find(db,'facilities',id)
    return {'inspections':rows(db,'SELECT i.*,u.name actor FROM inspections i JOIN users u ON u.id=i.actor_id WHERE facility_id=? ORDER BY on_date DESC,i.id DESC',(id,)),'repairs':rows(db,'SELECT r.*,i.description incident,u.name actor FROM repairs r JOIN incidents i ON i.id=r.incident_id JOIN users u ON u.id=r.actor_id WHERE i.facility_id=? ORDER BY r.on_date DESC,r.id DESC',(id,)),'maintenance':rows(db,'SELECT e.*,j.starts_on,j.target_on,u.name actor FROM job_events e JOIN jobs j ON j.id=e.job_id JOIN users u ON u.id=e.actor_id WHERE j.facility_id=? ORDER BY e.id DESC',(id,))}

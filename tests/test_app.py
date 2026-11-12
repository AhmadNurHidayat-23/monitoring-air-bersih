import secrets
from datetime import date,timedelta
import pytest
from fastapi.testclient import TestClient
from app import create_app
from app.models import today
from core.db import connect
from core.security import add_user

def day(offset=0):
    return (date.fromisoformat(today())+timedelta(days=offset)).isoformat()

def facility(**extra):
    return {'location_id':1,'code':'AIR-DEMO-01','name':'Pompa Contoh','category':'Pompa','capacity':25,'unit':'Liter/detik','description':'Fasilitas demonstrasi',**extra}

def job(**extra):
    return {'facility_id':1,'starts_on':day(-1),'target_on':day(7),'task':'Pemeliharaan contoh','status':'Direncanakan','completed_on':'',**extra}

@pytest.fixture
def env(tmp_path):
    app=create_app({'INSTANCE_DIR':str(tmp_path)})
    db=connect(tmp_path)
    password=secrets.token_hex(20)
    for name,role in [('admin','Admin'),('staff','Petugas')]:
        add_user(db,name,'Penguji '+role,role,password)
    db.close()
    clients={}
    for name in ['admin','staff']:
        c=TestClient(app)
        r=c.post('/api/login',json={'username':name,'password':password})
        assert r.status_code==200
        clients[name]=(c,{'X-CSRF-Token':r.json()['csrf']})
    c,h=clients['admin']
    assert c.post('/api/locations',json={'name':'Lokasi Contoh','address':'Alamat demonstrasi'},headers=h).status_code==200
    assert c.post('/api/facilities',json=facility(),headers=h).status_code==200
    yield app,clients,tmp_path
    for c,_ in clients.values():
        c.close()

def test_crud_and_archive_restore(env):
    _,clients,_=env
    c,h=clients['admin']
    assert c.put('/api/locations/1',json={'name':'Lokasi Diubah','address':'Alamat contoh'},headers=h).status_code==200
    assert c.put('/api/facilities/1',json=facility(capacity=30),headers=h).status_code==200
    assert c.get('/api/state').json()['facilities'][0]['capacity']==30
    assert c.request('DELETE','/api/locations/1',json={},headers=h).status_code==409
    assert c.request('DELETE','/api/facilities/1',json={},headers=h).status_code==200
    assert c.get('/api/state').json()['facilities']==[]
    assert len(c.get('/api/state?archived=1').json()['facilities'])==1
    c.request('DELETE','/api/locations/1',json={},headers=h)
    assert c.post('/api/facilities/1/restore',json={},headers=h).status_code==409
    c.post('/api/locations/1/restore',json={},headers=h)
    assert c.post('/api/facilities/1/restore',json={},headers=h).status_code==200

def test_inspection_history_uses_recorded_dates_and_unknown_is_honest(env):
    _,clients,_=env
    c,h=clients['staff']
    assert c.get('/api/state').json()['facilities'][0]['condition'] is None
    for on,condition in [(day(),'Terbatas'),(day(-2),'Beroperasi')]:
        assert c.post('/api/inspections',json={'facility_id':1,'on_date':on,'condition':condition,'note':'Catatan operasional contoh'},headers=h).status_code==200
    state=c.get('/api/state').json()
    assert state['facilities'][0]['condition']=='Terbatas'
    assert state['summary']['operating']==0
    assert len(c.get('/api/facilities/1/history').json()['inspections'])==2
    assert c.request('DELETE','/api/inspections/1',json={},headers=h).status_code==405

def test_incident_repair_progress_history_and_archive_guard(env):
    _,clients,_=env
    c,h=clients['staff']
    assert c.post('/api/incidents',json={'facility_id':1,'on_date':day(-2),'severity':'Sedang','description':'Gangguan contoh'},headers=h).status_code==200
    admin,ah=clients['admin']
    assert admin.request('DELETE','/api/facilities/1',json={},headers=ah).status_code==409
    assert c.get('/api/state').json()['incidents'][0]['progress'] is None
    for on,progress in [(day(),100),(day(-1),40)]:
        assert c.post('/api/repairs',json={'incident_id':1,'on_date':on,'progress':progress,'note':'Perbaikan uji'},headers=h).status_code==200
    state=c.get('/api/state').json()
    assert state['incidents'][0]['status']=='Selesai'
    assert state['summary']['open']==0
    assert state['facilities'][0]['condition'] is None
    assert len(c.get('/api/facilities/1/history').json()['repairs'])==2
    assert admin.request('DELETE','/api/facilities/1',json={},headers=ah).status_code==200

def test_maintenance_crud_cancel_and_real_completion_date(env):
    _,clients,_=env
    c,h=clients['admin']
    assert c.post('/api/jobs',json=job(),headers=h).status_code==200
    assert c.put('/api/jobs/1',json=job(status='Berlangsung',task='Perawatan diubah'),headers=h).status_code==200
    assert c.request('DELETE','/api/facilities/1',json={},headers=h).status_code==409
    assert c.put('/api/jobs/1',json=job(status='Selesai',completed_on=day(1)),headers=h).status_code==400
    assert c.put('/api/jobs/1',json=job(status='Selesai',completed_on=day()),headers=h).status_code==200
    assert c.get('/api/state').json()['jobs'][0]['completed_on']==today()
    assert len(c.get('/api/facilities/1/history').json()['maintenance'])==3
    assert c.request('DELETE','/api/jobs/1',json={},headers=h).status_code==200
    assert c.get('/api/state').json()['jobs'][0]['status']=='Dibatalkan'
    assert c.put('/api/jobs/1',json=job(starts_on=day(-2)),headers=h).status_code==409

def test_validation_and_consistent_foreign_keys(env):
    _,clients,_=env
    c,h=clients['admin']
    for bad in [facility(capacity=0),facility(capacity=0.1),facility(unit='Tidak valid'),facility(category='Lainnya'),facility(location_id=999),facility(name='')]:
        assert c.post('/api/facilities',json=bad,headers=h).status_code in (400,404)
    assert c.post('/api/inspections',json={'facility_id':1,'on_date':day(1),'condition':'Beroperasi','note':'Uji'},headers=h).status_code==400
    c.post('/api/incidents',json={'facility_id':1,'on_date':day(),'severity':'Ringan','description':'Uji'},headers=h)
    for bad in [{'progress':101},{'on_date':day(-1)},{'on_date':'2026-02-30'}]:
        assert c.post('/api/repairs',json={'incident_id':1,'on_date':day(),'progress':20,'note':'Uji',**bad},headers=h).status_code==400
    assert c.post('/api/jobs',json=job(target_on=day(-2)),headers=h).status_code==400
    assert c.post('/api/jobs',json=job(status='Selesai',completed_on=day()),headers=h).status_code==400

def test_search_filter_and_csv_do_not_claim_potable_water(env):
    _,clients,_=env
    c,h=clients['staff']
    assert len(c.get('/api/state?q=pompa&location_id=1&category=Pompa&condition=Belum%20Diperiksa').json()['facilities'])==1
    assert c.get('/api/state?q=tidakada').json()['facilities']==[]
    assert c.get('/api/state?open_only=1').json()['facilities']==[]
    c.post('/api/incidents',json={'facility_id':1,'on_date':day(),'severity':'Ringan','description':'Gangguan uji'},headers=h)
    assert len(c.get('/api/state?open_only=1').json()['facilities'])==1
    csv=c.get('/api/export').content.decode('utf-8-sig')
    assert 'Pompa Contoh' in csv and 'Liter/detik' in csv
    assert 'Status operasional bukan hasil uji kualitas air.' in csv
    html=c.get('/').text
    assert 'tidak menyatakan air aman diminum' in html

def test_access_csrf_origin_isolation_fresh_roles_and_logout(env):
    app,clients,folder=env
    c,h=clients['staff']
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/state').status_code==401
    assert c.put('/api/facilities/1',json=facility(),headers=h).status_code==403
    assert c.post('/api/inspections',json={}).status_code==403
    assert c.post('/api/inspections',json={},headers={**h,'Origin':'https://example.invalid'}).status_code==403
    admin,ah=clients['admin']
    with TestClient(app) as wrong:
        wrong.cookies.set('app_session',admin.cookies.get('monitoring_air_bersih_session'))
        assert wrong.get('/api/state').status_code==401
    db=connect(folder)
    db.execute("UPDATE users SET role='Petugas' WHERE username='admin'")
    db.commit()
    db.close()
    assert admin.post('/api/locations',json={'name':'Role lama','address':'Uji'},headers=ah).status_code==403
    c.post('/api/logout',json={},headers=h)
    assert c.get('/api/state').status_code==401

def test_restart_idempotence_and_database_integrity(env):
    _,clients,folder=env
    c,h=clients['staff']
    c.post('/api/inspections',json={'facility_id':1,'on_date':day(),'condition':'Beroperasi','note':'Uji tersimpan'},headers=h)
    app=create_app({'INSTANCE_DIR':str(folder)})
    with TestClient(app) as fresh:
        fresh.cookies.update(c.cookies)
        assert fresh.get('/api/state').json()['summary']['operating']==1
    db=connect(folder)
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    db.close()

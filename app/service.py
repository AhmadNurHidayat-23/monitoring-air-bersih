from core.db import transaction
from core.security import Problem
from core.validate import text,integer,date,choice
from .models import find,today,incidents,CATEGORIES,UNITS

def active(db,id):
    r=find(db,'facilities',id)
    if r['archived'] or find(db,'locations',r['location_id'])['archived']:
        raise Problem('Pulihkan fasilitas dan lokasi terlebih dahulu.',409)
    return r

def location(db,b,id=None):
    name,address=text(b.get('name'),'Lokasi',100),text(b.get('address'),'Alamat demonstrasi',250)
    with transaction(db):
        if id:
            if find(db,'locations',id)['archived']:
                raise Problem('Lokasi diarsipkan.',409)
            db.execute('UPDATE locations SET name=?,address=? WHERE id=?',(name,address,id))
        else:
            db.execute('INSERT INTO locations(name,address) VALUES(?,?)',(name,address))

def facility(db,b,id=None):
    values=(integer(b.get('location_id'),'Lokasi',1),text(b.get('code'),'Kode fasilitas',40),text(b.get('name'),'Nama fasilitas',100),choice(b.get('category'),CATEGORIES,'Kategori'),integer(b.get('capacity'),'Kapasitas',1,1000000000),choice(b.get('unit'),UNITS,'Satuan'),text(b.get('description',''),'Keterangan fasilitas',1000,False))
    if find(db,'locations',values[0])['archived']:
        raise Problem('Lokasi diarsipkan.',409)
    with transaction(db):
        if id:
            old=active(db,id)
            if old['location_id']!=values[0] and db.execute('SELECT id FROM inspections WHERE facility_id=? UNION SELECT id FROM incidents WHERE facility_id=? UNION SELECT id FROM jobs WHERE facility_id=?',(id,id,id)).fetchone():
                raise Problem('Lokasi fasilitas dengan riwayat tidak dapat diganti.',409)
            db.execute('UPDATE facilities SET location_id=?,code=?,name=?,category=?,capacity=?,unit=?,description=? WHERE id=?',(*values,id))
        else:
            db.execute('INSERT INTO facilities(location_id,code,name,category,capacity,unit,description) VALUES(?,?,?,?,?,?,?)',values)

def past(value):
    on=date(value)
    if on>today():
        raise Problem('Tanggal pencatatan tidak boleh mendatang.')
    return on

def inspection(db,b,actor):
    id=integer(b.get('facility_id'),'Fasilitas',1)
    active(db,id)
    with transaction(db):
        db.execute('INSERT INTO inspections(facility_id,on_date,condition,note,actor_id) VALUES(?,?,?,?,?)',(id,past(b.get('on_date')),choice(b.get('condition'),('Beroperasi','Terbatas','Tidak Beroperasi'),'Kondisi'),text(b.get('note'),'Catatan operasional',1500),actor))

def incident(db,b,actor):
    id=integer(b.get('facility_id'),'Fasilitas',1)
    active(db,id)
    with transaction(db):
        db.execute('INSERT INTO incidents(facility_id,on_date,severity,description,actor_id) VALUES(?,?,?,?,?)',(id,past(b.get('on_date')),choice(b.get('severity'),('Ringan','Sedang','Berat'),'Tingkat gangguan'),text(b.get('description'),'Uraian gangguan',1500),actor))

def repair(db,b,actor):
    id,on=integer(b.get('incident_id'),'Gangguan',1),past(b.get('on_date'))
    item=find(db,'incidents',id)
    active(db,item['facility_id'])
    if on<item['on_date']:
        raise Problem('Tanggal perbaikan tidak boleh sebelum gangguan.')
    with transaction(db):
        db.execute('INSERT INTO repairs(incident_id,on_date,progress,note,actor_id) VALUES(?,?,?,?,?)',(id,on,integer(b.get('progress'),'Progres perbaikan',0,100),text(b.get('note'),'Tindakan perbaikan',1500),actor))

def job(db,b,actor,id=None):
    facility_id,start,target=integer(b.get('facility_id'),'Fasilitas',1),date(b.get('starts_on')),date(b.get('target_on'))
    active(db,facility_id)
    status=choice(b.get('status'),('Direncanakan','Berlangsung','Selesai','Dibatalkan'),'Status jadwal')
    task=text(b.get('task'),'Rencana pemeliharaan',1000)
    completed=date(b.get('completed_on')) if status=='Selesai' else ''
    if target<start or completed and (completed<start or completed>today()):
        raise Problem('Rentang jadwal atau tanggal selesai tidak valid.')
    if not id and status!='Direncanakan':
        raise Problem('Jadwal baru dimulai dengan status Direncanakan.')
    with transaction(db):
        if id:
            old=find(db,'jobs',id)
            if old['facility_id']!=facility_id or old['starts_on']!=start:
                raise Problem('Fasilitas dan tanggal mulai jadwal dipertahankan untuk riwayat.',409)
            db.execute('UPDATE jobs SET target_on=?,task=?,status=?,completed_on=? WHERE id=?',(target,task,status,completed,id))
        else:
            id=db.execute('INSERT INTO jobs(facility_id,starts_on,target_on,task,status,completed_on) VALUES(?,?,?,?,?,?)',(facility_id,start,target,task,status,completed)).lastrowid
        db.execute('INSERT INTO job_events(job_id,status,task,actor_id) VALUES(?,?,?,?)',(id,status,task,actor))

def archive(db,kind,id,restore=False):
    r=find(db,kind,id)
    with transaction(db):
        if kind=='locations' and not restore and db.execute('SELECT id FROM facilities WHERE location_id=? AND archived=0',(id,)).fetchone():
            raise Problem('Arsipkan seluruh fasilitas aktif lokasi terlebih dahulu.',409)
        if kind=='facilities':
            if restore and find(db,'locations',r['location_id'])['archived']:
                raise Problem('Pulihkan lokasi terlebih dahulu.',409)
            if not restore and (any(i['facility_id']==id and i['status']!='Selesai' for i in incidents(db)) or db.execute("SELECT id FROM jobs WHERE facility_id=? AND status NOT IN('Selesai','Dibatalkan')",(id,)).fetchone()):
                raise Problem('Selesaikan gangguan dan selesaikan/batalkan jadwal sebelum mengarsipkan.',409)
        db.execute(f'UPDATE {kind} SET archived=? WHERE id=?',(0 if restore else 1,id))

def cancel_job(db,id,actor):
    r=find(db,'jobs',id)
    job(db,{**r,'status':'Dibatalkan'},actor,id)

import csv
import io
from fastapi import APIRouter,Request,Depends
from fastapi.responses import Response
from core.auth import context,require,data
from core.security import Problem
from . import models,service
api=APIRouter()

@api.get('/api/state')
async def state(request:Request,ctx=Depends(context)):
    require(ctx,request)
    return models.state(ctx.db,request.query_params)

@api.post('/api/{kind}')
@api.put('/api/{kind}/{id}')
@api.delete('/api/{kind}/{id}')
async def save(request:Request,kind:str,id:int=None,ctx=Depends(context)):
    user=require(ctx,request)
    if kind not in ('locations','facilities','jobs','inspections','incidents','repairs'):
        raise Problem('Alamat tidak tersedia.',404)
    if kind in ('locations','facilities','jobs') and user['role']!='Admin':
        raise Problem('Data induk dan jadwal dikelola Admin.',403)
    if kind in ('inspections','incidents','repairs'):
        if request.method!='POST':
            raise Problem('Catatan disimpan sebagai riwayat.',405)
        getattr(service,{'inspections':'inspection','incidents':'incident','repairs':'repair'}[kind])(ctx.db,await data(request),user['id'])
    elif request.method=='DELETE':
        if kind=='jobs':
            service.cancel_job(ctx.db,id,user['id'])
        else:
            service.archive(ctx.db,kind,id)
    elif kind=='jobs':
        service.job(ctx.db,await data(request),user['id'],id)
    else:
        getattr(service,'location' if kind=='locations' else 'facility')(ctx.db,await data(request),id)
    return {'message':'Catatan fasilitas disimpan.'}

@api.post('/api/{kind}/{id}/restore')
async def restore(request:Request,kind:str,id:int,ctx=Depends(context)):
    require(ctx,request,('Admin',))
    if kind not in ('locations','facilities'):
        raise Problem('Alamat tidak tersedia.',404)
    service.archive(ctx.db,kind,id,True)
    return {'message':'Data dipulihkan.'}

@api.get('/api/facilities/{id}/history')
async def history(request:Request,id:int,ctx=Depends(context)):
    require(ctx,request)
    return models.history(ctx.db,id)

@api.get('/api/export')
async def export(request:Request,ctx=Depends(context)):
    require(ctx,request)
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(['Kode','Fasilitas','Lokasi','Kategori','Kapasitas','Satuan','Kondisi operasional','Tanggal inspeksi','Gangguan terbuka','Catatan'])
    for r in models.state(ctx.db,request.query_params)['facilities']:
        values=[r[k] if r[k] is not None else '' for k in ('code','name','location','category','capacity','unit','condition','inspected_on','open_incidents')]+['Status operasional bukan hasil uji kualitas air.']
        writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@')) else v for v in values])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv;charset=utf-8',headers={'Content-Disposition':'attachment; filename=pemantauan-air.csv'})

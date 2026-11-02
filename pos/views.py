import io, json, os, urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from bson import ObjectId
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from .store import db

def owner(request): return request.session.get("uid")
def workspace(request): return request.session.get("workspace") or owner(request)
def add_template_ids(documents):
    for document in documents: document["id"]=str(document["_id"])
    return documents
def oid(v):
    try: return ObjectId(v)
    except Exception: return None
def products_for(request, include_archived=False):
    q={"owner":owner(request)}
    if not include_archived: q["archived"]={"$ne":True}
    try: return add_template_ids(list(db().products.find(q).sort("updated",-1)))
    except Exception: return []
def orders_for(request, query=None):
    q={"owner":owner(request)}; q.update(query or {})
    try: return add_template_ids(list(db().orders.find(q).sort("created",-1).limit(5000)))
    except Exception: return []
def cats_for(request, active=True):
    q={"workspace":workspace(request)}
    if active: q["archived"]={"$ne":True}
    try: return add_template_ids(list(db().categories.find(q).sort("name",1)))
    except Exception: return []
def signed_in(fn):
    @wraps(fn)
    def wrap(request,*a,**kw):
        if not owner(request):
            if request.path.startswith("/api/"): return JsonResponse({"error":"Sign in required"},status=401)
            return redirect("/login/")
        return fn(request,*a,**kw)
    return wrap
def admin_only(fn):
    @wraps(fn)
    def wrap(request,*a,**kw):
        if request.session.get("role")!="admin": return JsonResponse({"error":"Admin access required"},status=403)
        return fn(request,*a,**kw)
    return wrap
def login(request):
    if owner(request): return redirect("/")
    error=""
    if request.method=="POST":
        email=request.POST.get("email","").strip().lower(); password=request.POST.get("password","")
        try:
            u=db().users.find_one({"email":email})
            if u and check_password(password,u["password"]):
                request.session["uid"]=str(u["_id"]); request.session["role"]=u["role"]; request.session["email"]=u["email"]; request.session["workspace"]=u.get("workspace",str(u["_id"]))
                return redirect("/")
        except Exception: pass
        error="Email or password is incorrect, or MongoDB is unavailable."
    return render(request,"login.html",{"error":error})
def signup(request):
    error=""
    if request.method=="POST":
        email=request.POST.get("email","").strip().lower(); password=request.POST.get("password","")
        try:
            if not email or len(password)<8: raise ValueError("Use a valid email and password of at least 8 characters.")
            admin=db().users.find_one({"role":"admin"})
            role="admin" if admin is None else "user"
            workspace_id=str(admin["_id"]) if admin else None
            record={"email":email,"password":make_password(password),"role":role,"created":datetime.now(timezone.utc)}
            result=db().users.insert_one(record)
            if workspace_id: db().users.update_one({"_id":result.inserted_id},{"$set":{"workspace":workspace_id}})
            else: db().users.update_one({"_id":result.inserted_id},{"$set":{"workspace":str(result.inserted_id)}})
            return redirect("/login/")
        except ValueError as e: error=str(e)
        except Exception: error="Account could not be created. The email may already be registered."
    return render(request,"signup.html",{"error":error})
def logout(request): request.session.flush(); return redirect("/login/")
@signed_in
def dashboard(request):
    ps=products_for(request); os=orders_for(request,{"status":"completed"})
    chart=[]
    for ago in range(6,-1,-1):
        day=(datetime.now(timezone.utc)-timedelta(days=ago)).date()
        chart.append({"label":day.strftime("%a"),"sales":sum(float(o.get("subtotal",0)) for o in os if o.get("created") and o["created"].date()==day)})
    return render(request,"dashboard.html",{"products":ps,"orders":os[:6],"revenue":sum(float(o.get("subtotal",0)) for o in os),"profit":sum(float(o.get("profit",0)) for o in os),"count":len(os),"low":sum(int(p.get("stock",0))<=5 for p in ps),"chart":json.dumps(chart),"tax":tax(request),"email":request.session.get("email")})
def tax(request):
    try: return float(db().settings.find_one({"owner":owner(request),"key":"vat"})["rate"])
    except Exception: return 11.0
@signed_in
def products(request):
    items=products_for(request)
    for item in items: item["margin"]=float(item.get("price",0))-float(item.get("cost",0))
    return render(request,"products.html",{"products":items,"categories":cats_for(request),"tax":tax(request)})
@signed_in
@require_POST
def save_product(request):
    try:
        category=oid(request.POST.get("category_id")); cat=db().categories.find_one({"_id":category,"workspace":workspace(request),"archived":{"$ne":True}})
        if not cat: raise ValueError("Choose an active category.")
        sub=request.POST.get("subcategory","").strip()
        stock=max(0,int(request.POST.get("stock",0))); days=max(1,int(request.POST.get("deadline_days",30))); now=datetime.now(timezone.utc)
        data={"owner":owner(request),"name":request.POST["name"].strip(),"sku":request.POST.get("sku",""),"supplier":request.POST.get("supplier",""),"cost":float(request.POST.get("cost",0)),"price":float(request.POST.get("price",0)),"stock":stock,"deadline_days":days,"category_id":category,"category_name":cat["name"],"subcategory":sub,"updated":now,"archived":False}
        pid=oid(request.POST.get("id"))
        existing=db().products.find_one({"_id":pid,"owner":owner(request)}) if pid else None
        if existing and int(existing.get("stock",0))==stock:
            data["initial_stock"]=int(existing.get("initial_stock",stock)); data["stock_since"]=existing.get("stock_since",now); data["deadline_at"]=existing.get("deadline_at",now+timedelta(days=days)); data["deadstock_status"]=existing.get("deadstock_status","active")
        else:
            data["initial_stock"]=stock; data["stock_since"]=now; data["deadline_at"]=now+timedelta(days=days); data["deadstock_status"]="active"
        if existing: db().products.update_one({"_id":pid,"owner":owner(request)},{"$set":data})
        else: db().products.insert_one(data)
        return JsonResponse({"ok":True,"message":"Product saved"}) if request.headers.get("x-requested-with")=="XMLHttpRequest" else redirect("/products/")
    except Exception as e:
        msg=str(e) or "Could not save product."
        return JsonResponse({"error":msg},status=400) if request.headers.get("x-requested-with")=="XMLHttpRequest" else redirect("/products/")
@signed_in
@require_POST
def delete_product(request,pid):
    if not db().products.update_one({"_id":oid(pid),"owner":owner(request)},{"$set":{"archived":True,"updated":datetime.now(timezone.utc)}}).matched_count: return JsonResponse({"error":"Product not found"},status=404)
    return JsonResponse({"ok":True})
@signed_in
def sales(request): return render(request,"sales.html",{"products":products_for(request),"orders":orders_for(request),"tax":tax(request)})
@signed_in
def deadstock(request): return render(request,"deadstock.html",{})
@signed_in
def deadstock_data(request):
    now=datetime.now(timezone.utc); rows=[]
    for p in products_for(request,True):
        initial=int(p.get("initial_stock",p.get("stock",0))); remaining=int(p.get("stock",0)); expired=int(p.get("expired_qty",0)); removed=int(p.get("removed_qty",0))
        if initial<=0 and remaining<=0 and not p.get("deadstock_status"): continue
        stock_since=p.get("stock_since",p.get("updated",now))
        deadline=p.get("deadline_at") or (stock_since+timedelta(days=int(p.get("deadline_days",30))))
        if deadline.tzinfo is None: deadline=deadline.replace(tzinfo=timezone.utc)
        status=p.get("deadstock_status","active")
        if status=="active" and remaining<=0: status="sold out"
        elif status=="active" and now>=deadline: status="overdue"
        sold=max(0,initial-remaining-expired-removed)
        rows.append({"id":str(p["_id"]),"name":p.get("name","Unnamed item"),"category":p.get("category_name",""),"initial":initial,"sold":sold,"remaining":remaining,"capital":float(p.get("cost",0))*remaining,"deadline":deadline.isoformat(),"status":status,"reason":p.get("deadstock_reason","")})
    return JsonResponse({"items":rows,"count":len(rows),"overdue":sum(1 for x in rows if x["status"]=="overdue"),"remaining":sum(x["remaining"] for x in rows),"capital":sum(x["capital"] for x in rows)})
@signed_in
@require_POST
def deadstock_action(request,pid):
    product=db().products.find_one({"_id":oid(pid),"owner":owner(request)})
    if not product: return JsonResponse({"error":"Item not found"},status=404)
    now=datetime.now(timezone.utc); stock=max(0,int(product.get("stock",0))); deadline=product.get("deadline_at",now)
    if deadline.tzinfo is None: deadline=deadline.replace(tzinfo=timezone.utc)
    if stock<=0 or product.get("deadstock_status") in ("expired","removed"):
        return JsonResponse({"error":"This item has no remaining stock to process."},status=400)
    action=request.POST.get("action"); reason=request.POST.get("reason","").strip()
    if action=="extend":
        try: days=int(request.POST.get("days",30))
        except ValueError: days=0
        if days<1 or days>3650: return JsonResponse({"error":"Choose an extension between 1 and 3650 days."},status=400)
        changes={"deadline_days":days,"deadline_at":now+timedelta(days=days),"deadstock_status":"active","updated":now}
    elif action=="expire":
        if not reason: return JsonResponse({"error":"Add a reason before marking stock expired."},status=400)
        changes={"expired_qty":stock,"stock":0,"deadstock_status":"expired","deadstock_reason":reason,"deadstock_action_at":now,"updated":now}
    elif action=="remove":
        changes={"removed_qty":stock,"stock":0,"deadstock_status":"removed","deadstock_reason":reason,"deadstock_action_at":now,"archived":True,"updated":now}
    else: return JsonResponse({"error":"Choose extend, expire, or remove."},status=400)
    db().products.update_one({"_id":product["_id"],"owner":owner(request)},{"$set":changes})
    db().inventory_events.insert_one({"owner":owner(request),"product_id":product["_id"],"product_name":product.get("name"),"action":action,"quantity":stock,"reason":reason,"days":changes.get("deadline_days"),"created":now})
    return JsonResponse({"ok":True,"message":"Deadline extended" if action=="extend" else ("Stock marked expired" if action=="expire" else "Stock removed and item archived")})
@signed_in
@require_POST
def checkout(request):
    try:
        p=db().products.find_one({"_id":oid(request.POST.get("product_id")),"owner":owner(request),"archived":{"$ne":True}})
        q=max(1,int(request.POST.get("quantity",1)))
        if not p: raise ValueError("Choose a valid product.")
        stock=int(p.get("stock",0))
        if stock and q>stock: raise ValueError("Quantity exceeds available stock.")
        sub=float(p["price"])*q; capital=float(p.get("cost",0))*q; rate=tax(request)
        db().orders.insert_one({"owner":owner(request),"product_id":p["_id"],"product_name":p["name"],"category_id":p["category_id"],"category_name":p["category_name"],"subcategory":p.get("subcategory",""),"quantity":q,"subtotal":sub,"tax":sub*rate/100,"tax_rate":rate,"total":sub*(1+rate/100),"capital":capital,"profit":sub-capital,"status":"pending","created":datetime.now(timezone.utc)})
        if stock: db().products.update_one({"_id":p["_id"]},{"$inc":{"stock":-q}})
        result={"ok":True,"message":"Sale saved as pending"}
        return JsonResponse(result) if request.headers.get("x-requested-with")=="XMLHttpRequest" else redirect("/sales/")
    except ValueError as e: return JsonResponse({"error":str(e)},status=400)
    except Exception: return JsonResponse({"error":"MongoDB unavailable; sale was not recorded."},status=503)
@signed_in
@require_POST
def complete_sale(request, sale_id):
    result=db().orders.update_one({"_id":oid(sale_id),"owner":owner(request)},{"$set":{"status":"completed","completed_at":datetime.now(timezone.utc)}})
    return JsonResponse({"ok":bool(result.matched_count)})
@signed_in
def reports(request): return render(request,"reports.html",{"tax":tax(request),"is_admin":request.session.get("role")=="admin"})
@signed_in
def report_data(request):
    year=int(request.GET.get("year",datetime.now().year)); month=int(request.GET.get("month",0) or 0)
    q={"status":"completed","created":{"$gte":datetime(year,month or 1,1,tzinfo=timezone.utc)}}
    if month:
        end=datetime(year+1,1,1,tzinfo=timezone.utc) if month==12 else datetime(year,month+1,1,tzinfo=timezone.utc)
    else: end=datetime(year+1,1,1,tzinfo=timezone.utc)
    q["created"]["$lt"]=end
    user_rows=[]
    if request.session.get("role")=="admin":
        user_rows=list(db().users.find({"workspace":workspace(request)},{"email":1}))
        member_ids=[str(u["_id"]) for u in user_rows]
        selected=request.GET.get("user","")
        q["owner"]=selected if selected in member_ids else {"$in":member_ids}
        rows=list(db().orders.find(q).sort("created",-1).limit(5000))
    else: rows=orders_for(request,q)
    grouped={}; months={str(i).zfill(2):{"revenue":0,"profit":0} for i in range(1,13)}
    for o in rows:
        key=o.get("category_name","Uncategorized")+" / "+(o.get("subcategory") or "No subcategory")
        g=grouped.setdefault(key,{"category":o.get("category_name","Uncategorized"),"subcategory":o.get("subcategory",""),"revenue":0,"profit":0,"loss":0,"count":0})
        rev=float(o.get("subtotal",0)); prof=float(o.get("profit",0)); g["revenue"]+=rev; g["profit"]+=max(0,prof); g["loss"]+=max(0,-prof); g["count"]+=1
        mo=o["created"].strftime("%m"); months[mo]["revenue"]+=rev; months[mo]["profit"]+=prof
    users=[{"id":str(u["_id"]),"email":u["email"]} for u in user_rows]
    user_label=request.session.get("email","")
    selected=request.GET.get("user","")
    if selected and request.session.get("role")=="admin":
        user_label=next((u["email"] for u in user_rows if str(u["_id"])==selected),"All workspace users")
    elif request.session.get("role")=="admin": user_label="All workspace users"
    return JsonResponse({"year":year,"month":month,"user_label":user_label,"revenue":sum(float(o.get("subtotal",0)) for o in rows),"profit":sum(float(o.get("profit",0)) for o in rows),"count":len(rows),"groups":list(grouped.values()),"months":months,"users":users})
@signed_in
def report_pdf(request):
    data=json.loads(report_data(request).content); buf=io.BytesIO(); pdf=canvas.Canvas(buf,pagesize=landscape(letter)); w,h=landscape(letter)
    pdf.setTitle("Mitra POS sales report"); pdf.setFillColor(colors.HexColor("#20775a")); pdf.setFont("Helvetica-Bold",20); pdf.drawString(42,h-45,"Mitra POS | Completed sales")
    pdf.setFillColor(colors.black); pdf.setFont("Helvetica",10); period=str(data["year"])+(f" / {data['month']:02d}" if data["month"] else " / annual")
    pdf.drawString(42,h-66,f"Period: {period}    User: {data['user_label']}    Sales: {data['count']}    Revenue: Rp {data['revenue']:,.0f}    Profit / loss: Rp {data['profit']:,.0f}")
    y=h-105; pdf.setFont("Helvetica-Bold",10); pdf.drawString(42,y,"Category / subcategory"); pdf.drawString(350,y,"Revenue"); pdf.drawString(470,y,"Profit"); pdf.drawString(570,y,"Loss"); pdf.drawString(675,y,"Orders")
    y-=18; pdf.setFont("Helvetica",9)
    for g in data["groups"]:
        if y<45: pdf.showPage(); y=h-45; pdf.setFont("Helvetica",9)
        pdf.drawString(42,y,(g["category"]+" / "+(g["subcategory"] or "-"))[:48]); pdf.drawRightString(435,y,f"Rp {g['revenue']:,.0f}"); pdf.drawRightString(535,y,f"Rp {g['profit']:,.0f}"); pdf.drawRightString(635,y,f"Rp {g['loss']:,.0f}"); pdf.drawRightString(730,y,str(g["count"])); y-=16
    if not data["month"]:
        if y<85: pdf.showPage(); y=h-45
        y-=16; pdf.setFont("Helvetica-Bold",11); pdf.drawString(42,y,"Monthly totals"); y-=18; pdf.setFont("Helvetica",9)
        for number,values in data["months"].items():
            if y<40: pdf.showPage(); y=h-45; pdf.setFont("Helvetica",9)
            pdf.drawString(42,y,datetime.strptime(number,"%m").strftime("%B")); pdf.drawRightString(435,y,f"Rp {values['revenue']:,.0f}"); pdf.drawRightString(570,y,f"Rp {values['profit']:,.0f}"); y-=14
    pdf.save(); response=HttpResponse(buf.getvalue(),content_type="application/pdf"); response["Content-Disposition"]=f'attachment; filename="sales-{period.replace(" / ","-")}.pdf"'; return response
@signed_in
@admin_only
@require_POST
def save_category(request):
    name=request.POST.get("name","").strip()
    if not name: return JsonResponse({"error":"Category name is required"},status=400)
    try: db().categories.insert_one({"workspace":workspace(request),"name":name,"threshold":float(request.POST.get("threshold",0)),"archived":False,"created":datetime.now(timezone.utc)})
    except Exception: return JsonResponse({"error":"Could not add category"},status=400)
    return JsonResponse({"ok":True})
@signed_in
@admin_only
@require_POST
def set_threshold(request,cat_id):
    raw=request.POST.get("threshold","").strip()
    if not raw:
        result=db().categories.update_one({"_id":oid(cat_id),"workspace":workspace(request)},{"$unset":{"threshold":""}})
        return JsonResponse({"ok":bool(result.matched_count),"message":"Monthly margin target cleared"})
    try: value=float(raw)
    except ValueError: return JsonResponse({"error":"Enter a valid percentage"},status=400)
    if not 0<=value<=100: return JsonResponse({"error":"Margin must be between 0 and 100"},status=400)
    result=db().categories.update_one({"_id":oid(cat_id),"workspace":workspace(request)},{"$set":{"threshold":value}})
    return JsonResponse({"ok":bool(result.matched_count),"message":"Monthly margin target updated"})
@signed_in
@admin_only
def categories(request): return render(request,"categories.html",{"categories":cats_for(request,False)})
@signed_in
@admin_only
@require_POST
def delete_category(request,cat_id):
    category=oid(cat_id)
    if not category or not db().categories.find_one({"_id":category,"workspace":workspace(request)}):
        return JsonResponse({"error":"Category not found"},status=404)
    db().products.update_many({"category_id":category},{"$set":{"archived":True,"updated":datetime.now(timezone.utc)}})
    db().categories.delete_one({"_id":category,"workspace":workspace(request)})
    db().category_decisions.delete_many({"category_id":category})
    return JsonResponse({"ok":True,"message":"Category deleted; related products archived and sales history retained"})
@signed_in
@admin_only
@require_POST
def category_decision(request,cat_id):
    decision=request.POST.get("decision")
    category=oid(cat_id)
    if decision not in ("retain","archive"): return JsonResponse({"error":"Invalid choice"},status=400)
    if not db().categories.find_one({"_id":category,"workspace":workspace(request)}): return JsonResponse({"error":"Category not found"},status=404)
    month=datetime.now().strftime("%Y-%m")
    db().category_decisions.update_one({"owner":owner(request),"category_id":category,"month":month},{"$set":{"decision":decision,"updated":datetime.now(timezone.utc)}},upsert=True)
    db().categories.update_one({"_id":category,"workspace":workspace(request)},{"$set":{"archived":decision=="archive"}})
    if decision=="archive": db().products.update_many({"category_id":category},{"$set":{"archived":True}})
    return JsonResponse({"ok":True})
@signed_in
def margin_alerts(request):
    month=datetime.now().strftime("%Y-%m"); start=datetime.now(timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    cats=cats_for(request); sales=orders_for(request,{"status":"completed","created":{"$gte":start}}); alerts=[]
    for c in cats:
        threshold=float(c.get("threshold") or 0); relevant=[o for o in sales if str(o.get("category_id"))==str(c["_id"])]
        revenue=sum(float(o.get("subtotal",0)) for o in relevant); profit=sum(float(o.get("profit",0)) for o in relevant); margin=(profit/revenue*100) if revenue else 0
        decided=db().category_decisions.find_one({"owner":owner(request),"category_id":c["_id"],"month":month})
        if threshold and margin<threshold and not decided: alerts.append({"id":str(c["_id"]),"name":c["name"],"margin":round(margin,1),"threshold":threshold,"month":month})
    return JsonResponse({"alerts":alerts})
@signed_in
@require_POST
def refresh_tax(request):
    url=os.getenv("TAX_RATE_URL","")
    try:
        if not url: raise ValueError()
        with urllib.request.urlopen(url,timeout=4) as r: rate=float(json.loads(r.read().decode())["rate"])
        if not 0<=rate<=100: raise ValueError()
        db().settings.update_one({"owner":owner(request),"key":"vat"},{"$set":{"rate":rate,"updated":datetime.now(timezone.utc)}},upsert=True)
        return JsonResponse({"ok":True,"rate":rate,"message":f"Tax rate updated to {rate:g}%"})
    except Exception: return JsonResponse({"error":"Refresh unavailable; saved rate or 11% fallback remains active."},status=503)

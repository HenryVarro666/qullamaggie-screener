import json, requests, os
from playwright.sync_api import sync_playwright

API="https://api.deepvue.com"
HOME=os.environ.get("DEEPVUE_DIR", os.path.expanduser("~/.deepvue"))
tok=json.load(open(f"{HOME}/tokens.json"))
UA={"user-agent":"Mozilla/5.0","origin":"https://app.deepvue.com"}
at=requests.post(f"{API}/api/v2/auth/refresh",json={"refreshToken":tok["refreshToken"]},
                 headers={**UA,"content-type":"application/json"}).json()["accessToken"]
tok["accessToken"]=at; json.dump(tok,open(f"{HOME}/tokens.json","w"),indent=2)

SAMESITE={"strict":"Strict","lax":"Lax","no_restriction":"None","none":"None","unspecified":"Lax"}
def load_cookies(path):
    raw=json.load(open(path)); out=[]
    for c in raw:
        ck={"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),
            "secure":bool(c.get("secure",False)),"httpOnly":bool(c.get("httpOnly",False)),
            "sameSite":SAMESITE.get(str(c.get("sameSite","unspecified")).lower(),"Lax")}
        if "expirationDate" in c and not c.get("session",False): ck["expires"]=float(c["expirationDate"])
        if ck["sameSite"]=="None" and not ck["secure"]: ck["secure"]=True
        out.append(ck)
    return out
cookies=load_cookies(f"{HOME}/cookies.json")
init=f"""
localStorage.setItem('accessToken', {json.dumps(at)});
localStorage.setItem('refreshToken', {json.dumps(tok['refreshToken'])});
localStorage.setItem('deviceId', {json.dumps(tok['deviceId'])});
localStorage.setItem('deepvue-chart-device-id', {json.dumps(tok['chartDeviceId'])});
localStorage.setItem('theme','dark-mode'); localStorage.setItem('i18nextLng','en');
"""
COLUMNS=[0,17,3,1878,278,277,2081,225,20]  # symIdx,ticker,last,ADR%20d,perf6M,perf3M,perf1M,avg$vol20d,sector
CHUNK=400

js = r"""
async ([cols, chunk, token, deviceId]) => {
  const J=(o)=>JSON.stringify(o);
  const socketId='sid-'+Math.random().toString(36).slice(2)+Date.now().toString(36);
  const proto=`${socketId}***${token}***${deviceId}`;
  const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
  return await new Promise((resolve)=>{
    const ws=new WebSocket('wss://lightserver.deepvue.com/ws-data',[proto]);
    let indices=null, rowsByIdx={}, started=false;
    const finish=()=>{ try{ws.close()}catch(e){}; resolve({indices_count: indices?indices.length:0, rows:Object.values(rowsByIdx)}); };
    let hardTimer=setTimeout(finish, 60000);
    ws.onmessage=async (ev)=>{
      let m; try{m=JSON.parse(ev.data)}catch(e){return;}
      if(m.event==='Connect.Authorized'){
        ws.send(J({event:'Screener.IndicesList', data:{messageId:Math.floor(Math.random()*1e6), filters:[], sortBy:[]}}));
      } else if(m.event==='Screener.IndicesList' && Array.isArray(m.data&&m.data.data) && !started){
        started=true; indices=m.data.data;
        for(let i=0;i<indices.length;i+=chunk){
          const part=indices.slice(i,i+chunk);
          ws.send(J({event:'Screener.Subscribe', data:{messageId:Math.floor(Math.random()*1e6),
            filters:[[[0,0,part]]], columns:cols, range:[0,part.length], sortBy:[], symbolIndex:0}}));
          await sleep(150);
        }
        // wait for stragglers then finish
        let last=-1, stable=0;
        for(let k=0;k<80;k++){
          await sleep(500);
          const n=Object.keys(rowsByIdx).length;
          if(n>=indices.length){ break; }
          if(n===last){ stable++; if(stable>=6) break; } else { stable=0; last=n; }
        }
        clearTimeout(hardTimer); finish();
      } else if((m.event==='Screener.Subscribe'||m.event==='Screener.Patch') && Array.isArray(m.data&&m.data.data)){
        for(const row of m.data.data){ if(Array.isArray(row)) rowsByIdx[row[0]]=row; }
      }
    };
    ws.onerror=()=>{ clearTimeout(hardTimer); finish(); };
  });
}
"""

with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    ctx=b.new_context(); ctx.add_cookies(cookies); ctx.add_init_script(init)
    page=ctx.new_page()
    page.goto("https://app.deepvue.com/?p=screener", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3500)
    res=page.evaluate(js, [COLUMNS, CHUNK, at, tok["deviceId"]])
    b.close()

rows=res["rows"]
json.dump({"columns":COLUMNS,"rows":rows}, open("/tmp/dv_universe.json","w"))
print("universe indices:", res["indices_count"], "| rows fetched:", len(rows))
ci={c:i for i,c in enumerate(COLUMNS)}
v=lambda r,c: r[ci[c]] if r and ci[c]<len(r) else None
num=lambda x: x if isinstance(x,(int,float)) else None
# Breakout client-side filter
def ok(r):
    last,adr,p6,p3,p1,dv,sec=num(v(r,3)),num(v(r,1878)),num(v(r,278)),num(v(r,277)),num(v(r,2081)),num(v(r,225)),v(r,20)
    if None in (last,adr,p6,p3,p1,dv): return False
    if sec in (None,"N/A",""): return False
    # method floors (from screening.md): price>=1, ADR%>=3, perf6M>=20%, avg$vol20d>=500k
    if not (last>=1 and adr>=0.03 and p6>=0.20 and dv>=500000 and p6<=20): return False
    # uptrend guard: still a Stage-2 leader, not a collapsed ex-runner
    if p3 < 0.05: return False          # last 3M must still be up
    if p1 < -0.20: return False         # allow consolidation/pullback, drop collapses
    return True
cand=[r for r in rows if ok(r)]
cand.sort(key=lambda r:num(v(r,278)) or -9, reverse=True)
print("breakout candidates:", len(cand))
top=cand[:10]
json.dump({"columns":COLUMNS,"top":top}, open("/tmp/dv_top.json","w"), indent=2)
print("\n=== TOP 10 BREAKOUT (by Perf 6M) ===")
print(f"{'#':>2} {'Tkr':<6} {'Last':>8} {'ADR%':>6} {'6M%':>7} {'3M%':>7} {'1M%':>7} {'$Vol(M)':>8}  Sector")
for i,r in enumerate(top,1):
    print(f"{i:>2} {v(r,17):<6} {num(v(r,3)):>8.2f} {num(v(r,1878))*100:>6.1f} {num(v(r,278))*100:>7.1f} "
          f"{(num(v(r,277)) or 0)*100:>7.1f} {(num(v(r,2081)) or 0)*100:>7.1f} {num(v(r,225))/1e6:>8.1f}  {v(r,20)}")

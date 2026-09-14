import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Activity, BarChart3, CheckCircle2, ClipboardCheck, Database, Image,
  LayoutDashboard, LogOut, Package, Play, RefreshCw, Settings, ShieldCheck,
  Sparkles, Upload, UserPlus, Video, WandSparkles, XCircle,
} from 'lucide-react'
import { api, auth, Product, Task, User } from './api'

type Page = 'dashboard' | 'products' | 'tasks' | 'approvals' | 'review' | 'import' | 'settings'
type Dashboard = { product_count: number; active_rate: number; gmv: number; inventory_warnings: Product[]; pending_approvals: number; trend: number[] }
type ProductDetail = { product: Product; competitors: Array<{id:number; name:string; price:number; highlights:string}>; contents: Array<{id:number; type:string; status:string; revision:number; payload:Record<string, unknown>}>; experiment?: Experiment; metrics?: Metric }
type Experiment = { id:number; product_id?:number; title:string; status:string; strategy:Record<string, unknown>; decision_note?:string }
type Metric = { period:string; impressions:number; clicks:number; paid_orders:number; gmv:number; ad_spend:number; ctr:number|null; conversion_rate:number|null; roas:number|null }

const nav: Array<{id:Page; label:string; icon:typeof LayoutDashboard}> = [
  { id:'dashboard', label:'运营大盘', icon:LayoutDashboard },
  { id:'products', label:'商品工作台', icon:Package },
  { id:'tasks', label:'生成任务', icon:Activity },
  { id:'approvals', label:'投放审批', icon:ClipboardCheck },
  { id:'review', label:'经营复盘', icon:BarChart3 },
  { id:'import', label:'数据导入', icon:Upload },
  { id:'settings', label:'模型配置', icon:Settings },
]

const statusText: Record<string,string> = { queued:'排队中', running:'生成中', succeeded:'已完成', failed:'失败', cancelled:'已取消', timeout:'超时', submitted:'待审批', approved:'已通过', rejected:'已驳回', confirmed:'已确认', draft:'草稿' }

function money(value:number) { return new Intl.NumberFormat('zh-CN', { style:'currency', currency:'CNY', maximumFractionDigits:0 }).format(value) }

function Login({onLogin}:{onLogin:(u:User)=>void}) {
  const [mode,setMode] = useState<'login'|'register'|'forgot'>('login')
  const [account,setAccount] = useState('operator')
  const [password,setPassword] = useState('')
  const [email,setEmail] = useState('operator@example.com')
  const [username,setUsername] = useState('demo_user')
  const [message,setMessage] = useState('')
  const [busy,setBusy] = useState(false)
  async function submit(e:FormEvent) {
    e.preventDefault(); setBusy(true); setMessage('')
    try {
      if (mode === 'forgot') {
        const r = await api<{message:string;debug_reset_token?:string}>('/api/auth/forgot-password',{method:'POST',body:JSON.stringify({email})})
        setMessage(r.debug_reset_token ? `${r.message}（演示令牌：${r.debug_reset_token}）` : r.message)
      } else {
        const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
        const body = mode === 'login' ? {account,password} : {username,email,password}
        const r = await api<{access_token:string;user:User}>(path,{method:'POST',body:JSON.stringify(body)})
        auth.token=r.access_token; onLogin(r.user)
      }
    } catch (e) { setMessage(e instanceof Error ? e.message : '操作失败') }
    finally { setBusy(false) }
  }
  return <div className="login-shell">
    <div className="login-visual">
      <div className="brand"><span><Sparkles size={22}/></span>星策 AI</div>
      <div className="hero-copy"><div className="eyebrow">E-COMMERCE COPILOT</div><h1>让每一次上新<br/>都有数据和创意支撑</h1><p>从竞品诊断、内容生成到投放审批与经营复盘，一站式完成手机新品冷启动。</p></div>
      <div className="hero-stats"><div><b>3×</b><span>创意方向</span></div><div><b>AI</b><span>异步工作流</span></div><div><b>闭环</b><span>投放与复盘</span></div></div>
    </div>
    <div className="login-panel"><form className="login-card" onSubmit={submit}>
      <div className="mobile-brand"><Sparkles/> 星策 AI</div>
      <h2>{mode==='login'?'欢迎回来':mode==='register'?'创建运营账号':'找回密码'}</h2>
      <p>{mode==='login'?'登录电商运营智能工作台':mode==='register'?'注册账号默认获得运营人员权限':'演示环境会返回一次性重置令牌'}</p>
      {mode==='register' && <label>用户名<input value={username} onChange={e=>setUsername(e.target.value)} required/></label>}
      {mode==='login' ? <label>账号或邮箱<input value={account} onChange={e=>setAccount(e.target.value)} required/></label> : <label>邮箱<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label>}
      {mode!=='forgot' && <label>密码<input type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={8} required/></label>}
      {message && <div className="form-message">{message}</div>}
      <button className="primary wide" disabled={busy}>{busy?'处理中…':mode==='login'?'登录工作台':mode==='register'?'立即注册':'获取重置令牌'}</button>
      {mode==='login' && <div className="demo-accounts"><span>演示账号</span><button type="button" onClick={()=>{setAccount('operator');setPassword('')}}>运营人员</button><button type="button" onClick={()=>{setAccount('manager');setPassword('')}}>运营主管</button></div>}
      <div className="login-links">{mode!=='login' && <button type="button" onClick={()=>setMode('login')}>返回登录</button>}{mode==='login' && <><button type="button" onClick={()=>setMode('register')}><UserPlus size={15}/>注册</button><button type="button" onClick={()=>setMode('forgot')}>忘记密码</button></>}</div>
    </form></div>
  </div>
}

export default function App() {
  const [user,setUser] = useState<User|null>(null)
  const [page,setPage] = useState<Page>('dashboard')
  const [dash,setDash] = useState<Dashboard|null>(null)
  const [products,setProducts] = useState<Product[]>([])
  const [selected,setSelected] = useState<number|null>(null)
  const [detail,setDetail] = useState<ProductDetail|null>(null)
  const [tasks,setTasks] = useState<Task[]>([])
  const [experiments,setExperiments] = useState<Experiment[]>([])
  const [notice,setNotice] = useState('')
  const [loading,setLoading] = useState(false)

  async function loadBase() {
    setLoading(true)
    try {
      const [d,p,t,e] = await Promise.all([api<Dashboard>('/api/dashboard'),api<Product[]>('/api/products'),api<Task[]>('/api/tasks'),api<Experiment[]>('/api/experiments')])
      setDash(d); setProducts(p); setTasks(t); setExperiments(e)
      const id=selected || p[0]?.id; if(id){setSelected(id);setDetail(await api<ProductDetail>(`/api/products/${id}`))}
    } catch(e) { setNotice(e instanceof Error?e.message:'加载失败') }
    finally { setLoading(false) }
  }
  useEffect(()=>{ if(auth.token) api<User>('/api/auth/me').then(setUser).catch(()=>auth.token='') },[])
  useEffect(()=>{ if(user) loadBase() },[user])
  useEffect(()=>{ if(!user || !tasks.some(t=>['queued','running'].includes(t.status))) return; const timer=setInterval(loadBase,2500); return()=>clearInterval(timer) },[user,tasks])
  async function selectProduct(id:number){setSelected(id);setDetail(await api<ProductDetail>(`/api/products/${id}`))}
  async function generate(kind:'diagnosis'|'creative'|'image'|'video') {
    if(!selected)return; const title={diagnosis:'AI 商品诊断',creative:'主图与短视频创意',image:'电商主图生成',video:'商品短视频生成'}[kind]
    await api(`/api/products/${selected}/generate`,{method:'POST',body:JSON.stringify({kind,title})}); setNotice(`${title}已提交`); setPage('tasks'); await loadBase()
  }
  function logout(){auth.token='';setUser(null);setDash(null)}
  if(!user) return <Login onLogin={setUser}/>
  const title=nav.find(x=>x.id===page)?.label
  return <div className="app-shell">
    <aside><div className="brand"><span><Sparkles size={20}/></span>星策 AI</div><div className="workspace-label">运营工作台</div><nav>{nav.map(n=><button key={n.id} className={page===n.id?'active':''} onClick={()=>setPage(n.id)}><n.icon size={19}/>{n.label}{n.id==='approvals'&&experiments.filter(x=>x.status==='submitted').length>0&&<i>{experiments.filter(x=>x.status==='submitted').length}</i>}</button>)}</nav><div className="side-foot"><div className="avatar">{user.username[0].toUpperCase()}</div><div><b>{user.username}</b><span>{user.role==='manager'?'运营主管':'运营人员'}</span></div><button onClick={logout}><LogOut size={18}/></button></div></aside>
    <main><header><div><div className="breadcrumb">电商运营助手 / {title}</div><h1>{title}</h1></div><div className="header-actions"><span className="mode-pill"><span/>AI 工作流</span><button className="icon-btn" onClick={loadBase} title="刷新"><RefreshCw size={18} className={loading?'spin':''}/></button></div></header>
      {notice&&<div className="toast" onClick={()=>setNotice('')}><CheckCircle2 size={18}/>{notice}</div>}
      {page==='dashboard'&&<DashboardPage data={dash} products={products} onProduct={id=>{selectProduct(id);setPage('products')}}/>}
      {page==='products'&&<ProductsPage products={products} detail={detail} selected={selected} onSelect={selectProduct} onGenerate={generate}/>}
      {page==='tasks'&&<TasksPage tasks={tasks} onAction={async(id,act)=>{await api(`/api/tasks/${id}/${act}`,{method:'POST'});await loadBase()}}/>}
      {page==='approvals'&&<ApprovalsPage user={user} items={experiments} onDecision={async(id,decision)=>{await api(`/api/experiments/${id}/decision`,{method:'POST',body:JSON.stringify({decision,note:decision==='approved'?'符合小预算测款规则，同意执行':'请补充素材差异化与止损阈值'})});await loadBase()}}/>}
      {page==='review'&&<ReviewPage products={products} selected={selected} onSelect={selectProduct} detail={detail}/>}
      {page==='import'&&<ImportPage/>}
      {page==='settings'&&<SettingsPage manager={user.role==='manager'}/>}
    </main>
  </div>
}

function DashboardPage({data,products,onProduct}:{data:Dashboard|null;products:Product[];onProduct:(id:number)=>void}) {
  const max=Math.max(...(data?.trend||[1])); return <>
    <section className="welcome"><div><span>今日运营简报</span><h2>手机新品冷启动正在稳步推进</h2><p>曜石 X1 已完成竞品诊断，建议优先验证“夜景影像 + 长续航”主图方向。</p><button className="primary" onClick={()=>products[0]&&onProduct(products[0].id)}><WandSparkles size={17}/>进入商品工作台</button></div><img src="/images/demo-phone.png"/></section>
    <section className="stat-grid"><Stat label="商品总数" value={String(data?.product_count??'—')} hint="当前在售商品" icon={Package}/><Stat label="累计 GMV" value={data?money(data.gmv):'—'} hint="演示数据口径" icon={BarChart3}/><Stat label="动销率" value={`${data?.active_rate??0}%`} hint="有支付商品 / 在售商品" icon={Activity}/><Stat label="待审批" value={String(data?.pending_approvals??0)} hint="需要运营主管处理" icon={ClipboardCheck}/></section>
    <section className="two-cols"><div className="panel"><div className="panel-head"><div><span>GMV 趋势</span><h3>近 7 个数据周期</h3></div><span className="positive">+18.6%</span></div><div className="bars">{(data?.trend||[]).map((x,i)=><div key={i}><span style={{height:`${x/max*100}%`}}/><small>第{i+1}期</small></div>)}</div></div><div className="panel"><div className="panel-head"><div><span>库存提醒</span><h3>需要关注的商品</h3></div></div>{data?.inventory_warnings.length?<div className="warning-list">{data.inventory_warnings.map(p=><button onClick={()=>onProduct(p.id)} key={p.id}><img src={p.image_url}/><span><b>{p.name}</b><small>库存 {p.inventory} · 阈值 {p.warning_threshold}</small></span><i>偏低</i></button>)}</div>:<Empty text="当前没有库存预警"/>}</div></section>
  </>
}
function Stat({label,value,hint,icon:Icon}:{label:string;value:string;hint:string;icon:typeof Package}){return <div className="stat-card"><span className="stat-icon"><Icon size={20}/></span><div><small>{label}</small><strong>{value}</strong><p>{hint}</p></div></div>}

function ProductsPage({products,detail,selected,onSelect,onGenerate}:{products:Product[];detail:ProductDetail|null;selected:number|null;onSelect:(id:number)=>void;onGenerate:(k:'diagnosis'|'creative'|'image'|'video')=>void}) {
 return <div className="workbench"><div className="product-rail"><h3>商品列表</h3>{products.map(p=><button key={p.id} className={selected===p.id?'selected':''} onClick={()=>onSelect(p.id)}><img src={p.image_url}/><span><b>{p.name}</b><small>{p.category} · {money(p.price)}</small></span></button>)}</div><div className="work-content">{!detail?<Empty text="暂无商品"/>:<><div className="product-hero"><img src={detail.product.image_url}/><div><span className="tag">{detail.product.status==='on_sale'?'在售':'草稿'}</span><h2>{detail.product.name}</h2><p>{detail.product.summary}</p><div className="product-meta"><span>售价 <b>{money(detail.product.price)}</b></span><span>库存 <b>{detail.product.inventory}</b></span><span>竞品 <b>{detail.competitors.length}</b></span></div></div></div><div className="action-grid"><Action icon={Sparkles} title="AI 商品诊断" desc="分析卖点、用户痛点与竞品机会" onClick={()=>onGenerate('diagnosis')}/><Action icon={WandSparkles} title="生成创意方案" desc="输出 3 组主图方向和视频脚本" onClick={()=>onGenerate('creative')}/><Action icon={Image} title="生成商品主图" desc="基于已确认创意创建视觉素材" onClick={()=>onGenerate('image')}/><Action icon={Video} title="生成短视频" desc="异步创建 9:16 手机商品视频" onClick={()=>onGenerate('video')}/></div><div className="two-cols"><div className="panel"><div className="panel-head"><h3>竞品对比</h3></div><table><thead><tr><th>竞品</th><th>价格</th><th>核心卖点</th></tr></thead><tbody>{detail.competitors.map(c=><tr key={c.id}><td>{c.name}</td><td>{money(c.price)}</td><td>{c.highlights}</td></tr>)}</tbody></table></div><div className="panel"><div className="panel-head"><h3>内容资产</h3><span>{detail.contents.length} 份</span></div><div className="content-list">{detail.contents.map(c=><div key={c.id}><span className="doc-icon">{c.type==='diagnosis'?'诊':'创'}</span><div><b>{c.type==='diagnosis'?'商品诊断报告':'创意方案'}</b><small>版本 {c.revision} · {statusText[c.status]||c.status}</small></div></div>)}</div></div></div></>}</div></div>
}
function Action({icon:Icon,title,desc,onClick}:{icon:typeof Sparkles;title:string;desc:string;onClick:()=>void}){return <button className="action-card" onClick={onClick}><span><Icon/></span><div><b>{title}</b><small>{desc}</small></div><Play size={16}/></button>}

function TasksPage({tasks,onAction}:{tasks:Task[];onAction:(id:number,a:'cancel'|'retry')=>void}){return <div className="panel"><div className="panel-head"><div><span>异步工作流</span><h3>最近 50 个生成任务</h3></div><div className="legend"><i className="dot green"/>真实/模拟模式均记录</div></div><div className="task-list">{tasks.map(t=><div className="task-row" key={t.id}><div className={`task-kind ${t.kind}`}>{t.kind==='video'?<Video/>:t.kind==='image'?<Image/>:<Sparkles/>}</div><div className="task-main"><b>{t.title}</b><small>{t.provider_mode==='mock'?'Mock 演示':'真实调用'} · 任务 #{t.id}</small><div className="progress"><span style={{width:`${t.progress}%`}}/></div></div><span className={`status ${t.status}`}>{statusText[t.status]||t.status}</span>{['queued','running'].includes(t.status)&&<button className="text-btn danger" onClick={()=>onAction(t.id,'cancel')}>取消</button>}{['failed','timeout','cancelled'].includes(t.status)&&<button className="text-btn" onClick={()=>onAction(t.id,'retry')}>重试</button>}</div>)}{!tasks.length&&<Empty text="还没有生成任务"/>}</div></div>}

function ApprovalsPage({user,items,onDecision}:{user:User;items:Experiment[];onDecision:(id:number,d:'approved'|'rejected')=>void}){return <div className="approval-grid">{items.map(x=><article className="approval-card" key={x.id}><div className="approval-top"><span className={`status ${x.status}`}>{statusText[x.status]||x.status}</span><small>方案 #{x.id}</small></div><h3>{x.title}</h3><p>AI 建议以小预算分组测款，比较夜景影像、长续航和服务保障三类素材方向。</p><div className="strategy"><div><span>测试预算</span><b>¥300 / 组</b></div><div><span>目标 CTR</span><b>≥ 3.2%</b></div><div><span>止损条件</span><b>ROAS &lt; 1.5</b></div></div>{x.decision_note&&<div className="decision-note">审批意见：{x.decision_note}</div>}{x.status==='submitted'&&user.role==='manager'?<div className="approve-actions"><button className="outline danger" onClick={()=>onDecision(x.id,'rejected')}><XCircle size={17}/>驳回</button><button className="primary" onClick={()=>onDecision(x.id,'approved')}><CheckCircle2 size={17}/>确认通过</button></div>:x.status==='submitted'?<div className="role-tip"><ShieldCheck/>已提交，等待运营主管审批</div>:null}</article>)}{!items.length&&<div className="panel"><Empty text="暂无投放方案"/></div>}</div>}

function ReviewPage({products,selected,onSelect,detail}:{products:Product[];selected:number|null;onSelect:(id:number)=>void;detail:ProductDetail|null}){const m=detail?.metrics;return <><div className="filter-bar"><label>复盘商品<select value={selected||''} onChange={e=>onSelect(Number(e.target.value))}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label><span>指标口径：GMV 不扣退款 · ROAS = GMV / 广告花费</span></div>{m?<><section className="stat-grid review-stats"><Stat label="曝光量" value={m.impressions.toLocaleString()} hint={m.period} icon={Activity}/><Stat label="CTR" value={`${m.ctr??'—'}%`} hint="点击量 / 曝光量" icon={BarChart3}/><Stat label="转化率" value={`${m.conversion_rate??'—'}%`} hint="支付订单 / 点击量" icon={CheckCircle2}/><Stat label="ROAS" value={String(m.roas??'—')} hint={`GMV ${money(m.gmv)}`} icon={Sparkles}/></section><div className="two-cols"><div className="panel review-block"><h3>本轮结论</h3><p>影像卖点主图具备点击吸引力，详情页信任证据仍有提升空间。建议保留高点击方向，同时优化服务承诺和真实样张表达。</p><div className="insight positive-bg">CTR 达到演示目标，主图方向可进入下一轮验证。</div></div><div className="panel review-block"><h3>下一轮行动</h3><ol><li>补充夜景人像原片与竞品对比</li><li>突出 30 天无忧换机服务</li><li>测试长续航场景化短视频素材</li></ol></div></div></>:<div className="panel"><Empty text="该商品暂无经营指标，请先回填演示数据"/></div>}</>}

function ImportPage(){const [result,setResult]=useState<any>(null);const [busy,setBusy]=useState(false);async function upload(file:File){setBusy(true);try{const fd=new FormData();fd.append('file',file);setResult(await api('/api/imports/preview',{method:'POST',body:fd}))}catch(e){setResult({error:e instanceof Error?e.message:'上传失败'})}finally{setBusy(false)}}return <div className="panel import-panel"><div className="upload-zone"><Upload size={36}/><h3>{busy?'正在解析…':'上传经营数据'}</h3><p>支持 CSV、XLSX，演示版单文件不超过 5 MB；提交前仅做预览，不直接写库。</p><label className="primary">选择文件<input type="file" accept=".csv,.xlsx" hidden onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/></label></div>{result&&<div className="import-result">{result.error?<div className="error-box">{result.error}</div>:<><h3>{result.filename}</h3><p>已预览 {result.row_count_previewed} 行 · 字段：{result.columns.join('、')}</p>{result.rows?.length>0&&<pre>{JSON.stringify(result.rows.slice(0,5),null,2)}</pre>}</>}</div>}</div>}

function SettingsPage({manager}:{manager:boolean}){const [data,setData]=useState<any>(null);const [error,setError]=useState('');useEffect(()=>{if(manager)api('/api/settings').then(setData).catch(e=>setError(e.message))},[manager]);if(!manager)return <div className="panel"><Empty text="仅运营主管可以查看模型与运行配置"/></div>;return <div className="settings-grid"><div className="panel settings-summary"><span className="settings-icon"><Database/></span><div><small>运行模式</small><h2>{data?.ai_mode==='live'?'真实模型调用':'Mock 演示模式'}</h2><p>{data?.base_url||'加载中…'}</p></div><span className={`status ${data?.api_key_configured?'succeeded':'queued'}`}>{data?.api_key_configured?'Key 已配置':'等待配置 Key'}</span></div><div className="panel"><div className="panel-head"><h3>模型路由</h3><span>Worker 并发 {data?.worker_concurrency??1}</span></div>{error&&<div className="error-box">{error}</div>}<div className="model-list">{data&&Object.entries(data.models).map(([k,v])=><div key={k}><span>{k.toUpperCase()}</span><b>{String(v)}</b></div>)}</div><div className="security-note"><ShieldCheck/><span>模型密钥仅通过服务器 `.env` 注入，页面不会返回密钥原文。</span></div></div></div>}

function Empty({text}:{text:string}){return <div className="empty"><Package size={34}/><p>{text}</p></div>}

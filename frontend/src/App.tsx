import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Activity, BarChart3, CheckCircle2, ClipboardCheck, Database, Image,
  LayoutDashboard, LogOut, Package, Play, RefreshCw, Settings, ShieldCheck,
  Sparkles, Upload, UserPlus, Video, WandSparkles, XCircle,
} from 'lucide-react'
import { api, auth, Product, Task, User } from './api'

type Page = 'dashboard' | 'products' | 'tasks' | 'approvals' | 'review' | 'import' | 'settings'
type WorkflowKind = 'diagnosis'|'creative'|'image'|'video'|'strategy'|'review'
type Dashboard = { product_count: number; active_rate: number; gmv: number; inventory_warnings: Product[]; pending_approvals: number; trend: number[] }
type ProductDetail = { product: Product; competitors: Array<{id:number; name:string; price:number; highlights:unknown; highlights_text?:string}>; contents: Array<{id:number; type:string; status:string; revision:number; payload:Record<string, unknown>}>; experiment?: Experiment; metrics?: Metric }
type Experiment = { id:number; product_id?:number; title:string; status:string; strategy:Record<string, unknown>; decision_note?:string }
type ExperimentDraft = { product_id:number; title:string; audience:string; channel:string; budget:number; period:string; creative_angle:string; target_ctr:number; stop_roas:number }
type Metric = { period:string; impressions:number; clicks:number; paid_orders:number; gmv:number; ad_spend:number; ctr:number|null; conversion_rate:number|null; roas:number|null }
type TaskResult = { task:Task; product:Product|null; content:{id:number;type:string;status:string;revision:number;payload:Record<string,unknown>}|null; experiment:Experiment|null; result_url:string|null }
type ImportPreview = { status:'preview'; can_import:boolean; message:string; filename:string; row_count_total:number; row_count_previewed:number; columns:string[]; rows:Array<Record<string,unknown>>; validation_errors:string[] }
type ImportCommit = { status:'imported'; rows_imported:number; products_created:number; products_updated:number; metrics_created:number; metrics_updated:number }

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
function displayHighlights(value:unknown):string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(displayHighlights).filter(Boolean).join(' · ')
  if (value && typeof value === 'object') return Object.values(value).map(displayHighlights).filter(Boolean).join(' · ')
  return value == null ? '—' : String(value)
}
function ProductImage({product,className=''}:{product:Product;className?:string}) {
  const marker='#tile='
  if(product.image_url.includes(marker)) {
    const tile=Number(product.image_url.split(marker)[1]||0)
    const column=tile%4
    const row=Math.floor(tile/4)
    return <span role="img" aria-label={product.name} className={`product-image sprite-image ${className}`} style={{backgroundImage:'url(/images/product-catalog-grid.png)',backgroundPosition:`${column*100/3}% ${row*100/3}%`}}/>
  }
  return <img className={`product-image ${className}`} src={product.image_url} alt={product.name}/>
}

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
  const [taskResult,setTaskResult] = useState<TaskResult|null>(null)
  const [resultLoading,setResultLoading] = useState(false)

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
  async function generateForProduct(productId:number,kind:WorkflowKind) {
    const title={diagnosis:'AI 商品诊断',creative:'主图与短视频创意',image:'电商主图生成',video:'商品短视频生成',strategy:'AI 投放建议',review:'AI 经营复盘'}[kind]
    await api(`/api/products/${productId}/generate`,{method:'POST',body:JSON.stringify({kind,title})}); setNotice(`${title}已提交`); setPage('tasks'); await loadBase()
  }
  async function generate(kind:WorkflowKind) { if(selected)await generateForProduct(selected,kind) }
  async function viewTaskResult(id:number) {
    setResultLoading(true)
    try { setTaskResult(await api<TaskResult>(`/api/tasks/${id}/result`)) }
    catch(e) { setNotice(e instanceof Error?e.message:'结果加载失败') }
    finally { setResultLoading(false) }
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
      {page==='tasks'&&<TasksPage tasks={tasks} resultLoading={resultLoading} onView={viewTaskResult} onAction={async(id,act)=>{await api(`/api/tasks/${id}/${act}`,{method:'POST'});await loadBase()}}/>}
      {page==='approvals'&&<ApprovalsPage user={user} products={products} items={experiments} onGenerate={id=>generateForProduct(id,'strategy')} onCreate={async body=>{await api('/api/experiments',{method:'POST',body:JSON.stringify(body)});setNotice('投放方案草稿已创建');await loadBase()}} onSubmit={async id=>{await api(`/api/experiments/${id}/submit`,{method:'POST'});setNotice('投放方案已提交主管审批');await loadBase()}} onDecision={async(id,decision)=>{await api(`/api/experiments/${id}/decision`,{method:'POST',body:JSON.stringify({decision,note:decision==='approved'?'符合小预算测款规则，同意执行':'请补充素材差异化与止损阈值'})});await loadBase()}}/>}
      {page==='review'&&<ReviewPage products={products} selected={selected} onSelect={selectProduct} detail={detail} onGenerate={()=>generate('review')}/>}
      {page==='import'&&<ImportPage onImported={loadBase}/>}
      {page==='settings'&&<SettingsPage manager={user.role==='manager'}/>}
    </main>
    {taskResult&&<ResultModal result={taskResult} onClose={()=>setTaskResult(null)}/>}
  </div>
}

function DashboardPage({data,products,onProduct}:{data:Dashboard|null;products:Product[];onProduct:(id:number)=>void}) {
  const max=Math.max(...(data?.trend||[1])); return <>
    <section className="welcome"><div><span>今日运营简报</span><h2>手机新品冷启动正在稳步推进</h2><p>曜石 X1 已完成竞品诊断，建议优先验证“夜景影像 + 长续航”主图方向。</p><button className="primary" onClick={()=>products[0]&&onProduct(products[0].id)}><WandSparkles size={17}/>进入商品工作台</button></div><img src="/images/demo-phone.png"/></section>
    <section className="stat-grid"><Stat label="商品总数" value={String(data?.product_count??'—')} hint="当前在售商品" icon={Package}/><Stat label="累计 GMV" value={data?money(data.gmv):'—'} hint="演示数据口径" icon={BarChart3}/><Stat label="动销率" value={`${data?.active_rate??0}%`} hint="有支付商品 / 在售商品" icon={Activity}/><Stat label="待审批" value={String(data?.pending_approvals??0)} hint="需要运营主管处理" icon={ClipboardCheck}/></section>
    <section className="two-cols"><div className="panel"><div className="panel-head"><div><span>GMV 趋势</span><h3>近 7 个数据周期</h3></div><span className="positive">+18.6%</span></div><div className="bars">{(data?.trend||[]).map((x,i)=><div key={i}><span style={{height:`${x/max*100}%`}}/><small>第{i+1}期</small></div>)}</div></div><div className="panel"><div className="panel-head"><div><span>库存提醒</span><h3>需要关注的商品</h3></div></div>{data?.inventory_warnings.length?<div className="warning-list">{data.inventory_warnings.map(p=><button onClick={()=>onProduct(p.id)} key={p.id}><ProductImage product={p}/><span><b>{p.name}</b><small>库存 {p.inventory} · 阈值 {p.warning_threshold}</small></span><i>偏低</i></button>)}</div>:<Empty text="当前没有库存预警"/>}</div></section>
  </>
}
function Stat({label,value,hint,icon:Icon}:{label:string;value:string;hint:string;icon:typeof Package}){return <div className="stat-card"><span className="stat-icon"><Icon size={20}/></span><div><small>{label}</small><strong>{value}</strong><p>{hint}</p></div></div>}

function ProductsPage({products,detail,selected,onSelect,onGenerate}:{products:Product[];detail:ProductDetail|null;selected:number|null;onSelect:(id:number)=>void;onGenerate:(k:WorkflowKind)=>void}) {
 return <div className="workbench"><div className="product-rail"><h3>商品列表</h3>{products.map(p=><button key={p.id} className={selected===p.id?'selected':''} onClick={()=>onSelect(p.id)}><ProductImage product={p}/><span><b>{p.name}</b><small>{p.category} · {money(p.price)}</small></span></button>)}</div><div className="work-content">{!detail?<Empty text="暂无商品"/>:<><div className="product-hero"><ProductImage product={detail.product}/><div><span className="tag">{detail.product.status==='on_sale'?'在售':'草稿'}</span><h2>{detail.product.name}</h2><p>{detail.product.summary}</p><div className="product-meta"><span>售价 <b>{money(detail.product.price)}</b></span><span>库存 <b>{detail.product.inventory}</b></span><span>竞品 <b>{detail.competitors.length}</b></span></div></div></div><div className="action-grid"><Action icon={Sparkles} title="AI 商品诊断" desc="分析卖点、用户痛点与竞品机会" onClick={()=>onGenerate('diagnosis')}/><Action icon={WandSparkles} title="生成创意方案" desc="输出 3 组主图方向和视频脚本" onClick={()=>onGenerate('creative')}/><Action icon={Image} title="生成商品主图" desc="真实调用图片模型并保存结果" onClick={()=>onGenerate('image')}/><Action icon={Video} title="生成短视频" desc="真实调用 Wan2.2 异步生成 9:16 视频" onClick={()=>onGenerate('video')}/></div><div className="two-cols"><div className="panel"><div className="panel-head"><h3>竞品对比</h3></div><table><thead><tr><th>竞品</th><th>价格</th><th>核心卖点</th></tr></thead><tbody>{detail.competitors.map(c=><tr key={c.id}><td>{c.name}</td><td>{money(c.price)}</td><td>{c.highlights_text||displayHighlights(c.highlights)}</td></tr>)}</tbody></table></div><div className="panel"><div className="panel-head"><h3>内容资产</h3><span>{detail.contents.length} 份</span></div><div className="content-list">{detail.contents.map(c=><div key={c.id}><span className="doc-icon">{c.type==='diagnosis'?'诊':'创'}</span><div><b>{c.type==='diagnosis'?'商品诊断报告':'创意方案'}</b><small>版本 {c.revision} · {statusText[c.status]||c.status}</small></div></div>)}</div></div></div></>}</div></div>
}
function Action({icon:Icon,title,desc,onClick}:{icon:typeof Sparkles;title:string;desc:string;onClick:()=>void}){return <button className="action-card" onClick={onClick}><span><Icon/></span><div><b>{title}</b><small>{desc}</small></div><Play size={16}/></button>}

function TasksPage({tasks,resultLoading,onView,onAction}:{tasks:Task[];resultLoading:boolean;onView:(id:number)=>void;onAction:(id:number,a:'cancel'|'retry')=>void}){return <div className="panel"><div className="panel-head"><div><span>异步工作流</span><h3>最近 50 个生成任务</h3></div><div className="legend"><i className="dot green"/>真实/模拟模式均记录</div></div><div className="task-list">{tasks.map(t=><div className="task-row" key={t.id}><div className={`task-kind ${t.kind}`}>{t.kind==='video'?<Video/>:t.kind==='image'?<Image/>:<Sparkles/>}</div><div className="task-main"><b>{t.title}</b><small>{t.provider_mode==='mock'?'Mock 演示':'真实调用'} · 任务 #{t.id}</small>{t.error_message&&<p className="task-error">{t.error_message}</p>}<div className="progress"><span style={{width:`${t.progress}%`}}/></div></div><span className={`status ${t.status}`}>{statusText[t.status]||t.status}</span>{t.status==='succeeded'&&<button className="text-btn" disabled={resultLoading} onClick={()=>onView(t.id)}>查看结果</button>}{['queued','running'].includes(t.status)&&<button className="text-btn danger" onClick={()=>onAction(t.id,'cancel')}>取消</button>}{['failed','timeout','cancelled'].includes(t.status)&&t.retryable!==false&&<button className="text-btn" onClick={()=>onAction(t.id,'retry')}>重试</button>}{t.status==='failed'&&t.retryable===false&&<span className="retry-blocked">需处理额度/权限</span>}</div>)}{!tasks.length&&<Empty text="还没有生成任务"/>}</div></div>}

const resultLabels:Record<string,string>={diagnosis:'商品诊断',conclusion:'诊断结论',product_basic_info:'商品基础信息',name:'商品名称',price:'商品价格',category:'商品类目',compliance_statement:'依据说明',positioning_analysis:'定位分析',price_segment:'价格带',core_attribute:'核心属性',positioning_logic:'定位依据',operational_diagnosis:'运营诊断',data_limitation:'数据边界',traffic_matching:'流量匹配',price_value_match:'价格与价值匹配',target_audience:'目标人群',price_analysis:'价格分析',selling_points:'核心卖点',conversion_barriers:'转化障碍',actions:'建议行动',image_directions:'主图创意方向',video_scripts:'短视频脚本',title:'标题',layout:'画面布局',copy:'文案',selling_point:'核心卖点',hook:'开场钩子',shots:'镜头设计',voiceover:'口播文案',cta:'行动引导',audience:'目标人群',channel:'投放渠道',budget:'预算',period:'周期',creative_angle:'素材方向',target_ctr:'目标 CTR',stop_roas:'ROAS 止损线',rationale:'建议依据',executive_summary:'复盘摘要',goal_vs_actual:'目标与实际',observations:'观测变化',possible_causes:'可能原因',next_actions:'下一轮行动',evidence_limitations:'证据边界'}
function ResultValue({value}:{value:unknown}) {
  if(Array.isArray(value)) return <div className="result-list">{value.map((item,index)=><div key={index} className="result-list-item"><ResultValue value={item}/></div>)}</div>
  if(value&&typeof value==='object') return <div className="result-object">{Object.entries(value).map(([key,item])=><section key={key}><h4>{resultLabels[key]||key}</h4><ResultValue value={item}/></section>)}</div>
  return <p>{value==null?'—':String(value)}</p>
}
function ResultModal({result,onClose}:{result:TaskResult;onClose:()=>void}) {
  const isVideo=result.task.kind==='video'&&Boolean(result.result_url?.match(/\.(mp4|webm)(\?|$)/i))
  return <div className="result-overlay" role="presentation" onMouseDown={e=>{if(e.currentTarget===e.target)onClose()}}><article className="result-modal" role="dialog" aria-modal="true" aria-label="生成结果"><div className="result-head"><div><span>{result.task.provider_mode==='mock'?'Mock 演示结果':'真实模型结果'}</span><h2>{result.task.title}</h2><p>{result.product?.name||`商品 #${result.task.product_id}`} · 任务 #{result.task.id}</p></div><button className="icon-btn" onClick={onClose} title="关闭"><XCircle size={20}/></button></div><div className="result-content">{result.content?<ResultValue value={result.content.payload}/>:result.experiment?<ResultValue value={result.experiment.strategy}/>:result.result_url?<div className="media-result">{isVideo?<video src={result.result_url} controls/>:<img src={result.result_url} alt={result.task.title}/>}<a href={result.result_url} target="_blank" rel="noreferrer">在新窗口打开素材</a>{result.task.kind==='video'&&!isVideo&&<small>当前视频任务为 Mock，占位素材用于验证结果链路。</small>}</div>:<Empty text="该任务没有可展示的结果"/>}</div></article></div>
}

function ApprovalsPage({user,products,items,onGenerate,onCreate,onSubmit,onDecision}:{user:User;products:Product[];items:Experiment[];onGenerate:(productId:number)=>Promise<void>;onCreate:(body:ExperimentDraft)=>Promise<void>;onSubmit:(id:number)=>Promise<void>;onDecision:(id:number,d:'approved'|'rejected')=>Promise<void>}) {
  const [form,setForm]=useState<ExperimentDraft>({product_id:products[0]?.id||0,title:'新品冷启动小预算测款',audience:'22–38 岁数码兴趣及品质生活人群',channel:'信息流',budget:900,period:'7 天',creative_angle:'外观质感、核心性能与真实使用场景三组素材对比',target_ctr:3.2,stop_roas:1.5})
  const [busy,setBusy]=useState(false)
  useEffect(()=>{if(!form.product_id&&products[0])setForm(current=>({...current,product_id:products[0].id}))},[products,form.product_id])
  async function create(e:FormEvent) {e.preventDefault();setBusy(true);try{await onCreate(form)}finally{setBusy(false)}}
  const value=(strategy:Record<string,unknown>,key:string,fallback='—')=>String(strategy[key]??fallback)
  return <div className="approval-layout">
    <form className="panel campaign-form" onSubmit={create}><div className="panel-head"><div><span>投放发起</span><h3>新建投放方案</h3></div><small>AI 建议/人工草稿 → 提交审批 → 主管确认</small></div><div className="campaign-fields"><label>投放商品<select value={form.product_id} onChange={e=>setForm({...form,product_id:Number(e.target.value)})}>{products.map(product=><option value={product.id} key={product.id}>{product.name}</option>)}</select></label><label>方案名称<input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} required/></label><label className="wide-field">目标人群<input value={form.audience} onChange={e=>setForm({...form,audience:e.target.value})} required/></label><label>投放渠道<select value={form.channel} onChange={e=>setForm({...form,channel:e.target.value})}><option>信息流</option><option>搜索广告</option><option>短视频</option><option>直播间</option></select></label><label>测试周期<input value={form.period} onChange={e=>setForm({...form,period:e.target.value})} required/></label><label>预算（元）<input type="number" min="1" value={form.budget} onChange={e=>setForm({...form,budget:Number(e.target.value)})} required/></label><label>目标 CTR（%）<input type="number" min="0.1" step="0.1" value={form.target_ctr} onChange={e=>setForm({...form,target_ctr:Number(e.target.value)})} required/></label><label>ROAS 止损线<input type="number" min="0" step="0.1" value={form.stop_roas} onChange={e=>setForm({...form,stop_roas:Number(e.target.value)})} required/></label><label className="wide-field">素材方向<input value={form.creative_angle} onChange={e=>setForm({...form,creative_angle:e.target.value})} required/></label></div><div className="approve-actions"><button type="button" className="outline" disabled={busy||!products.length} onClick={()=>onGenerate(form.product_id)}><Sparkles size={17}/>AI 生成投放建议</button><button className="primary" disabled={busy||!products.length}><ClipboardCheck size={17}/>{busy?'正在创建…':'保存人工草稿'}</button></div></form>
    <div className="approval-grid">{items.map(item=>{const targets=(item.strategy.targets&&typeof item.strategy.targets==='object'?item.strategy.targets:{}) as Record<string,unknown>;const product=products.find(current=>current.id===item.product_id);return <article className="approval-card" key={item.id}><div className="approval-top"><span className={`status ${item.status}`}>{statusText[item.status]||item.status}</span><small>方案 #{item.id}</small></div><h3>{item.title}</h3><p><b>{product?.name||`商品 #${item.product_id}`}</b> · {value(item.strategy,'channel')} · {value(item.strategy,'period')}</p><div className="campaign-detail"><span>目标人群</span><p>{value(item.strategy,'audience')}</p><span>素材方向</span><p>{value(item.strategy,'creative_angle',value(item.strategy,'ab_test'))}</p></div><div className="strategy"><div><span>测试预算</span><b>¥{Number(item.strategy.budget||300).toLocaleString()}</b></div><div><span>目标 CTR</span><b>≥ {String(targets.ctr??3.2)}%</b></div><div><span>止损条件</span><b>ROAS &lt; {String(targets.stop_roas??1.5)}</b></div></div>{item.decision_note&&<div className="decision-note">审批意见：{item.decision_note}</div>}{item.status==='draft'?<div className="approve-actions"><button className="primary" onClick={()=>onSubmit(item.id)}><ClipboardCheck size={17}/>提交主管审批</button></div>:item.status==='submitted'&&user.role==='manager'?<div className="approve-actions"><button className="outline danger" onClick={()=>onDecision(item.id,'rejected')}><XCircle size={17}/>驳回</button><button className="primary" onClick={()=>onDecision(item.id,'approved')}><CheckCircle2 size={17}/>确认通过</button></div>:item.status==='submitted'?<div className="role-tip"><ShieldCheck/>已提交，等待运营主管审批</div>:<div className={`role-tip ${item.status}`}><ShieldCheck/>{item.status==='approved'?'主管已批准该投放方案':'主管已驳回，请新建修改后的方案'}</div>}</article>})}{!items.length&&<div className="panel"><Empty text="暂无投放方案，请先创建草稿"/></div>}</div>
  </div>
}

function ReviewPage({products,selected,onSelect,detail,onGenerate}:{products:Product[];selected:number|null;onSelect:(id:number)=>void;detail:ProductDetail|null;onGenerate:()=>Promise<void>}){const m=detail?.metrics;const report=detail?.contents.filter(item=>item.type==='review').at(-1);return <><div className="filter-bar"><label>复盘商品<select value={selected||''} onChange={e=>onSelect(Number(e.target.value))}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label><button className="primary" disabled={!m} onClick={onGenerate}><Sparkles size={16}/>AI 生成经营复盘</button><span>指标口径：GMV 不扣退款 · ROAS = GMV / 广告花费</span></div>{m?<><section className="stat-grid review-stats"><Stat label="曝光量" value={m.impressions.toLocaleString()} hint={m.period} icon={Activity}/><Stat label="CTR" value={`${m.ctr??'—'}%`} hint="点击量 / 曝光量" icon={BarChart3}/><Stat label="转化率" value={`${m.conversion_rate??'—'}%`} hint="支付订单 / 点击量" icon={CheckCircle2}/><Stat label="ROAS" value={String(m.roas??'—')} hint={`GMV ${money(m.gmv)}`} icon={Sparkles}/></section>{report?<div className="panel review-block"><h3>AI 经营复盘 · 版本 {report.revision}</h3><ResultValue value={report.payload}/></div>:<div className="panel"><Empty text="经营数据已具备，请点击 AI 生成经营复盘"/></div>}</>:<div className="panel"><Empty text="该商品暂无经营指标，请先回填演示数据"/></div>}</>}

function ImportPage({onImported}:{onImported:()=>Promise<void>}) {
  const [file,setFile]=useState<File|null>(null)
  const [preview,setPreview]=useState<ImportPreview|null>(null)
  const [imported,setImported]=useState<ImportCommit|null>(null)
  const [error,setError]=useState('')
  const [stage,setStage]=useState<'idle'|'previewing'|'ready'|'importing'|'done'>('idle')
  async function upload(nextFile:File) {
    setFile(nextFile); setPreview(null); setImported(null); setError(''); setStage('previewing')
    try {
      const fd=new FormData(); fd.append('file',nextFile)
      const result=await api<ImportPreview>('/api/imports/preview',{method:'POST',body:fd})
      setPreview(result); setStage(result.can_import?'ready':'idle')
    } catch(e) { setError(e instanceof Error?e.message:'上传失败'); setStage('idle') }
  }
  async function commit() {
    if(!file||!preview?.can_import)return
    setError(''); setStage('importing')
    try {
      const fd=new FormData(); fd.append('file',file)
      const result=await api<ImportCommit>('/api/imports/commit',{method:'POST',body:fd})
      setImported(result); setStage('done'); await onImported()
    } catch(e) { setError(e instanceof Error?e.message:'导入失败'); setStage('ready') }
  }
  return <div className="panel import-panel"><div className="upload-zone"><Upload size={36}/><h3>{stage==='previewing'?'正在解析…':stage==='importing'?'正在写入数据库…':'上传经营数据'}</h3><p>支持 CSV、XLSX，演示版单文件不超过 5 MB。先校验预览，再由你确认写入数据库。</p><label className="primary">重新选择文件<input type="file" accept=".csv,.xlsx" hidden disabled={stage==='previewing'||stage==='importing'} onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/></label></div>
    {error&&<div className="error-box import-message">{error}</div>}
    {preview&&<div className="import-result"><h3>{preview.filename}</h3><div className={`import-state ${preview.can_import?'pending':'invalid'}`}><b>{preview.message}</b><span>{preview.can_import?'当前只是预览，点击下方按钮后才会真正入库。':'文件没有写入数据库。'}</span></div><p>文件共 {preview.row_count_total} 行，当前预览 {preview.row_count_previewed} 行 · 字段：{preview.columns.join('、')}</p>{preview.validation_errors.length>0&&<ul className="validation-errors">{preview.validation_errors.map((item,index)=><li key={index}>{item}</li>)}</ul>}{preview.rows.length>0&&<pre>{JSON.stringify(preview.rows.slice(0,5),null,2)}</pre>}{preview.can_import&&stage!=='done'&&<button className="primary import-confirm" disabled={stage==='importing'} onClick={commit}><Database size={17}/>{stage==='importing'?'正在导入…':'确认导入数据库'}</button>}</div>}
    {imported&&<div className="import-success"><CheckCircle2 size={24}/><div><h3>导入成功，数据已写入数据库</h3><p>导入 {imported.rows_imported} 行 · 商品新增 {imported.products_created} / 更新 {imported.products_updated} · 经营指标新增 {imported.metrics_created} / 更新 {imported.metrics_updated}</p><small>现在可以在“商品工作台”和“经营复盘”中查看导入结果。重复导入同一文件会更新已有记录，不会重复新增。</small></div></div>}
  </div>
}

function SettingsPage({manager}:{manager:boolean}){const [data,setData]=useState<any>(null);const [error,setError]=useState('');useEffect(()=>{if(manager)api('/api/settings').then(setData).catch(e=>setError(e.message))},[manager]);if(!manager)return <div className="panel"><Empty text="仅运营主管可以查看模型与运行配置"/></div>;return <div className="settings-grid"><div className="panel settings-summary"><span className="settings-icon"><Database/></span><div><small>运行模式</small><h2>{data?.ai_mode==='live'?'真实模型调用':'Mock 演示模式'}</h2><p>{data?.base_url||'加载中…'}</p></div><span className={`status ${data?.api_key_configured?'succeeded':'queued'}`}>{data?.api_key_configured?'Key 已配置':'等待配置 Key'}</span></div><div className="panel"><div className="panel-head"><h3>模型路由</h3><span>Worker 并发 {data?.worker_concurrency??1}</span></div>{error&&<div className="error-box">{error}</div>}<div className="model-list">{data&&Object.entries(data.models).map(([k,v])=><div key={k}><span>{k.toUpperCase()}</span><b>{String(v)}</b></div>)}</div><div className="security-note"><ShieldCheck/><span>模型密钥仅通过服务器 `.env` 注入，页面不会返回密钥原文。</span></div></div></div>}

function Empty({text}:{text:string}){return <div className="empty"><Package size={34}/><p>{text}</p></div>}

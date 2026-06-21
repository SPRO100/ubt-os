import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis } from "recharts";

const C = {
  bg:"#07090f", card:"#0d1628", border:"#162035",
  accent:"#00e5a0", blue:"#3b82f6", yellow:"#f5a623",
  red:"#ff4757", purple:"#a78bfa", text:"#dde6f5", muted:"#4a6080"
};

// ── Mock Data ──────────────────────────────────────────────
const TOP_HOOKS = [
  { rank:1, text:"Мне 64 года и я хожу без боли", type:"transformation", completion:74, ctr:3.2, cr:4.1, score:88 },
  { rank:2, text:"Хирург раскрыл правду о суставах", type:"doctor",         completion:71, ctr:2.9, cr:3.8, score:84 },
  { rank:3, text:"Эти 3 продукта УНИЧТОЖАЮТ суставы", type:"antagonist",    completion:68, ctr:2.7, cr:3.5, score:79 },
  { rank:4, text:"97% людей делают это неправильно", type:"fact",           completion:65, ctr:2.4, cr:2.9, score:73 },
  { rank:5, text:"30 дней с этим — вот что случилось", type:"before_after", completion:70, ctr:2.6, cr:3.1, score:76 },
];

const TOP_CTAS = [
  { rank:1, text:"Ссылка в bio", position:"end",    ctr:3.8, cr:4.2, score:91 },
  { rank:2, text:"Промокод в профиле", position:"end",   ctr:3.5, cr:3.9, score:87 },
  { rank:3, text:"Узнала откуда в закрепе", position:"mid", ctr:2.9, cr:3.4, score:78 },
  { rank:4, text:"В описании ниже ↓", position:"end",    ctr:2.7, cr:3.1, score:74 },
];

const PATTERNS = [
  { name:"transformation+ugc+short", hook:"transformation", format:"story", style:"UGC", duration:"30-45s", completion:73, ctr:3.1, cr:4.0, samples:24, confidence:0.88 },
  { name:"doctor+cinematic+mid",     hook:"doctor",         format:"reveal",style:"Cinematic",duration:"45-60s",completion:69,ctr:2.8,cr:3.6,samples:18,confidence:0.76},
  { name:"antagonist+ugc+short",     hook:"antagonist",     format:"warning",style:"UGC",duration:"30-45s",completion:66,ctr:2.6,cr:3.2,samples:15,confidence:0.71},
];

const SCORE_DIST = [
  { range:"0-30",  count:12, label:"Poor" },
  { range:"30-50", count:28, label:"Avg" },
  { range:"50-70", count:45, label:"Good" },
  { range:"70-85", count:31, label:"Top" },
  { range:"85-100",count:14, label:"Elite" },
];

// ── Atoms ──────────────────────────────────────────────────
const Card = ({children, style={}}) => (
  <div style={{background:C.card, border:`1px solid ${C.border}`, borderRadius:10, padding:16, ...style}}>
    {children}
  </div>
);

const SectionHeader = ({children}) => (
  <div style={{color:C.muted, fontSize:11, fontWeight:700, letterSpacing:"0.1em", marginBottom:14}}>
    {children}
  </div>
);

const ScoreBadge = ({score}) => {
  const color = score >= 80 ? C.accent : score >= 60 ? C.yellow : score >= 40 ? C.blue : C.red;
  return (
    <span style={{
      background:color+"22", color, border:`1px solid ${color}44`,
      borderRadius:6, padding:"3px 10px", fontSize:12, fontWeight:700, minWidth:42, display:"inline-block", textAlign:"center"
    }}>{score}</span>
  );
};

const ScoreBar = ({value, max=100, color}) => (
  <div style={{background:"#1a2640", borderRadius:3, height:5, flex:1}}>
    <div style={{width:`${(value/max)*100}%`, height:"100%", background:color, borderRadius:3, transition:"width 0.6s ease"}}/>
  </div>
);

const TypeTag = ({type}) => {
  const colors = {
    transformation:C.accent, doctor:C.blue, antagonist:C.red,
    fact:C.yellow, before_after:C.purple, story:"#f97316"
  };
  const color = colors[type] || C.muted;
  return (
    <span style={{background:color+"1a", color, border:`1px solid ${color}33`, borderRadius:4, padding:"1px 7px", fontSize:10, fontWeight:700}}>
      {type}
    </span>
  );
};

// ── Top Hooks Table ────────────────────────────────────────
function TopHooksWidget() {
  const [view, setView] = useState("nutra");
  return (
    <Card>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14}}>
        <SectionHeader style={{margin:0}}>🎣 ТОП ХУКОВ</SectionHeader>
        <div style={{display:"flex", gap:6}}>
          {["nutra","betting"].map(v => (
            <button key={v} onClick={()=>setView(v)} style={{
              padding:"3px 10px", borderRadius:5, fontSize:10, fontWeight:700, cursor:"pointer",
              background: view===v ? C.accent+"22" : "transparent",
              border: `1px solid ${view===v ? C.accent : C.border}`,
              color: view===v ? C.accent : C.muted
            }}>{v.toUpperCase()}</button>
          ))}
        </div>
      </div>

      {TOP_HOOKS.map((h,i) => (
        <div key={i} style={{
          padding:"10px 0", borderBottom: i<TOP_HOOKS.length-1 ? `1px solid ${C.border}` : "none",
          display:"flex", alignItems:"center", gap:12
        }}>
          <span style={{color:C.muted, fontSize:11, minWidth:16, textAlign:"center"}}>{h.rank}</span>
          <div style={{flex:1}}>
            <div style={{color:C.text, fontSize:12, fontWeight:600, marginBottom:4}}>«{h.text}»</div>
            <div style={{display:"flex", alignItems:"center", gap:10}}>
              <TypeTag type={h.type}/>
              <div style={{display:"flex", alignItems:"center", gap:6, flex:1}}>
                <span style={{color:C.muted, fontSize:10}}>CR</span>
                <ScoreBar value={h.cr} max={5} color={C.accent}/>
                <span style={{color:C.accent, fontSize:10, minWidth:28}}>{h.cr}%</span>
              </div>
            </div>
          </div>
          <div style={{display:"flex", flexDirection:"column", alignItems:"flex-end", gap:4}}>
            <ScoreBadge score={h.score}/>
            <span style={{color:C.muted, fontSize:10}}>{h.completion}% view</span>
          </div>
        </div>
      ))}
    </Card>
  );
}

// ── Top CTAs ───────────────────────────────────────────────
function TopCTAsWidget() {
  return (
    <Card>
      <SectionHeader>👆 ТОП CTA</SectionHeader>
      {TOP_CTAS.map((c,i) => (
        <div key={i} style={{
          padding:"9px 0", borderBottom: i<TOP_CTAS.length-1 ? `1px solid ${C.border}` : "none",
          display:"flex", alignItems:"center", gap:10
        }}>
          <span style={{color:C.muted, fontSize:11, minWidth:16}}>{c.rank}</span>
          <div style={{flex:1}}>
            <div style={{color:C.text, fontSize:12, fontWeight:600}}>«{c.text}»</div>
            <div style={{display:"flex", gap:8, marginTop:3}}>
              <span style={{color:C.muted, fontSize:10}}>{c.position}</span>
              <span style={{color:C.blue, fontSize:10}}>CTR {c.ctr}%</span>
              <span style={{color:C.accent, fontSize:10}}>CR {c.cr}%</span>
            </div>
          </div>
          <ScoreBadge score={c.score}/>
        </div>
      ))}
    </Card>
  );
}

// ── Score Distribution ─────────────────────────────────────
function ScoreDistWidget() {
  const CustomTT = ({active, payload}) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{background:C.card, border:`1px solid ${C.border}`, borderRadius:6, padding:"8px 12px"}}>
        <div style={{color:C.text, fontSize:12}}>{payload[0].payload.label}</div>
        <div style={{color:C.accent, fontSize:13, fontWeight:700}}>{payload[0].value} видео</div>
      </div>
    );
  };

  return (
    <Card>
      <SectionHeader>📊 РАСПРЕДЕЛЕНИЕ СКОРОВ</SectionHeader>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={SCORE_DIST} margin={{top:0,bottom:0}}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
          <XAxis dataKey="range" tick={{fill:C.muted, fontSize:10}} axisLine={false} tickLine={false}/>
          <YAxis tick={{fill:C.muted, fontSize:10}} axisLine={false} tickLine={false}/>
          <Tooltip content={<CustomTT/>}/>
          <Bar dataKey="count" fill={C.accent} radius={[4,4,0,0]} fillOpacity={0.8}/>
        </BarChart>
      </ResponsiveContainer>
      <div style={{display:"flex", gap:16, marginTop:10, justifyContent:"center"}}>
        {[["Elite 85+", C.accent, 14], ["Top 70+", C.yellow, 31], ["Good 50+", C.blue, 45]].map(([l,c,n]) => (
          <div key={l} style={{display:"flex", alignItems:"center", gap:5}}>
            <div style={{width:8, height:8, borderRadius:2, background:c}}/>
            <span style={{color:C.muted, fontSize:10}}>{l}: {n}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Winning Patterns ───────────────────────────────────────
function WinningPatternsWidget() {
  const [selected, setSelected] = useState(0);
  const p = PATTERNS[selected];

  const radarData = [
    {metric:"Completion", value: p.completion},
    {metric:"CTR",        value: p.ctr * 20},
    {metric:"CR",         value: p.cr * 20},
    {metric:"Confidence", value: p.confidence * 100},
    {metric:"Samples",    value: Math.min(p.samples * 4, 100)},
  ];

  return (
    <Card>
      <SectionHeader>🏆 ВЫИГРЫШНЫЕ ПАТТЕРНЫ</SectionHeader>
      <div style={{display:"flex", gap:8, marginBottom:14, flexWrap:"wrap"}}>
        {PATTERNS.map((p,i) => (
          <button key={i} onClick={()=>setSelected(i)} style={{
            padding:"4px 10px", borderRadius:6, cursor:"pointer", fontSize:10, fontWeight:700,
            background: selected===i ? C.purple+"22" : "transparent",
            border: `1px solid ${selected===i ? C.purple : C.border}`,
            color: selected===i ? C.purple : C.muted
          }}>{p.hook}</button>
        ))}
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
        <div>
          {[
            ["Хук",     p.hook],
            ["Формат",  p.format],
            ["Стиль",   p.style],
            ["Длина",   p.duration],
            ["CTA",     "в конце"],
          ].map(([k,v]) => (
            <div key={k} style={{display:"flex", justifyContent:"space-between", padding:"5px 0", borderBottom:`1px solid ${C.border}`}}>
              <span style={{color:C.muted, fontSize:11}}>{k}</span>
              <span style={{color:C.text, fontSize:11, fontWeight:600}}>{v}</span>
            </div>
          ))}
          <div style={{marginTop:10, padding:"8px 10px", background:C.accent+"11", borderRadius:6, border:`1px solid ${C.accent}33`}}>
            <div style={{color:C.muted, fontSize:10}}>Выборка / Уверенность</div>
            <div style={{color:C.accent, fontSize:13, fontWeight:700}}>{p.samples} видео / {Math.round(p.confidence*100)}%</div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <RadarChart data={radarData}>
            <PolarGrid stroke={C.border}/>
            <PolarAngleAxis dataKey="metric" tick={{fill:C.muted, fontSize:9}}/>
            <Radar dataKey="value" fill={C.purple} fillOpacity={0.3} stroke={C.purple} strokeWidth={1.5}/>
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

// ── Main Dashboard ─────────────────────────────────────────
export default function CreativeVaultDashboard() {
  return (
    <div style={{
      background:C.bg, minHeight:"100vh", padding:20,
      fontFamily:"'IBM Plex Mono','Fira Code',monospace", color:C.text
    }}>
      <style>{`* { box-sizing:border-box; } button { font-family:inherit; }`}</style>

      <div style={{display:"flex", alignItems:"center", gap:12, marginBottom:20}}>
        <div style={{width:8, height:8, borderRadius:"50%", background:C.accent, boxShadow:`0 0 8px ${C.accent}`}}/>
        <span style={{color:C.accent, fontWeight:700, fontSize:14, letterSpacing:"0.1em"}}>CREATIVE VAULT</span>
        <span style={{color:C.muted, fontSize:11}}>/ 130 ассетов · 3 паттерна · обновлено 01:04</span>
      </div>

      {/* Stats row */}
      <div style={{display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:20}}>
        {[
          {label:"Всего ассетов",   val:"130",  col:C.text},
          {label:"Top Performers",  val:"45",   col:C.accent},
          {label:"Паттернов",       val:"3",    col:C.purple},
          {label:"Средний CR",      val:"3.2%", col:C.yellow},
        ].map((s,i) => (
          <Card key={i} style={{textAlign:"center"}}>
            <div style={{color:s.col, fontSize:24, fontWeight:700}}>{s.val}</div>
            <div style={{color:C.muted, fontSize:10, marginTop:4}}>{s.label}</div>
          </Card>
        ))}
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16}}>
        <TopHooksWidget/>
        <TopCTAsWidget/>
      </div>
      <div style={{display:"grid", gridTemplateColumns:"1fr 1.5fr", gap:16}}>
        <ScoreDistWidget/>
        <WinningPatternsWidget/>
      </div>
    </div>
  );
}

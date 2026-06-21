import { useState } from "react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, FunnelChart, Funnel, LabelList } from "recharts";

const C = {
  bg:"#07090f", card:"#0d1628", border:"#162035",
  accent:"#00e5a0", blue:"#3b82f6", yellow:"#f5a623",
  red:"#ff4757", purple:"#a78bfa", text:"#dde6f5", muted:"#4a6080"
};

const REVENUE_7D = [
  {d:"Пн", revenue:420, conversions:12, events:9800},
  {d:"Вт", revenue:285, conversions:8,  events:7200},
  {d:"Ср", revenue:610, conversions:17, events:12400},
  {d:"Чт", revenue:390, conversions:11, events:9100},
  {d:"Пт", revenue:720, conversions:20, events:15600},
  {d:"Сб", revenue:540, conversions:15, events:11200},
  {d:"Вс", revenue:810, conversions:23, events:17400},
];

const FUNNEL_DATA = [
  {name:"Просмотры", value:100000, fill:C.blue},
  {name:"Клики", value:2500, fill:C.accent},
  {name:"Лид", value:480, fill:C.yellow},
  {name:"Конверсия", value:106, fill:"#f97316"},
];

const PARTNER_DATA = [
  {partner:"Dr.Cash", conversions:67, epc:2.1, approval:88, revenue:141, hold:14, rank:1},
  {partner:"1win",    conversions:45, epc:3.2, approval:92, revenue:144, hold:7,  rank:2},
  {partner:"Mostbet", conversions:28, epc:2.8, approval:89, revenue:78,  hold:7,  rank:3},
];

const LEAKS = [
  {type:"weak_cta",       platform:"TikTok",   geo:"RU", actual:1.8, bench:2.5, upside:320, action:"Заменить CTA в видео с CTR < 2%"},
  {type:"weak_prelander", platform:"Instagram", geo:"PL", actual:2.1, bench:3.2, upside:210, action:"A/B тест прелендинга"},
  {type:"low_approval",   platform:"TikTok",   geo:"KZ", actual:71,  bench:85,  upside:140, action:"Сменить источник трафика"},
];

const SCALING = [
  {video:"@sport_pro #247", platform:"TikTok", geo:"RU", roi:520, revenue:180, rev_per_view:0.014},
  {video:"@goals_daily #89",platform:"YouTube",geo:"RU", roi:380, revenue:95,  rev_per_view:0.009},
  {video:"@stats_ua #33",   platform:"Instagram",geo:"UA",roi:310, revenue:72, rev_per_view:0.007},
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

const Tag = ({label, color}) => (
  <span style={{background:color+"1a", color, border:`1px solid ${color}33`, borderRadius:4, padding:"2px 8px", fontSize:10, fontWeight:700}}>
    {label}
  </span>
);

// ── Revenue Trend ──────────────────────────────────────────
function RevenueTrendWidget() {
  const total = REVENUE_7D.reduce((s,d) => s + d.revenue, 0);
  const convs = REVENUE_7D.reduce((s,d) => s + d.conversions, 0);

  const CustomTT = ({active, payload, label}) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{background:C.card, border:`1px solid ${C.border}`, borderRadius:6, padding:"8px 12px"}}>
        <div style={{color:C.muted, fontSize:11, marginBottom:4}}>{label}</div>
        <div style={{color:C.accent,  fontSize:13}}>💰 ${payload[0]?.value}</div>
        <div style={{color:C.yellow, fontSize:12}}>🎯 {payload[1]?.value} конв.</div>
      </div>
    );
  };

  return (
    <Card>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16}}>
        <div>
          <SectionHeader style={{margin:0, marginBottom:6}}>ДОХОД — 7 ДНЕЙ</SectionHeader>
          <div style={{color:C.accent, fontSize:28, fontWeight:700}}>${total.toLocaleString()}</div>
          <div style={{color:C.muted, fontSize:11, marginTop:2}}>{convs} конверсий · EPC $2.4</div>
        </div>
        <div style={{textAlign:"right"}}>
          <div style={{color:C.yellow, fontSize:20, fontWeight:700}}>{convs}</div>
          <div style={{color:C.muted, fontSize:10}}>конверсий</div>
          <div style={{color:C.green||C.accent, fontSize:11, marginTop:4}}>+18% к пр. нед.</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={REVENUE_7D}>
          <defs>
            <linearGradient id="gRev" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={C.accent} stopOpacity={0.25}/>
              <stop offset="95%" stopColor={C.accent} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
          <XAxis dataKey="d" tick={{fill:C.muted, fontSize:10}} axisLine={false} tickLine={false}/>
          <YAxis tick={{fill:C.muted, fontSize:10}} axisLine={false} tickLine={false} tickFormatter={v=>"$"+v}/>
          <Tooltip content={<CustomTT/>}/>
          <Area type="monotone" dataKey="revenue" stroke={C.accent} strokeWidth={2} fill="url(#gRev)"/>
          <Area type="monotone" dataKey="conversions" stroke={C.yellow} strokeWidth={1} fill="none" strokeDasharray="4 2"/>
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

// ── Funnel Leaks ───────────────────────────────────────────
function FunnelLeaksWidget() {
  const totalUpside = LEAKS.reduce((s,l) => s + l.upside, 0);
  return (
    <Card>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14}}>
        <SectionHeader style={{margin:0}}>⚠️ УТЕЧКИ ВОРОНКИ</SectionHeader>
        <span style={{color:C.yellow, fontSize:13, fontWeight:700}}>+${totalUpside} потенциал</span>
      </div>
      {LEAKS.map((leak, i) => (
        <div key={i} style={{
          padding:"10px 12px", marginBottom:8,
          background:C.yellow+"0d", border:`1px solid ${C.yellow}33`, borderRadius:7
        }}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6}}>
            <div style={{display:"flex", gap:8, alignItems:"center"}}>
              <Tag label={leak.platform} color={C.blue}/>
              <Tag label={leak.geo} color={C.muted}/>
              <span style={{color:C.text, fontSize:12, fontWeight:600}}>
                {leak.type === "weak_cta" ? "Слабый CTA" :
                 leak.type === "weak_prelander" ? "Слабый прелендинг" : "Низкий апрув"}
              </span>
            </div>
            <span style={{color:C.yellow, fontWeight:700, fontSize:14}}>+${leak.upside}</span>
          </div>
          <div style={{display:"flex", gap:20, marginBottom:6}}>
            <div>
              <span style={{color:C.muted, fontSize:10}}>Факт </span>
              <span style={{color:C.red, fontSize:12, fontWeight:700}}>{leak.actual}%</span>
            </div>
            <div>
              <span style={{color:C.muted, fontSize:10}}>Бенч </span>
              <span style={{color:C.accent, fontSize:12, fontWeight:700}}>{leak.bench}%</span>
            </div>
          </div>
          <div style={{color:C.muted, fontSize:11}}>→ {leak.action}</div>
        </div>
      ))}
    </Card>
  );
}

// ── Partner Comparison ─────────────────────────────────────
function PartnerComparisonWidget() {
  return (
    <Card>
      <SectionHeader>🤝 ПАРТНЁРКИ — СРАВНЕНИЕ</SectionHeader>
      {PARTNER_DATA.map((p, i) => (
        <div key={i} style={{
          padding:"10px 0", borderBottom: i < PARTNER_DATA.length-1 ? `1px solid ${C.border}` : "none"
        }}>
          <div style={{display:"flex", justifyContent:"space-between", marginBottom:6}}>
            <div style={{display:"flex", alignItems:"center", gap:8}}>
              <span style={{
                width:20, height:20, borderRadius:5, background:C.accent+"22",
                color:C.accent, fontSize:11, fontWeight:700,
                display:"flex", alignItems:"center", justifyContent:"center"
              }}>#{p.rank}</span>
              <span style={{color:C.text, fontSize:13, fontWeight:700}}>{p.partner}</span>
            </div>
            <span style={{color:C.accent, fontSize:14, fontWeight:700}}>${p.revenue}</span>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8}}>
            {[
              ["Конверсий",  p.conversions, C.text],
              ["EPC",        "$"+p.epc,     C.yellow],
              ["Апрув",      p.approval+"%",p.approval>88?C.accent:C.red],
              ["Hold",       p.hold+"д",    C.muted],
            ].map(([k,v,c]) => (
              <div key={k} style={{background:C.bg, borderRadius:5, padding:"4px 8px", textAlign:"center"}}>
                <div style={{color:c, fontSize:12, fontWeight:700}}>{v}</div>
                <div style={{color:C.muted, fontSize:9}}>{k}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </Card>
  );
}

// ── Scaling Candidates ─────────────────────────────────────
function ScalingWidget() {
  return (
    <Card style={{borderColor:C.accent+"44"}}>
      <SectionHeader>🚀 МАСШТАБИРОВАТЬ СЕЙЧАС</SectionHeader>
      {SCALING.map((s, i) => (
        <div key={i} style={{
          padding:"10px 12px", marginBottom:8,
          background:C.accent+"0d", border:`1px solid ${C.accent}33`, borderRadius:7,
          display:"flex", alignItems:"center", gap:12
        }}>
          <div style={{
            padding:"6px 10px", background:C.accent+"22",
            borderRadius:6, textAlign:"center", flexShrink:0
          }}>
            <div style={{color:C.accent, fontSize:16, fontWeight:700}}>{s.roi}%</div>
            <div style={{color:C.muted, fontSize:9}}>ROI</div>
          </div>
          <div style={{flex:1}}>
            <div style={{color:C.text, fontSize:12, fontWeight:600}}>{s.video}</div>
            <div style={{display:"flex", gap:8, marginTop:3}}>
              <Tag label={s.platform} color={C.blue}/>
              <Tag label={s.geo} color={C.muted}/>
              <span style={{color:C.accent, fontSize:10}}>${s.rev_per_view}/view</span>
            </div>
          </div>
          <div style={{textAlign:"right"}}>
            <div style={{color:C.yellow, fontSize:14, fontWeight:700}}>${s.revenue}</div>
            <div style={{color:C.muted, fontSize:10}}>доход</div>
          </div>
        </div>
      ))}
      <div style={{marginTop:8, padding:"8px 12px", background:"#0a1628", borderRadius:6}}>
        <div style={{color:C.muted, fontSize:11}}>
          💡 Увеличь публикации на эти аккаунты × 2 и переключи бюджет времени с ROI &lt; 100%
        </div>
      </div>
    </Card>
  );
}

// ── Main ───────────────────────────────────────────────────
export default function RevenueAnalystDashboard() {
  return (
    <div style={{
      background:C.bg, minHeight:"100vh", padding:20,
      fontFamily:"'IBM Plex Mono','Fira Code',monospace", color:C.text
    }}>
      <style>{`* { box-sizing:border-box; }`}</style>

      <div style={{display:"flex", alignItems:"center", gap:12, marginBottom:20}}>
        <div style={{width:8, height:8, borderRadius:"50%", background:C.yellow, boxShadow:`0 0 8px ${C.yellow}`}}/>
        <span style={{color:C.yellow, fontWeight:700, fontSize:14, letterSpacing:"0.1em"}}>REVENUE ANALYST</span>
        <span style={{color:C.muted, fontSize:11}}>/ A16 · обновлено 23:31</span>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16}}>
        <RevenueTrendWidget/>
        <FunnelLeaksWidget/>
      </div>
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16}}>
        <PartnerComparisonWidget/>
        <ScalingWidget/>
      </div>
    </div>
  );
}

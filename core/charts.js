/* ================= 图表注册表 =================
   每个实现签名: fn(ch, spec, ds, DATA, Core)
   spec 由数据源适配器在 BOARD.charts() 里声明，函数字段均为闭包。 */
(function(){
const { PAL, AXT, SPLIT, tip, fmt } = Core;

/* 柱状 + 可选均线 + 缩放。spec: {barName, yName, values(ds)->[], tip(ds,i)->html, ma=true, maColor} */
Core.registry.trend = function(ch, spec, ds){
  const vals = spec.values(ds);
  const series = [{
    name:spec.barName, type:'bar', data:vals, barMaxWidth:spec.barMaxWidth||22,
    itemStyle:{borderRadius:[4,4,0,0], color:new echarts.graphic.LinearGradient(0,0,0,1,
      [{offset:0, color:spec.barColor||'#67e8f9'},{offset:1, color:spec.barColor2||'rgba(59,130,246,.25)'}])}}];
  const legendData = [spec.barName];
  if (spec.ma !== false){
    legendData.push(spec.maName || '7日均线');
    series.push({name:spec.maName || '7日均线', type:'line', smooth:.5, symbol:'none',
      data:Core.ma(vals).map(v => spec.maScale ? spec.maScale(v) : v),
      lineStyle:{color:spec.maColor||'#f472b6', width:2.5, shadowColor:'rgba(244,114,182,.5)', shadowBlur:10}});
  }
  ch.setOption({
    animation:false,
    tooltip: tip({trigger:'axis', axisPointer:{type:'shadow'},
      formatter: ps => spec.tip(ds, ps[0].dataIndex, ps[1] ? ps[1].value : null)}),
    legend:{data:legendData, top:0, right:6, textStyle:{color:AXT}},
    grid:{left:64, right:24, top:38, bottom:70},
    xAxis:{type:'category', data:ds.map(d=>fmt.md(d.d)),
      axisLine:{lineStyle:{color:'rgba(148,163,184,.28)'}},
      axisLabel:{color:AXT, rotate:ds.length>60?45:0, fontSize:11}},
    yAxis:{type:'value', name:spec.yName||'', nameTextStyle:{color:AXT},
      axisLabel: spec.yFmt ? {color:AXT, formatter:spec.yFmt} : {color:AXT},
      splitLine:{lineStyle:{color:SPLIT}}},
    dataZoom:[{type:'inside'},{type:'slider', height:20, bottom:14, borderColor:'rgba(148,163,184,.25)',
      fillerColor:'rgba(34,211,238,.14)', handleStyle:{color:'#22d3ee'}, textStyle:{color:AXT}}],
    series,
  }, true);
};

/* 堆叠面积。spec: {names(ds)->[], value(ds,name)->number, yName, valueFmt} */
Core.registry.stack = function(ch, spec, ds){
  const names = spec.names(ds);
  ch.setOption({
    animation:false,
    tooltip: tip({trigger:'axis', axisPointer:{type:'cross', crossStyle:{color:'rgba(148,163,184,.4)'}},
      valueFormatter: spec.valueFmt}),
    legend:{type:'scroll', top:0, textStyle:{color:AXT}, pageTextStyle:{color:AXT}},
    grid:{left:56, right:20, top:40, bottom:46},
    xAxis:{type:'category', boundaryGap:false, data:ds.map(d=>fmt.md(d.d)),
      axisLine:{lineStyle:{color:'rgba(148,163,184,.28)'}},
      axisLabel:{color:AXT, rotate:ds.length>60?45:0, fontSize:11}},
    yAxis:{type:'value', axisLabel:{color:AXT, formatter:spec.yFmt||'{value}'}, splitLine:{lineStyle:{color:SPLIT}}},
    series:names.map((n,i)=>({
      name:n, type:'line', stack:spec.stackName||'s', smooth:.4, symbol:'none', lineStyle:{width:0},
      areaStyle:{opacity:.55}, emphasis:{focus:'series'}, itemStyle:{color:PAL[i%PAL.length]},
      data:ds.map(d=>+(spec.value(d, n).toFixed ? spec.value(d, n).toFixed(2) : spec.value(d, n)))}))
  }, true);
};

/* 横向排行条。spec: {items(ds)->[[name,val]]升序, fmt(v)->label, c1, c2, labelColor} */
Core.registry.hbar = function(ch, spec, ds){
  const items = spec.items(ds);
  ch.setOption({
    animation:false,
    tooltip: tip({trigger:'axis', axisPointer:{type:'shadow'}, valueFormatter:v=>spec.fmt(v)}),
    grid:{left:8, right:spec.labelWidth||74, top:spec.top||14, bottom:14, containLabel:true},
    xAxis:{type:'value', show:false},
    yAxis:{type:'category', data:items.map(e=>e[0]), axisLine:{show:false}, axisTick:{show:false},
      axisLabel:{color:AXT, fontSize:12}},
    series:[{type:'bar', barMaxWidth:16, data:items.map(e=>+(spec.scale?spec.scale(e[1]):e[1]).toFixed(2)),
      label:{show:true, position:'right', color:spec.labelColor||'#67e8f9', fontSize:12,
        formatter:p=>spec.fmt(spec.scale&&spec.inverse?spec.scale(p.value):p.value)},
      itemStyle:{borderRadius:[0,5,5,0], color:new echarts.graphic.LinearGradient(0,0,1,0,
        [{offset:0, color:spec.c2||'rgba(167,139,250,.35)'},{offset:1, color:spec.c1||'#e879f9'}])},
      emphasis:{itemStyle:{shadowBlur:14, shadowColor:'rgba(232,121,249,.55)'}}}]
  }, true);
};

/* 环形占比。spec: {items(ds)->[[name,val]]降序, topN=6, center:{big,sub}, itemTip(name,val,pct)} */
Core.registry.donut = function(ch, spec, ds){
  const items = spec.items(ds);
  const total = items.reduce((a,e)=>a+e[1], 0);
  const top = items.slice(0, spec.topN===undefined?6:spec.topN);
  const rest = items.slice(top.length);
  const data = top.map((e,i)=>({name:e[0], value:+e[1].toFixed(2), itemStyle:{color:PAL[i%PAL.length]}}));
  if (rest.length) data.push({name:'其他', value:+rest.reduce((a,e)=>a+e[1],0).toFixed(2),
    itemStyle:{color:'rgba(148,163,184,.45)'}});
  ch.setOption({
    animation:false,
    tooltip: tip({trigger:'item', formatter:p => spec.itemTip ?
      spec.itemTip(p.name, p.value, p.percent) :
      `<b style="color:${p.color}">${p.name}</b><br><b>${fmt.money(p.value)}</b>（${p.percent}%）`}),
    legend:{type:'scroll', orient:'vertical', right:8, top:'middle', textStyle:{color:AXT}, pageTextStyle:{color:AXT}},
    title:{text:spec.center.big, subtext:spec.center.sub, left:'33.5%', top:'41%', textAlign:'center',
      textStyle:{color:'#e2e8f0', fontSize:24, fontWeight:800}, subtextStyle:{color:AXT, fontSize:12}},
    series:[{type:'pie', radius:['46%','68%'], center:['34%','52%'],
      itemStyle:{borderColor:'#0a0f1e', borderWidth:3, borderRadius:6},
      label:{color:AXT, formatter:'{b}\n{d}%', fontSize:11, lineHeight:15},
      labelLine:{lineStyle:{color:'rgba(148,163,184,.35)'}},
      emphasis:{scaleSize:6, itemStyle:{shadowBlur:18, shadowColor:'rgba(34,211,238,.4)'}},
      data}]
  }, true);
};

/* 横向堆叠条。spec: {categories(ds)->[名字]升序, series:[{name,color,values(ds,cat)->number}], fmt} */
Core.registry.hstack = function(ch, spec, ds){
  const cats = spec.categories(ds);
  ch.setOption({
    animation:false,
    tooltip: tip({trigger:'axis', axisPointer:{type:'shadow'}, valueFormatter:v=>spec.fmt(v)}),
    legend:{top:0, textStyle:{color:AXT}},
    grid:{left:96, right:30, top:38, bottom:30},
    xAxis:{type:'value', axisLabel:{color:AXT, formatter:spec.axisFmt||(v=>v)}, splitLine:{lineStyle:{color:SPLIT}}},
    yAxis:{type:'category', data:cats, axisLine:{lineStyle:{color:'rgba(148,163,184,.28)'}},
      axisLabel:{color:AXT, fontSize:11}},
    series:spec.series.map(s=>({name:s.name, type:'bar', stack:'hs', barMaxWidth:16,
      itemStyle:{color:s.color}, data:spec.values(ds, s)}))
  }, true);
};

/* 热力图。spec: {xLabels, yLabels, data([[x,y,v]]), max, tip(x,y,v)} */
Core.registry.heatmap = function(ch, spec){
  ch.setOption({
    animation:false,
    tooltip: tip({formatter:p => spec.tip(p.data[0], p.data[1], p.data[2])}),
    grid:{left:56, right:26, top:16, bottom:64},
    xAxis:{type:'category', data:spec.xLabels, splitArea:{show:true, areaStyle:{color:['rgba(148,163,184,.03)','transparent']}},
      axisLine:{show:false}, axisTick:{show:false}, axisLabel:{color:AXT}},
    yAxis:{type:'category', data:spec.yLabels, splitArea:{show:true, areaStyle:{color:['rgba(148,163,184,.03)','transparent']}},
      axisLine:{show:false}, axisTick:{show:false}, axisLabel:{color:AXT}},
    visualMap:{type:'continuous', min:0, max:spec.max, calculable:true, orient:'horizontal',
      left:'center', bottom:6, itemHeight:110, textStyle:{color:AXT},
      inRange:{color:['#0b1226','#155e75','#22d3ee','#e879f9']}},
    series:[{type:'heatmap', data:spec.data,
      itemStyle:{borderColor:'#080d1c', borderWidth:3, borderRadius:4},
      emphasis:{itemStyle:{shadowBlur:12, shadowColor:'rgba(34,211,238,.6)'}}}]
  }, true);
};

/* 可排序表格。spec: {columns:[{k,label,fmt(v,row),cls}], rows(ds)->[row], footer(rows)->[...], initSort:{k,dir}} */
Core.registry.table = function(ch, spec, ds){
  const el = ch.getDom();
  let rows = spec.rows(ds), sortK = spec.initSort?.k || null, sortDir = spec.initSort?.dir || -1;
  const rawOf = spec.raw || ((row, k) => row[k]);
  function draw(){
    rows.sort((a,b) => { const x=rawOf(a,sortK), y=rawOf(b,sortK);
      return (x>y?1:x<y?-1:0)*sortDir; });
    const head = spec.columns.map(c =>
      `<th data-k="${c.k}">${c.label}<span class="arr">${c.k===sortK?(sortDir===1?'▲':'▼'):''}</span></th>`).join('');
    const body = rows.map(r => '<tr>' + spec.columns.map(c =>
      `<td${c.cls?` class="${c.cls}"`:''}>${c.fmt ? c.fmt(r[c.k], r) : r[c.k]}</td>`).join('') + '</tr>').join('');
    const foot = spec.footer ? '<tfoot><tr>' + spec.footer(rows).map(v=>`<td>${v}</td>`).join('') + '</tr></tfoot>' : '';
    el.innerHTML = `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody>${foot}</table></div>`;
    el.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.k;
      sortDir = (k === sortK) ? -sortDir : (k === spec.columns[0].k ? -1 : -1);
      sortK = k; draw();
    }));
  }
  draw();
};
})();

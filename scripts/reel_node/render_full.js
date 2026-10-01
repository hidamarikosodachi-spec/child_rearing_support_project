// リールv2 本制作（全8シーン・約31秒・930フレーム）色鉛筆絵本 @napi-rs/canvas + roughjs
// 指示書v2準拠：点目・ハッチング塗り・ボイリング・各シーンのモーション。顔ありOK(CEO 6/8)。
// ナレーション(TTS)はedge-tts商用懸念によりCEO保留→第1弾は画面テキスト。BGMは別途無料自作トラックを後付け。
// 使い方: node render_full.js   → frames_full/ に930枚出力
const fs = require('fs');
const path = require('path');
const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');
const rough = require('roughjs');

// 新マシンではフォントがユーザー領域にある。候補を順に探して最初に見つかったものを使う
// （見つからないと日本語が豆腐□になるので、起点で止める）
const FONT_CANDIDATES = [
  process.env.HIDAMARI_FONT,
  '/home/saki/.local/share/fonts/NotoSansCJK-Regular.ttc',
  '/home/saki/.local/share/fonts/NotoSansCJK-Bold.ttc',
  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
].filter(Boolean);
const fontPath = FONT_CANDIDATES.find(p => fs.existsSync(p));
if (!fontPath) throw new Error('日本語フォントが見つかりません: ' + FONT_CANDIDATES.join(', '));
GlobalFonts.registerFromPath(fontPath, 'HidamariJP');
console.log('font:', fontPath);
const FONT = 'HidamariJP';
const W = 1080, H = 1920;            // 出力（設計540x960を×2）
const FLOOR = 960 * 0.60;

const P = {
  paper:'#FBF4E4', hidamari:'#F6EBD6', hair:'#5A4636', hairLine:'#4A3A2C',
  parentWear:'#C97B5A', parentArm:'#B5663F', childWear:'#DBA84E', childArm:'#C98F2E',
  skin:'#E8C9A8', skinLine:'#C49A77', blush:'#F0A98E', mouth:'#B0613F',
  shoe:'#B05A38', text:'#5A4636', ground:'#C9B28A',
};
const skin  = {fill:P.skin, stroke:P.skinLine, fillStyle:'hachure', hachureGap:4.5, fillWeight:1.1, roughness:1.4, strokeWidth:2, hachureAngle:65};
const hair  = {fill:P.hair, stroke:P.hairLine, fillStyle:'hachure', hachureGap:3, fillWeight:1.4, roughness:1.4, strokeWidth:2, hachureAngle:35};
const pCloth= {fill:P.parentWear, stroke:'#A85A3A', fillStyle:'hachure', hachureGap:4, fillWeight:1.3, roughness:1.4, strokeWidth:2, hachureAngle:-40};
const cCloth= {fill:P.childWear, stroke:'#B8862E', fillStyle:'hachure', hachureGap:4, fillWeight:1.3, roughness:1.4, strokeWidth:2, hachureAngle:-40};
const blush = {fill:P.blush, fillStyle:'hachure', hachureGap:2.5, fillWeight:1, stroke:'none', roughness:1.2, hachureAngle:10};
const dot   = {fill:'#4A3A2C', fillStyle:'solid', stroke:'none', roughness:1.1};
const mouth = {stroke:P.mouth, strokeWidth:2.5, roughness:1.1};
const eyeline= {stroke:'#4A3A2C', strokeWidth:3, roughness:1.2};
const mouthFill={fill:'#C76A45', fillStyle:'hachure', hachureGap:2, fillWeight:1.4, stroke:P.mouth, strokeWidth:2, roughness:1.1};
const shoeOpt= {fill:P.shoe, fillStyle:'hachure', hachureGap:2.5, fillWeight:1.5, stroke:'#8F4326', strokeWidth:2, roughness:1.4};
const groundOpt={stroke:P.ground, strokeWidth:2.5, roughness:1.8};

const S = (o,s)=>({...o, seed:Math.max(1, s|0)});
const boilSeed = f => [11,57,103][Math.floor(f/6)%3];
const eIO = t => t<0.5 ? 2*t*t : 1-Math.pow(-2*t+2,2)/2;
const eOut = t => 1-Math.pow(1-t,3);
const clamp01 = t => Math.max(0, Math.min(1, t));

// ---- 顔 ----
function childHead(rc, x, cy, expr, s){
  rc.circle(x, cy-52, 14, S(hair, s+1));
  rc.circle(x-47, cy+4, 15, S(skin, s+2));
  rc.circle(x+47, cy+4, 15, S(skin, s+3));
  rc.circle(x, cy, 92, S(skin, s+4));
  rc.arc(x, cy-4, 96, 96, Math.PI, 2*Math.PI, true, S(hair, s+5));
  rc.circle(x-28, cy+22, 12, S(blush, s+6));
  rc.circle(x+28, cy+22, 12, S(blush, s+7));
  if(expr==='effort'){
    rc.line(x-23, cy+2, x-9, cy+9, S(eyeline, s+8));
    rc.line(x+23, cy+2, x+9, cy+9, S(eyeline, s+9));
    rc.line(x-7, cy+30, x+7, cy+30, S(mouth, s+10));
  } else if(expr==='proud'){
    rc.path(`M${x-24},${cy+6} Q${x-16},${cy+13} ${x-8},${cy+6}`, S(eyeline, s+8));
    rc.path(`M${x+8},${cy+6} Q${x+16},${cy+13} ${x+24},${cy+6}`, S(eyeline, s+9));
    rc.path(`M${x-12},${cy+24} Q${x},${cy+38} ${x+12},${cy+24} Z`, S(mouthFill, s+10));
  } else {
    rc.circle(x-16, cy+8, 6, S(dot, s+8));
    rc.circle(x+16, cy+8, 6, S(dot, s+9));
    rc.path(`M${x-10},${cy+26} Q${x},${cy+34} ${x+10},${cy+26}`, S(mouth, s+10));
  }
}
function parentHead(rc, x, cy, s){
  rc.circle(x, cy-60, 26, S(hair, s+1));
  rc.circle(x-50, cy+6, 16, S(skin, s+2));
  rc.circle(x+50, cy+6, 16, S(skin, s+3));
  rc.circle(x, cy, 100, S(skin, s+4));
  rc.arc(x, cy-4, 104, 104, Math.PI, 2*Math.PI, true, S(hair, s+5));
  rc.circle(x-30, cy+24, 14, S(blush, s+6));
  rc.circle(x+30, cy+24, 14, S(blush, s+7));
  rc.path(`M${x-26},${cy+8} Q${x-17},${cy+15} ${x-8},${cy+8}`, S(eyeline, s+8));
  rc.path(`M${x+8},${cy+8} Q${x+17},${cy+15} ${x+26},${cy+8}`, S(eyeline, s+9));
  rc.path(`M${x-11},${cy+28} Q${x},${cy+36} ${x+11},${cy+28}`, S(mouth, s+10));
}

// ---- 体 ----
function childSeated(rc, hipX, hipY, handX, handY, s){
  rc.path(`M${hipX-26},${hipY+2} Q${hipX-30},${hipY+34} ${hipX+6},${hipY+36}
           L${hipX+62},${hipY+34} Q${hipX+80},${hipY+32} ${hipX+78},${hipY+18}
           Q${hipX+74},${hipY+4} ${hipX+44},${hipY+4} Q${hipX+6},${hipY-2} ${hipX-26},${hipY+2} Z`, S(cCloth, s+20));
  rc.circle(hipX+80, hipY+18, 12, S(skin, s+21));
  rc.path(`M${hipX-30},${hipY+4} Q${hipX-34},${hipY-66} ${hipX},${hipY-72}
           Q${hipX+34},${hipY-66} ${hipX+30},${hipY+4} Q${hipX},${hipY+12} ${hipX-30},${hipY+4} Z`, S(cCloth, s+22));
  rc.line(hipX-20, hipY-48, handX, handY, {seed:Math.max(1,(s+23)|0), stroke:P.childArm, strokeWidth:7, roughness:1.5});
  rc.circle(handX, handY, 11, S(skin, s+24));
}
function childStand(rc, x, footY, expr, s){
  // 立ち姿。footY=足元。脚→胴→（proudなら両手up / それ以外は腕なし）
  rc.rectangle(x-13, footY-44, 12, 44, S(skin, s+18));
  rc.rectangle(x+3,  footY-44, 12, 44, S(skin, s+19));
  rc.path(`M${x-30},${footY-44} Q${x-34},${footY-116} ${x},${footY-120}
           Q${x+34},${footY-116} ${x+30},${footY-44} Q${x},${footY-36} ${x-30},${footY-44} Z`, S(cCloth, s+20));
  if(expr==='proud'){
    // 両手をパッと上げる（肩から斜め上へ・頭と重ねない）
    rc.line(x-26, footY-104, x-64, footY-152, {seed:Math.max(1,(s+21)|0), stroke:P.childArm, strokeWidth:7, roughness:1.5});
    rc.line(x+26, footY-104, x+64, footY-152, {seed:Math.max(1,(s+22)|0), stroke:P.childArm, strokeWidth:7, roughness:1.5});
    rc.circle(x-66, footY-154, 10, S(skin, s+23));
    rc.circle(x+66, footY-154, 10, S(skin, s+24));
  }
}
function parentKneel(rc, x, hipY, armEndX, armEndY, s){
  // 膝をついて寄り添う親（正面）。armEnd を動かして「伸びる→止まる→戻る」を表現
  rc.path(`M${x-40},${hipY+6} Q${x-46},${hipY+40} ${x+10},${hipY+42}
           L${x+70},${hipY+40} Q${x+88},${hipY+38} ${x+84},${hipY+22}
           Q${x+78},${hipY+8} ${x+40},${hipY+8} Q${x+4},${hipY} ${x-40},${hipY+6} Z`, S(pCloth, s+20));
  rc.path(`M${x-36},${hipY+8} Q${x-40},${hipY-78} ${x},${hipY-84}
           Q${x+40},${hipY-78} ${x+36},${hipY+8} Q${x},${hipY+16} ${x-36},${hipY+8} Z`, S(pCloth, s+22));
  if(armEndX!==null){
    rc.line(x+24, hipY-56, armEndX, armEndY, {seed:Math.max(1,(s+23)|0), stroke:P.parentArm, strokeWidth:8, roughness:1.5});
    rc.circle(armEndX, armEndY, 13, S(skin, s+24));
  }
}
function parentBackKneel(rc, x, hipY, s){
  // うしろ姿の親（しゃがみ）。頭=髪色のみ
  rc.path(`M${x-42},${hipY+6} Q${x-48},${hipY+42} ${x+8},${hipY+44}
           L${x+64},${hipY+42} Q${x+84},${hipY+40} ${x+80},${hipY+22}
           Q${x+74},${hipY+8} ${x+38},${hipY+8} Q${x+2},${hipY} ${x-42},${hipY+6} Z`, S(pCloth, s+20));
  rc.path(`M${x-36},${hipY+8} Q${x-40},${hipY-72} ${x},${hipY-78}
           Q${x+40},${hipY-72} ${x+36},${hipY+8} Q${x},${hipY+16} ${x-36},${hipY+8} Z`, S(pCloth, s+22));
  rc.circle(x, hipY-118, 50, S(hair, s+24));        // 後頭部（髪）
  rc.circle(x-46, hipY-114, 13, S(skin, s+25));     // 耳
  rc.circle(x+46, hipY-114, 13, S(skin, s+26));
}
function shoeProp(rc, x, y, s){
  rc.path(`M${x},${y} L${x},${y-12} Q${x},${y-18} ${x+8},${y-18} L${x+16},${y-18}
           Q${x+22},${y-18} ${x+25},${y-12} L${x+30},${y-10} Q${x+36},${y-8} ${x+36},${y-4}
           L${x+36},${y-2} Q${x+36},${y+2} ${x+30},${y+2} L${x+4},${y+2} Q${x},${y+2} ${x},${y} Z`, S(shoeOpt, s+30));
}

// ---- 背景・光・文字 ----
function background(ctx, rc, withGround=true){
  ctx.fillStyle = P.paper; ctx.fillRect(0,0,540,960);
  ctx.fillStyle = P.hidamari; ctx.fillRect(0, FLOOR, 540, 960-FLOOR);
  if(withGround) rc.line(0, FLOOR, 540, FLOOR, {...groundOpt, seed:7});
}
function lightEllipse(ctx, cx, cy, rx, ry, alpha){
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rx);
  g.addColorStop(0, `rgba(255,244,206,${alpha})`);
  g.addColorStop(1, 'rgba(255,244,206,0)');
  ctx.save(); ctx.translate(cx, cy); ctx.scale(1, ry/rx); ctx.translate(-cx, -cy);
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, rx, 0, 2*Math.PI); ctx.fill(); ctx.restore();
}
function drawText(ctx, lines, yTop, size, color, alpha=1){
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.fillStyle = color; ctx.textAlign='center'; ctx.textBaseline='alphabetic';
  ctx.font = `${size}px "${FONT}"`;
  let y = yTop;
  for(const ln of lines){ ctx.fillText(ln, 270, y); y += size*1.8; }
  ctx.restore();
}
// シーン内フェード（in 0.3s / out 0.3s）alpha
function fade(lf, total, fin=9, fout=9){
  if(lf < fin) return lf/fin;
  if(lf > total-fout) return Math.max(0,(total-lf)/fout);
  return 1;
}

// ============ シーン（lf=シーン内フレーム, n=シーン総フレーム）============
function S1(ctx, rc, lf, n){ // かかとが、合わない（寄り）
  const f = lf, bs = boilSeed(f);
  background(ctx, rc);
  const armP = (f%15)/15, pull = eIO(armP<0.5?armP*2:(1-armP)*2);
  const hipX=250, hipY=600, headCy=488;
  const hx=(hipX+70)-22*pull, hy=(hipY+18)-6*pull, tilt=0.05*Math.sin(2*Math.PI*f/30);
  ctx.save(); ctx.translate(hipX,hipY); ctx.rotate(-tilt); ctx.translate(-hipX,-hipY);
  childSeated(rc, hipX, hipY, hx, hy, bs); childHead(rc, hipX, headCy, 'effort', bs);
  ctx.restore();
  shoeProp(rc, hipX+96, hipY+24, bs);
  drawText(ctx, ['かかとが、合わない。'], 800, 26, P.text, fade(lf,n));
}
function S2(ctx, rc, lf, n){ // タイトル
  const f=lf+90, bs=boilSeed(f);
  background(ctx, rc);
  const armP=(f%15)/15, pull=eIO(armP<0.5?armP*2:(1-armP)*2);
  const hipX=250, hipY=620, headCy=520;  // 少し引き
  ctx.save(); ctx.translate(hipX,hipY); ctx.scale(0.86,0.86); ctx.translate(-hipX,-hipY);
  childSeated(rc, hipX, hipY, (hipX+70)-22*pull, (hipY+18)-6*pull, bs);
  childHead(rc, hipX, headCy, 'effort', bs);
  ctx.restore();
  const a = fade(lf,n,14,9);
  drawText(ctx, ['じぶんで、はく'], 300, 40, P.text, a);
  drawText(ctx, ['ある朝の、玄関での話。'], 250, 17, P.text, a*0.9);
}
function S3(ctx, rc, lf, n){ // 「もう、貸して」手が出かかって止めた
  const f=lf+180, bs=boilSeed(f);
  background(ctx, rc);
  // 腕：1.2s伸び(easeOut)→0.5s静止→1.5s戻る(easeInOut)  (30fps)
  const t=lf/30; let reach;
  if(t<1.2) reach=eOut(t/1.2);
  else if(t<1.7) reach=1;
  else reach=1-eIO(clamp01((t-1.7)/1.5));
  const childX=300, childY=600;
  const armSX=190, armSY=560;            // 親の肩
  const restX=170, restY=540, tgtX=childX-22, tgtY=childY+18;
  const aex=restX+(tgtX-restX)*reach, aey=restY+(tgtY-restY)*reach;
  childSeated(rc, childX, childY, (childX+70)-6, (childY+18), bs);
  childHead(rc, childX, childY-112, 'effort', bs);
  shoeProp(rc, childX+96, childY+24, bs);
  parentKneel(rc, 150, 590, aex, aey, bs);
  parentHead(rc, 150, 470, bs);
  const a=fade(lf,n,12,9);
  drawText(ctx, ['「もう、貸して」'], 790, 26, P.text, t<1.2?a:a);
  if(t>1.7) drawText(ctx, ['手が出かかって──止めた。'], 836, 24, P.text, fade(lf-Math.floor(1.7*30),n-Math.floor(1.7*30),9,9));
}
function S4(ctx, rc, lf, n){ // 5分だけ、待ってみた（引き・光明滅・うなずき）
  const f=lf+330, bs=boilSeed(f);
  background(ctx, rc);
  const la=0.6+0.2*(0.5+0.5*Math.sin(2*Math.PI*lf/120));
  lightEllipse(ctx, 300, FLOOR+30, 150, 40, la);
  // 親うしろ姿（2回うなずく：頭+3px沈み at lf~40, ~100）
  let nod=0; if(Math.abs(lf-40)<8) nod=3*(1-Math.abs(lf-40)/8); if(Math.abs(lf-100)<8) nod=3*(1-Math.abs(lf-100)/8);
  ctx.save(); ctx.translate(0,nod); parentBackKneel(rc, 200, 600, bs); ctx.restore();
  // 子（時々ぴょこ）
  const hop = (lf%70<6)? -4*(1-(lf%70)/6) : 0;
  ctx.save(); ctx.translate(0,hop);
  childSeated(rc, 330, 604, 396, 616, bs); childHead(rc, 330, 492, 'effort', bs);
  ctx.restore();
  shoeProp(rc, 330+96, 628, bs);
  drawText(ctx, ['5分だけ、待ってみた。'], 800, 26, P.text, fade(lf,n));
}
function S5(ctx, rc, lf, n){ // できた・得意げ（「ふり返りかけ」は廃止＝終始この正面ポーズ）
  const f=lf+510, bs=boilSeed(f);
  background(ctx, rc);
  // 正面・得意げ・立ち上がって片足に靴（S5の最初から）
  ctx.save(); ctx.translate(270,460); ctx.rotate(-0.08); ctx.translate(-270,-460);
  childStand(rc, 270, 600, 'proud', bs);
  childHead(rc, 270, 442, 'proud', bs);
  ctx.restore();
  shoeProp(rc, 250, 600, bs);
  const a=fade(lf,n);
  drawText(ctx, ['できた。'], 790, 30, P.text, a);
  if(lf>20) drawText(ctx, ['あの、得意げな顔。'], 836, 24, P.text, fade(lf-20,n-20,9,9)); // 少し遅れて
}
function S6(ctx, rc, lf, n){ // 並んで正面・光広がる・呼吸
  const f=lf+630, bs=boilSeed(f);
  background(ctx, rc, false);
  const grow = 1+0.15*(lf/n);
  lightEllipse(ctx, 270, 470, 260*grow, 200*grow, 0.5);
  const br = 1+0.01*Math.sin(2*Math.PI*lf/90); // 呼吸
  // 親
  ctx.save(); ctx.translate(190,600); ctx.scale(1,br); ctx.translate(-190,-600);
  parentKneel(rc, 190, 600, null, null, bs);
  ctx.restore(); parentHead(rc, 190, 478, bs);
  // 子
  ctx.save(); ctx.translate(340,612); ctx.scale(1,br); ctx.translate(-340,-612);
  childSeated(rc, 340, 612, 406, 624, bs);
  ctx.restore(); childHead(rc, 340, 500, 'normal', bs);
  drawText(ctx, ['先回りして直すことより、','戻ってこられる場所で','待っていること、なのかも。'], 770, 24, P.text, fade(lf,n,14,9));
}
function S7(ctx, rc, lf, n){ // ハイタッチ：それでも、大丈夫
  const f=lf+780, bs=boilSeed(f);
  background(ctx, rc, false);
  lightEllipse(ctx, 270, 460, 280, 220, 0.5);
  // 親(左・膝つき)と子(右・立つ)の内側の手が中央上で合わさる
  const Mx=270, pop=0.5+0.5*Math.sin(2*Math.PI*lf/36), My=430+(1-pop)*8;
  // 親：片腕を合流点へ
  parentKneel(rc, 172, 600, Mx-8, My+2, bs);
  parentHead(rc, 172, 478, bs);
  // 子：立ち姿（腕なし）＋内側の腕を合流点へ／外側は下に添える
  childStand(rc, 362, 600, 'stand', bs);
  rc.line(362-24, 600-106, Mx+8, My, {seed:Math.max(1,(bs+40)|0), stroke:P.childArm, strokeWidth:7, roughness:1.5});
  rc.circle(Mx+8, My, 11, S(skin, bs+41));
  rc.line(362+26, 600-104, 362+44, 600-66, {seed:Math.max(1,(bs+42)|0), stroke:P.childArm, strokeWidth:7, roughness:1.5});
  rc.circle(362+46, 600-64, 10, S(skin, bs+43));
  childHead(rc, 362, 442, 'normal', bs);
  shoeProp(rc, 344, 600, bs);
  // 手が合う瞬間の小さなひかり（パチン）
  if(pop>0.82){
    rc.line(Mx-14,My-14,Mx-5,My-6,{seed:5,stroke:'#E8B450',strokeWidth:2,roughness:1});
    rc.line(Mx+14,My-14,Mx+5,My-6,{seed:6,stroke:'#E8B450',strokeWidth:2,roughness:1});
    rc.line(Mx,My-18,Mx,My-9,{seed:8,stroke:'#E8B450',strokeWidth:2,roughness:1});
  }
  drawText(ctx, ['それでも、大丈夫。'], 800, 26, P.text, fade(lf,n));
}
function S8(ctx, rc, lf, n){ // ブランド
  background(ctx, rc, false);
  const a=fade(lf,n,12,16);
  drawText(ctx, ['ひだまりこそだち'], 430, 34, P.text, a);
  drawText(ctx, ['子育ての考え方を、親のことばに'], 500, 20, P.text, a*0.95);
  drawText(ctx, ['くわしくは プロフィールの note から'], 560, 18, P.text, a*0.9);
}

const TL = [[S1,90],[S2,90],[S3,150],[S4,180],[S5,120],[S6,150],[S7,90],[S8,60]];

const dir = path.join(__dirname, 'frames_full');
fs.mkdirSync(dir, {recursive:true});
// canvasは1枚だけ作って使い回す（毎フレーム生成はメモリ肥大→スワップで激遅になるため）
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');
const rc = rough.canvas(canvas);
let gi=0;
for(const [fn, n] of TL){
  for(let lf=0; lf<n; lf++){
    ctx.setTransform(1,0,0,1,0,0);
    ctx.clearRect(0,0,W,H);
    ctx.scale(2,2);
    fn(ctx, rc, lf, n);
    fs.writeFileSync(path.join(dir, `f_${String(gi).padStart(5,'0')}.png`), canvas.toBuffer('image/png'));
    gi++;
  }
}
console.log('[OK]', gi, 'frames ->', dir, '/', (gi/30).toFixed(1), 's');

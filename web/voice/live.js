'use strict';
const liveKey=window.MARVOI_KEY;
const voiceRuntime={stream:null,ctx:null,node:null,source:null,sink:null,callId:null,ready:false,state:'idle',epoch:0,abort:null,busy:false,speaking:false,replySource:null,recording:false,frames:[],pre:[],voicedMs:0,lastVoice:0,speechAt:0,rate:16000,noise:.003,tailUntil:0,bargedMs:0,metrics:[],taskSeq:0,textBusy:false,replyUrl:null};
let liveReady=false,livePlan=null,typedSequence=0,taskBusy=false,loadingText='正在準備本機模型…';
let partialEnabled=false,partialPending=false,partialFrames=[],partialUtterance=0;
function clearPartial(){partialFrames=[];partialUtterance++;}
function sendPartial(frames,rate){
  if(!partialEnabled||partialPending||!callActive||!voiceRuntime.callId)return;
  const id=voiceRuntime.callId,epoch=voiceRuntime.epoch,utterance=String(partialUtterance);partialPending=true;
  api('/api/voice/partial',encodeWav(frames,rate),{headers:{'Content-Type':'audio/wav','X-Call-ID':id,'X-Utterance':utterance}})
    .then(v=>{if(callActive&&voiceRuntime.epoch===epoch&&String(partialUtterance)===utterance&&v.text)$('callTranscript').textContent=v.text;})
    .catch(()=>{}).finally(()=>{partialPending=false;});
}
function bufferPartial(a,rate){
  if(!partialEnabled)return;
  partialFrames.push(a);
  const size=partialFrames.reduce((n,f)=>n+f.length,0);
  if(size>rate*3){partialFrames=[];partialUtterance++;return;}
  if(size>=rate*.65&&!partialPending){const f=partialFrames;partialFrames=[];sendPartial(f,rate);}
}
function syncTextControls(){
  $('taskSend').disabled=taskBusy;
  $('chatSend').disabled=voiceRuntime.textBusy;
  $('taskSend').setAttribute('aria-busy',String(taskBusy));
}
let activeSearch=null,searchPolling=false;
function paintSearchProgress(p){
  activeSearch=p;
  for(const prefix of ['task','call']){
    const box=$(prefix+'SearchProgress'),label=$(prefix+'SearchLabel'),bar=$(prefix+'SearchBar'),cancel=$(prefix+'SearchCancel');
    box.hidden=!p;
    if(!p)continue;
    if(prefix==='task'&&mode==='chat'&&voiceRuntime.textBusy)setMode('task');
    label.textContent=p.cancelling?'正在停止，完成當前圖片後結束…':'圖片辨識 '+p.done+' / '+p.total+' · 符合 '+p.matched+(p.cached?' · 重用 '+p.cached:'');
    bar.max=Math.max(1,p.total);bar.value=p.done;cancel.disabled=p.cancelling;
  }
}
async function pollSearchProgress(){
  if(searchPolling||!(taskBusy||voiceRuntime.textBusy||voiceRuntime.busy||activeSearch))return;
  searchPolling=true;
  try{const v=await api('/api/search/status',{}, {method:'GET'});paintSearchProgress(v.progress);}
  catch(e){}finally{searchPolling=false;}
}
for(const prefix of ['task','call'])$(prefix+'SearchCancel').onclick=async()=>{
  const p=activeSearch;if(!p)return;
  try{const v=await api('/api/search/cancel',{id:p.id});if(v.cancelled)paintSearchProgress({...p,cancelling:true});}catch(e){showTaskStatus(shortError(e));}
};
setInterval(pollSearchProgress,350);
function showTaskStatus(text){const node=$('taskFeedback');node.textContent=text;node.title=text;node.scrollIntoView({block:'nearest'});}
let localScopeState=null,localPolling=false;
function paintLocalStatus(s){
  localScopeState=s;
  const active=!!s.mode;
  $('localIndexState').textContent=!active?'尚未啟用':(s.state==='scanning'?'建立索引中':s.state==='complete'?'索引就緒':s.state==='partial'?'部分索引':'索引未完成')+' · '+s.indexed+' 個檔案';
  $('localPersonal').hidden=s.mode==='personal'||s.mode==='drives';
  $('localDrives').hidden=s.mode==='drives';
  $('localRefresh').hidden=!active;$('localRevoke').hidden=!active;
  $('localRefresh').disabled=s.state==='scanning';
  $('localRoots').hidden=!active;
  $('localRoots').textContent=active?'已授權範圍：\\n'+s.roots.map(r=>r.path).join('\\n'):'';
}
async function refreshLocalStatus(){
  if(localPolling)return;localPolling=true;
  try{paintLocalStatus(await api('/api/local/status',{}, {method:'GET'}));}catch(e){$('localIndexState').textContent='無法取得索引狀態';}
  finally{localPolling=false;}
}
async function changeLocalScope(mode){
  if(mode==='drives'&&!window.confirm('授權搜尋本機固定及外接磁碟中目前帳號可讀取的常見文件、圖片和媒體。排除系統與常見敏感位置；資料不會傳至雲端。此功能為唯讀。是否啟用？'))return;
  if(mode===null&&!window.confirm('停用本機搜尋並清除本機檔案索引及結果，不會刪除原始檔案。是否繼續？'))return;
  try{
    paintLocalStatus(await api('/api/local/scope',{mode,consent:mode!==null}));typedSequence++;$('callFiles').replaceChildren();$('callFiles').hidden=true;if(fileDialog.open)fileDialog.close();
    $('localNext').hidden=true;$('localPreview').hidden=true;$('localPreview').textContent='';
    if(!mode){$('files').replaceChildren();$('files').hidden=true;$('empty').hidden=false;showTaskStatus('已停用本機搜尋並清除索引。');}
    else showTaskStatus('已授權本機檔案搜尋。索引建立時也可以搜尋已完成的部分。');
  }catch(e){showTaskStatus(shortError(e));}
}
$('localPersonal').onclick=()=>changeLocalScope('personal');
$('localDrives').onclick=()=>changeLocalScope('drives');
$('localRevoke').onclick=()=>changeLocalScope(null);
$('localRefresh').onclick=async()=>{try{paintLocalStatus(await api('/api/local/refresh'));typedSequence++;$('localNext').hidden=true;$('localPreview').hidden=true;showTaskStatus('正在重新建立索引。');}catch(e){showTaskStatus(shortError(e));}};
$('localNext').onclick=async()=>{
  if(taskBusy)return;taskBusy=true;syncTextControls();$('localNext').disabled=true;showTaskStatus('正在搜尋下一批檔案…');
  const seq=++typedSequence;
  try{const v=await api('/api/local/next');if(seq===typedSequence)applyTask(v.result);}catch(e){if(seq===typedSequence)showTaskStatus(shortError(e));}
  finally{taskBusy=false;syncTextControls();$('localNext').disabled=false;}
};
let filePreviewUrl=null;
const cardPreviewUrls=new WeakMap();
const cardPreviewObserver=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;const image=entry.target;cardPreviewObserver.unobserve(image);const asset=cardPreviewUrls.get(image);if(!asset)continue;resultFile(asset,'thumbnail').then(blob=>{if(!image.isConnected)return;const reader=new FileReader();reader.onload=()=>{if(image.isConnected){image.src=reader.result;image.hidden=false;}};reader.readAsDataURL(blob);}).catch(()=>{image.hidden=true;});}}, {rootMargin:'40px'});
function clearFilePreview(){
  if(filePreviewUrl){URL.revokeObjectURL(filePreviewUrl);filePreviewUrl=null;}
  $('localPreview').replaceChildren();$('localPreview').hidden=true;
}
async function resultFile(asset,action){
  const response=await fetch('/api/results/file',{method:'POST',headers:{'X-MarVoi-Key':liveKey,'Content-Type':'application/json'},body:JSON.stringify({source:asset.source,id:asset.id,action})});
  if(!response.ok){const value=await response.json();throw new Error(value.error||'檔案無法取得。');}
  if(action==='open'||action==='text')return response.json();
  return response.blob();
}
function showFileMessage(text){
  if(mode==='call'){$('callTaskStatus').textContent=text;$('callTaskStatus').hidden=false;}
  else showTaskStatus(text);
}
function renderFileCards(rows,host){
  host.replaceChildren();
  for(const asset of rows){
    const row=document.createElement('div');row.className='file result-file-card';
    const body=document.createElement('div');body.className='file-detail';
    const name=document.createElement('div');name.className='filename';name.textContent=asset.name;
    const path=document.createElement('div');path.className='path';path.style.overflowWrap='anywhere';path.textContent=asset.path;
    const reason=document.createElement('div');reason.className='path';reason.textContent=(asset.match==='uncertain'?'需確認 · ':'')+(asset.reason||'');
    const actions=document.createElement('div');actions.className='local-result-actions';
    function add(label,fn,cls='secondary'){const b=document.createElement('button');b.type='button';b.className=cls;b.textContent=label;b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){showFileMessage(shortError(e));}finally{b.disabled=false;}};actions.append(b);}
    if(asset.can_open)add('開啟原檔',async()=>{await resultFile(asset,'open');showFileMessage('已開啟：'+asset.name);});
    if(asset.can_download)add('下載檔案',async()=>{const blob=await resultFile(asset,'download');const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=asset.name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);});
    if(asset.image_preview)add('圖片預覽',async()=>{const blob=await resultFile(asset,'thumbnail');if(!row.isConnected)return;clearFilePreview();filePreviewUrl=URL.createObjectURL(blob);const dialog=$('resultPreviewDialog');const image=$('resultPreviewImage');image.src=filePreviewUrl;image.alt=asset.name;image.hidden=false;$('resultPreviewText').hidden=true;$('resultPreviewTitle').textContent=asset.name;if(!dialog.open)dialog.showModal();},'ghost');
    if(asset.previewable)add('文字預覽',async()=>{const v=await resultFile(asset,'text');if(!row.isConnected)return;clearFilePreview();$('resultPreviewTitle').textContent=v.name;$('resultPreviewImage').hidden=true;$('resultPreviewText').textContent=v.text;$('resultPreviewText').hidden=false;if(!$('resultPreviewDialog').open)$('resultPreviewDialog').showModal();},'ghost');
    if(asset.source==='local')add('所在資料夾',()=>api('/api/local/reveal',{id:asset.id}),'ghost');
    if(asset.image_preview){
      const image=document.createElement('img');image.className='result-thumb';image.alt=asset.name;image.hidden=false;
      row.append(image);cardPreviewUrls.set(image,asset);cardPreviewObserver.observe(image);
    }else{
      const mark=document.createElement('div');mark.className='result-type';mark.textContent=(asset.name.split('.').pop()||'FILE').toUpperCase();row.append(mark);
    }
    body.append(name,path,reason,actions);row.append(body);host.append(row);
  }
  host.hidden=!rows.length;
}
const fileDialog=document.createElement('dialog');fileDialog.id='resultPreviewDialog';fileDialog.className='result-preview-dialog';
fileDialog.innerHTML='<div class="metrics-head"><strong id="resultPreviewTitle"></strong><button id="resultPreviewClose" class="icon-btn" aria-label="關閉">×</button></div><img id="resultPreviewImage" hidden><pre id="resultPreviewText" hidden></pre>';
document.body.append(fileDialog);$('resultPreviewClose').onclick=()=>fileDialog.close();
fileDialog.addEventListener('close',()=>{if(filePreviewUrl){URL.revokeObjectURL(filePreviewUrl);filePreviewUrl=null;}$('resultPreviewImage').removeAttribute('src');$('resultPreviewText').textContent='';});
function renderLocalResults(result){
  renderFileCards(result.file_results||[],$('files'));
  $('empty').hidden=!!(result.file_results||[]).length;
  $('localNext').hidden=!result.local_more;
}
function renderSearchResults(result){
  if(result.local_results){renderLocalResults(result);return;}
  if(result.file_results){renderFileCards(result.file_results,$('files'));$('empty').hidden=!!result.file_results.length;return;}
  const rows=result.visual_results?[...result.visual_results.yes.map(a=>({...a,label:'符合'})),...result.visual_results.uncertain.map(a=>({...a,label:'需確認'}))]:(result.selected||[]).map(name=>({name,label:'搜尋結果'}));
  const host=$('files');host.replaceChildren();
  for(const asset of rows){const row=document.createElement('div');row.className='file';const body=document.createElement('div');body.className='file-detail';const name=document.createElement('div');name.className='filename';name.textContent=asset.name;const detail=document.createElement('div');detail.className='path';detail.textContent=asset.label+(asset.reason?' · '+asset.reason:'');body.append(name,detail);row.append(body);host.append(row);}
  host.hidden=!rows.length;$('empty').hidden=!!rows.length;
}
async function api(path,body={},options={}){
  const headers={'X-MarVoi-Key':liveKey,...options.headers};const init={method:options.method||'POST',headers,signal:options.signal};
  if(init.method!=='GET'){if(body instanceof Blob||body instanceof File)init.body=body;else{headers['Content-Type']='application/json';init.body=JSON.stringify(body);}}
  const response=await fetch(path,init);const data=await response.json();if(!response.ok){const error=new Error(data.error||response.statusText);error.status=response.status;throw error;}return data;
}
function shortError(error){if(error?.name==='NotAllowedError')return language==='zh'?'請允許麥克風權限。':'Allow microphone access.';if(error?.name==='NotFoundError')return language==='zh'?'找不到麥克風。':'No microphone found.';return String(error?.message||error).slice(0,150);}
function liveStatus(s){voiceRuntime.state=s;updateCallUI();}
function resetCapture(){clearPartial();voiceRuntime.recording=false;voiceRuntime.frames=[];voiceRuntime.pre=[];voiceRuntime.voicedMs=0;voiceRuntime.lastVoice=0;voiceRuntime.speechAt=0;}
function interruptReply(){
  if(voiceRuntime.abort){voiceRuntime.abort.abort();voiceRuntime.abort=null;}
  if(voiceRuntime.replySource){try{voiceRuntime.replySource.stop();}catch{}voiceRuntime.replySource=null;}
  voiceRuntime.speaking=false;voiceRuntime.busy=false;voiceRuntime.epoch++;voiceRuntime.tailUntil=performance.now()+220;resetCapture();
  if(callActive&&voiceRuntime.callId)api('/api/call/cancel').catch(()=>{});
  if(callActive&&voiceRuntime.ready)liveStatus(callMuted?'muted':'listening');
}
updateCallTime=function(){const seconds=callActive&&voiceRuntime.ready?Math.max(0,Math.floor((Date.now()-callStarted)/1000)):0;$('callTime').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');};
updateCallUI=function(){
  const zh=language==='zh',states={idle:zh?'未接通':'Not connected',loading:zh?'準備語音…':'Preparing voice…',listening:zh?'聆聽中':'Listening',recording:zh?'正在聆聽':'Listening',processing:zh?'辨識與思考中…':'Recognizing…',speaking:zh?'回覆中':'Speaking',muted:zh?'已靜音':'Muted',ended:zh?'已掛斷':'Call ended',error:zh?'通話未完成':'Call error'};
  $('callState').textContent=states[voiceRuntime.state]||states.idle;$('callAvatar').classList.toggle('is-active',callActive&&!callMuted);$('callTab').classList.toggle('call-active',callActive);$('callToggle').classList.toggle('is-active',callActive);$('callToggle').setAttribute('aria-pressed',String(callActive));$('callToggle').disabled=!liveReady;
  $('callToggle').title=callActive?(zh?'掛斷':'Hang up'):(zh?'開始通話':'Start call');$('callToggle').setAttribute('aria-label',$('callToggle').title);$('callMute').disabled=!callActive||!voiceRuntime.ready;$('callMute').setAttribute('aria-pressed',String(callMuted));$('callMute').innerHTML=icon(callMuted?'micOff':'mic');$('callMute').title=callMuted?(zh?'取消靜音':'Unmute'):(zh?'靜音':'Mute');$('callMute').setAttribute('aria-label',$('callMute').title);
  const stop=voiceRuntime.busy||voiceRuntime.speaking;$('callDemo').disabled=!callActive||!voiceRuntime.ready||(callMuted&&!stop);$('callDemo').innerHTML=stop?'<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>':icon('up');$('callDemo').title=stop?(zh?'打斷回覆':'Interrupt'):(zh?'送出這段語音':'Send voice');$('callDemo').setAttribute('aria-label',$('callDemo').title);
  $('callChatMode').setAttribute('aria-pressed',String(callMode==='chat'));$('callTaskMode').setAttribute('aria-pressed',String(callMode==='task'));
  document.querySelector('.call-note').textContent=callActive?(zh?'本機辨識與朗讀':'Local speech processing'):(zh?'麥克風未啟用':'Microphone off');updateCallTime();
};
function encodeWav(frames,rate){
  const length=frames.reduce((n,f)=>n+f.length,0);const buffer=new ArrayBuffer(44+length*2),v=new DataView(buffer);const write=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};write(0,'RIFF');v.setUint32(4,36+length*2,true);write(8,'WAVE');write(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);write(36,'data');v.setUint32(40,length*2,true);let at=44;for(const frame of frames)for(const x of frame){const value=Math.max(-1,Math.min(1,x));v.setInt16(at,value<0?value*32768:value*32767,true);at+=2;}return new Blob([buffer],{type:'audio/wav'});
}
function audioFrame(message){
  if(!callActive||!voiceRuntime.ready||callMuted)return;const a=message.samples,now=performance.now();voiceRuntime.rate=message.rate;
  let sum=0;for(const x of a)sum+=x*x;const rms=Math.sqrt(sum/a.length),ms=a.length/message.rate*1000;
  if(voiceRuntime.speaking){if(rms>Math.max(.045,voiceRuntime.noise*4))voiceRuntime.bargedMs+=ms;else voiceRuntime.bargedMs=0;if(voiceRuntime.bargedMs>240){voiceRuntime.bargedMs=0;interruptReply();}return;}
  if(taskBusy||voiceRuntime.textBusy||voiceRuntime.busy||now<voiceRuntime.tailUntil)return;
  const threshold=Math.max(.012,Math.min(.04,voiceRuntime.noise*3));
  if(!voiceRuntime.recording){
    voiceRuntime.pre.push(a);while(voiceRuntime.pre.reduce((n,f)=>n+f.length,0)>message.rate*.35)voiceRuntime.pre.shift();
    if(rms>threshold)voiceRuntime.voicedMs+=ms;else{voiceRuntime.voicedMs=0;voiceRuntime.noise=.98*voiceRuntime.noise+.02*Math.min(rms,.012);}
    if(voiceRuntime.voicedMs>=120){voiceRuntime.recording=true;voiceRuntime.frames=voiceRuntime.pre;clearPartial();for(const f of voiceRuntime.pre)bufferPartial(f,message.rate);voiceRuntime.pre=[];voiceRuntime.speechAt=now-voiceRuntime.voicedMs;voiceRuntime.lastVoice=now;liveStatus('recording');}return;
  }
  voiceRuntime.frames.push(a);bufferPartial(a,message.rate);if(rms>threshold)voiceRuntime.lastVoice=now;
  if(now-voiceRuntime.lastVoice>=1100||now-voiceRuntime.speechAt>=20000)flushVoice();
}
async function flushVoice(force=false){
  if(!callActive||!voiceRuntime.ready||callMuted||voiceRuntime.busy||voiceRuntime.speaking)return;
  if(!voiceRuntime.frames.length){if(!force||!voiceRuntime.pre.length)return;voiceRuntime.frames=voiceRuntime.pre;voiceRuntime.lastVoice=performance.now();}
  const frames=voiceRuntime.frames,rate=voiceRuntime.rate,end=voiceRuntime.lastVoice||performance.now(),modeAtStart=callMode,id=voiceRuntime.callId,epoch=++voiceRuntime.epoch;const vad=(performance.now()-end)/1000;resetCapture();voiceRuntime.busy=true;liveStatus('processing');const started=performance.now();const controller=new AbortController();voiceRuntime.abort=controller;
  try{
    const wav=encodeWav(frames,rate);let value;let retryBegan=performance.now();
    while(true){try{value=await api('/api/voice/turn',wav,{headers:{'Content-Type':'audio/wav','X-Voice-Mode':modeAtStart,'X-Call-ID':id},signal:controller.signal});break;}catch(e){if(e.status===409&&e.message==='BUSY'&&performance.now()-retryBegan<8000){await new Promise(r=>setTimeout(r,180));continue;}throw e;}}
    if(!callActive||epoch!==voiceRuntime.epoch||id!==voiceRuntime.callId)return;
    if(value.status==='cancelled'||value.status==='no_speech'){voiceRuntime.busy=false;if(value.status==='no_speech')$('callTranscript').textContent=language==='zh'?'沒有辨識到清楚語音，請再說一次。':'No clear speech detected. Try again.';liveStatus(callMuted?'muted':'listening');return;}
    paintSearchProgress(null);$('callTranscript').textContent=value.recognized;
    if(value.result?.mode==='task'){
      applyTask(value.result);
      renderFileCards(value.result.file_results||[],$('callFiles'));
      const result=value.result;
      $('callTaskStatus').textContent=result.status==='preview'?'已產生分類預覽，尚未搬移檔案。':result.status==='searched'||result.status==='listed'?'找到 '+(result.selected||[]).length+' 個確定符合的檔案。'+(result.local_more?' 還有下一批候選。':''):result.text;
      $('callTaskStatus').hidden=false;
      $('callTaskView').hidden=!['preview','searched','listed','read','indexed','completed'].includes(result.status);
    }else if(value.result){
      $('callTaskStatus').hidden=true;$('callTaskView').hidden=true;$('callFiles').replaceChildren();$('callFiles').hidden=true;
      message('user',value.recognized);message('assistant',value.result.text);
    }
    if(!value.audio){liveStatus(callMuted?'muted':'listening');return;}
    const response=await fetch(value.audio.url,{headers:{'X-MarVoi-Key':liveKey},signal:controller.signal});if(!response.ok)throw new Error('語音檔讀取失敗。');const decodeBegan=performance.now();const audio=await voiceRuntime.ctx.decodeAudioData(await response.arrayBuffer());
    if(!callActive||epoch!==voiceRuntime.epoch)return;
    const speaker=voiceRuntime.ctx.createBufferSource();speaker.buffer=audio;speaker.connect(voiceRuntime.ctx.destination);voiceRuntime.replySource=speaker;voiceRuntime.busy=false;voiceRuntime.speaking=true;liveStatus('speaking');const play=performance.now();speaker.start();
    const metrics={turn_id:value.turn_id,speech_end_to_play_s:(play-end)/1000,client_total_s:(play-started)/1000,vad_wait_s:vad,network_wait_s:(decodeBegan-started)/1000,audio_decode_s:(play-decodeBegan)/1000,audio_output_latency_s:(voiceRuntime.ctx.baseLatency||0)+(voiceRuntime.ctx.outputLatency||0)};voiceRuntime.metrics.push({...value.metrics,...metrics});voiceRuntime.metrics=voiceRuntime.metrics.slice(-30);renderMetrics();api('/api/metrics',metrics).catch(()=>{});window.dispatchEvent(new CustomEvent('marvoi-playback',{detail:metrics}));
    let nextIndex=1;
    const finish=()=>{voiceRuntime.replySource=null;voiceRuntime.speaking=false;voiceRuntime.abort=null;voiceRuntime.tailUntil=performance.now()+250;resetCapture();if(callActive)liveStatus(callMuted?'muted':'listening');};
    const prefetch=async(index)=>{
      if(index>=(value.chunk_count||1))return null;
      const chunk=await api('/api/voice/chunk',{call_id:id,turn_id:value.turn_id,index},{signal:controller.signal});
      const r=await fetch(chunk.audio.url,{headers:{'X-MarVoi-Key':liveKey},signal:controller.signal});if(!r.ok)throw new Error('語音分段讀取失敗。');
      return voiceRuntime.ctx.decodeAudioData(await r.arrayBuffer());
    };
    let next=prefetch(nextIndex).catch(()=>null);
    const ended=async(current)=>{
      if(voiceRuntime.replySource!==current||!callActive||epoch!==voiceRuntime.epoch)return;
      const data=await next;
      if(voiceRuntime.replySource!==current||!callActive||epoch!==voiceRuntime.epoch)return;
      if(!data){finish();return;}
      const node=voiceRuntime.ctx.createBufferSource();node.buffer=data;node.connect(voiceRuntime.ctx.destination);voiceRuntime.replySource=node;next=prefetch(++nextIndex).catch(()=>null);node.onended=()=>ended(node);node.start();
    };
    speaker.onended=()=>ended(speaker);
  }catch(error){if(error.name!=='AbortError'&&callActive){$('callTranscript').textContent=shortError(error);liveStatus('error');api('/api/metrics',{error:shortError(error)}).catch(()=>{});}}
  finally{if(epoch===voiceRuntime.epoch){if(!voiceRuntime.speaking)voiceRuntime.abort=null;voiceRuntime.busy=false;if(callActive&&!voiceRuntime.speaking&&voiceRuntime.state!=='error')liveStatus(callMuted?'muted':'listening');}}
}
startCall=async function(){
  if(!liveReady||callActive)return;const epoch=++voiceRuntime.epoch;callActive=true;callMuted=false;callEnded=false;liveStatus('loading');$('callTranscript').textContent='';$('callTaskStatus').hidden=true;$('callTaskView').hidden=true;$('callFiles').replaceChildren();$('callFiles').hidden=true;
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});if(!callActive||epoch!==voiceRuntime.epoch){stream.getTracks().forEach(t=>t.stop());return;}voiceRuntime.stream=stream;
    const ctx=new AudioContext({sampleRate:16000});voiceRuntime.ctx=ctx;await ctx.resume();await ctx.audioWorklet.addModule('/audio-worklet.js');const source=ctx.createMediaStreamSource(stream),node=new AudioWorkletNode(ctx,'marvoi-pcm'),sink=ctx.createGain();sink.gain.value=0;source.connect(node);node.connect(sink);sink.connect(ctx.destination);node.port.onmessage=e=>audioFrame(e.data);voiceRuntime.source=source;voiceRuntime.node=node;voiceRuntime.sink=sink;
    const reply=await api('/api/call/start');if(!callActive||epoch!==voiceRuntime.epoch){api('/api/call/end').catch(()=>{});return;}
    voiceRuntime.callId=reply.call_id;partialEnabled=!!reply.partial_asr;voiceRuntime.ready=true;voiceRuntime.noise=.003;callStarted=Date.now();resetCapture();if(callTimer!==null)clearInterval(callTimer);callTimer=setInterval(updateCallTime,250);liveStatus('listening');
  }catch(error){await endCall();$('callTranscript').textContent=shortError(error);liveStatus('error');}
};
endCall=async function(){
  const was=callActive;callActive=false;callMuted=false;voiceRuntime.ready=false;partialEnabled=false;voiceRuntime.callId=null;voiceRuntime.epoch++;if(callTimer!==null)clearInterval(callTimer);callTimer=null;
  if(voiceRuntime.abort)voiceRuntime.abort.abort();voiceRuntime.abort=null;
  if(voiceRuntime.replySource){try{voiceRuntime.replySource.stop();}catch{}voiceRuntime.replySource=null;}
  voiceRuntime.speaking=false;voiceRuntime.busy=false;voiceRuntime.stream?.getTracks().forEach(t=>t.stop());voiceRuntime.stream=null;voiceRuntime.node?.disconnect();voiceRuntime.source?.disconnect();voiceRuntime.sink?.disconnect();voiceRuntime.node=null;voiceRuntime.source=null;voiceRuntime.sink=null;const ctx=voiceRuntime.ctx;voiceRuntime.ctx=null;resetCapture();liveStatus(was?'ended':'idle');if(ctx)await ctx.close().catch(()=>{});if(was)api('/api/call/end').catch(()=>{});
};
function switchCallMode(next){if(next===callMode)return;if(voiceRuntime.ready)interruptReply();callMode=next;updateCallUI();}
$('callTaskView').onclick=()=>{setMode('task');window.MarVoiSidebar?.close();};
$('callToggle').onclick=()=>callActive?endCall():startCall();$('callMute').onclick=()=>{if(!callActive||!voiceRuntime.ready)return;callMuted=!callMuted;voiceRuntime.stream?.getAudioTracks().forEach(t=>t.enabled=!callMuted);resetCapture();liveStatus(callMuted?'muted':'listening');};$('callDemo').onclick=()=>voiceRuntime.busy||voiceRuntime.speaking?interruptReply():flushVoice(true);$('callChatMode').onclick=()=>switchCallMode('chat');$('callTaskMode').onclick=()=>switchCallMode('task');

function renderTaskItems(items){
  $('files').replaceChildren();for(const item of items){const row=document.createElement('div');row.className='file';row.dataset.source=item.source;row.dataset.destination=item.destination;const sign=document.createElement('span');sign.className='file-icon';sign.innerHTML=icon(/\.(png|jpe?g|webp)$/i.test(item.name)?'image':'files');const detail=document.createElement('div');detail.className='file-detail';const name=document.createElement('div');name.className='filename';name.textContent=item.name;const path=document.createElement('div');path.className='path';path.textContent=item.source.substring(0,item.source.lastIndexOf('/')+1)+' → '+item.destination.substring(0,item.destination.lastIndexOf('/')+1);const full=document.createElement('div');full.className='path full-path';full.hidden=true;full.textContent=item.source+'\n→ '+item.destination;const toggle=document.createElement('button');toggle.className='icon-btn path-details';toggle.title='完整路徑';toggle.setAttribute('aria-label','完整路徑');toggle.innerHTML='<svg viewBox="0 0 24 24"><path d="m8 10 4 4 4-4"/></svg>';toggle.onclick=()=>{full.hidden=!full.hidden;};detail.append(name,path,full);row.append(sign,detail,toggle);$('files').append(row);}
}
function applyTask(result){
  $('localNext').hidden=true;$('localPreview').hidden=true;$('localPreview').textContent='';
  if(result.preserve_pending){$('taskFeedback').textContent=result.text;return;}
  livePlan=result.status==='preview'?result.plan_id:null;pending=!!livePlan;const items=result.items||[];renderTaskItems(items);$('files').hidden=!items.length;$('empty').hidden=!!items.length;$('previewBadge').hidden=!pending;$('previewBadge').textContent=items.length+(language==='zh'?' 份':' files');$('confirmation').hidden=!pending;$('taskFeedback').textContent=result.status==='preview'?'':result.text;
  if(result.status!=='preview')$('taskFeedback').title=result.text;
  if(['searched','listed','read'].includes(result.status))renderSearchResults(result);
}
sendChat=async function(){const input=$('chatInput'),text=input.value.trim();if(!text||voiceRuntime.textBusy)return;
  if(!liveReady){message('assistant',loadingText);return;}
  if(taskBusy){message('assistant','目前正在處理任務，請等結果完成後再送出。');return;}
  voiceRuntime.textBusy=true;syncTextControls();
  try{const v=await api('/api/text',{mode:'chat',text});message('user',text);message('assistant',v.result.text);if(v.result.mode==='task'){applyTask(v.result);setMode('task');}if(input.value.trim()===text)input.value='';}
  catch(e){message('assistant',e.message==='BUSY'?'目前正在處理其他請求，文字已保留，請稍後重試。':shortError(e));}
  finally{voiceRuntime.textBusy=false;syncTextControls();}
};
previewTask=async function(){
  const input=$('taskInput'),text=input.value.trim();
  if(!text){input.focus();return;}
  if(taskBusy){showTaskStatus('上一個任務正在處理，這段文字已保留。');return;}
  if(!liveReady){showTaskStatus(loadingText+' 文字已保留，模型就緒後可重新送出。');return;}
  if(voiceRuntime.textBusy){showTaskStatus('對話尚未完成，文字已保留，請稍後重試。');return;}
  taskBusy=true;syncTextControls();
  const seq=++typedSequence;
  showTaskStatus('已送出任務，正在理解指令與檢查素材…');
  try{
    if(callActive)await endCall();
    const v=await api('/api/text',{mode:'task',text});
    if(seq===typedSequence){
      paintSearchProgress(null);applyTask(v.result);
      if(!['error','clarify','refused','cancelled'].includes(v.result.status)&&input.value.trim()===text)input.value='';
    }
  }catch(e){
    if(seq===typedSequence)showTaskStatus(e.message==='BUSY'?'模型正在處理上一個請求；任務文字已保留，請稍後重試。':'任務未完成：'+shortError(e)+'。文字已保留，可重新送出。');
  }finally{taskBusy=false;syncTextControls();input.focus();}
};
$('chatSend').onclick=sendChat;$('taskSend').onclick=previewTask;
async function refreshAssets(){const v=await api('/api/assets',{}, {method:'GET'});assets=v.assets;updateCount();}
sampleAssets=async function(){if(!liveReady)return;try{await api('/api/assets/demo');livePlan=null;resetPreview();await refreshAssets();$('taskInput').value='整理本週的圖片與文案，先預覽。';$('taskFeedback').textContent='';}catch(e){$('taskFeedback').textContent=shortError(e);}};
$('demo').onclick=sampleAssets;$('reset').onclick=sampleAssets;$('fileInput').onchange=async e=>{if(!liveReady)return;const files=[...e.target.files];e.target.value='';if(files.length>100){$('taskFeedback').textContent='每次最多100份。';return;}try{for(const f of files)await api('/api/assets/import?name='+encodeURIComponent(f.name),f,{headers:{'Content-Type':'application/octet-stream'}});livePlan=null;resetPreview();await refreshAssets();$('taskFeedback').textContent='';}catch(error){$('taskFeedback').textContent=shortError(error);}};
async function playControlAudio(audio,epoch,started){
  if(!audio||!callActive||epoch!==voiceRuntime.epoch||!voiceRuntime.ctx)return;
  const response=await fetch(audio.url,{headers:{'X-MarVoi-Key':liveKey}});if(!response.ok)throw new Error('語音檔讀取失敗。');const decoded=await voiceRuntime.ctx.decodeAudioData(await response.arrayBuffer());
  if(!callActive||epoch!==voiceRuntime.epoch||!voiceRuntime.ctx)return;
  const source=voiceRuntime.ctx.createBufferSource();source.buffer=decoded;source.connect(voiceRuntime.ctx.destination);voiceRuntime.replySource=source;voiceRuntime.speaking=true;voiceRuntime.busy=false;liveStatus('speaking');source.start();api('/api/metrics',{confirmation_to_play_s:(performance.now()-started)/1000}).catch(()=>{});
  source.onended=()=>{if(voiceRuntime.replySource===source){voiceRuntime.replySource=null;voiceRuntime.speaking=false;voiceRuntime.tailUntil=performance.now()+250;resetCapture();if(callActive)liveStatus(callMuted?'muted':'listening');}};
}
async function controlTask(action){
  if(!livePlan)return;const id=livePlan,started=performance.now();$('confirm').disabled=true;$('cancel').disabled=true;let epoch=voiceRuntime.epoch;
  try{
    if(callActive){interruptReply();epoch=voiceRuntime.epoch;voiceRuntime.busy=true;liveStatus('processing');await api('/api/call/cancel');}
    const v=await api('/api/task/control',{action,plan_id:id,call_id:voiceRuntime.callId});applyTask(v.result);await refreshAssets();await playControlAudio(v.result.audio,epoch,started);
  }catch(e){$('taskFeedback').textContent=shortError(e);}
  finally{$('confirm').disabled=false;$('cancel').disabled=false;if(epoch===voiceRuntime.epoch){voiceRuntime.busy=false;if(callActive&&!voiceRuntime.speaking)liveStatus(callMuted?'muted':'listening');}}
}
$('confirm').onclick=()=>controlTask('confirm');$('cancel').onclick=()=>controlTask('cancel');

const metricButton=document.createElement('button');metricButton.id='callMetrics';metricButton.className='ghost call-metrics';metricButton.textContent='— 秒';metricButton.title='回覆速度記錄';document.querySelector('.call-note').before(metricButton);
const dialog=document.createElement('dialog');dialog.id='metricsDialog';dialog.innerHTML='<div class="metrics-head"><strong>回覆速度</strong><button id="metricsClose" class="icon-btn" aria-label="關閉">×</button></div><div id="metricRows"></div><p class="metrics-hint">偵測到停句 → 開始播放；包含停句等待、辨識、AI 與語音產生。</p>';document.body.append(dialog);$('metricsClose').onclick=()=>dialog.close();metricButton.onclick=()=>{renderMetrics();dialog.showModal();};
function renderMetrics(){const latest=voiceRuntime.metrics.at(-1);if(latest){metricButton.textContent=(language==='zh'?'停句→回覆 ':'Reply ')+latest.speech_end_to_play_s.toFixed(2)+(language==='zh'?' 秒':' s');metricButton.title='ASR '+latest.asr_s.toFixed(2)+'s / AI與工具 '+latest.assistant_s.toFixed(2)+'s / TTS '+latest.tts_s.toFixed(2)+'s';}const rows=$('metricRows');rows.replaceChildren();for(const m of [...voiceRuntime.metrics].reverse().slice(0,10)){const row=document.createElement('div');row.className='metric-row';row.textContent=m.speech_end_to_play_s.toFixed(2)+'s　ASR '+m.asr_s.toFixed(2)+' / AI '+m.assistant_s.toFixed(2)+' / TTS '+m.tts_s.toFixed(2);rows.append(row);}}
$('close').onclick=async()=>{await endCall();await api('/api/shutdown').catch(()=>{});$('window').hidden=true;$('restore').hidden=true;try{window.close();}catch{}};
window.addEventListener('pagehide',()=>{voiceRuntime.stream?.getTracks().forEach(t=>t.stop());navigator.sendBeacon('/api/client/detach',JSON.stringify({key:liveKey}));});
async function initialize(){
  await api('/api/client/attach');
  for(let i=0;i<600;i++){
    let status;
    try{status=await api('/api/status',{}, {method:'GET'});}
    catch(e){loadingText='正在等待本機服務：'+shortError(e);$('compact').querySelector('.state span:last-child').textContent=loadingText;await new Promise(r=>setTimeout(r,1000));continue;}
    if(status.error)throw new Error(status.error);
    loadingText=status.phase||'正在準備本機模型…';
    if(status.presentation){
      $('localTitle').textContent='成果展示 · 合成素材';
      $('localScopeNote').textContent='獨立展示環境，只包含六個合成檔案。搜尋與模型推論均真實執行，不讀取個人磁碟。';
      $('localDrives').hidden=true;
      document.documentElement.dataset.presentation='true';
    }
    if(status.ready){
      liveReady=true;C.zh.ready='就緒';C.en.ready='Ready';C.zh.label='本機';C.en.label='Local';$('open').disabled=false;copy();syncTextControls();
      if($('taskInput').value.trim())showTaskStatus('模型已就緒，任務文字已保留，請送出。');
      try{await refreshAssets();}catch(e){showTaskStatus('素材清單載入失敗：'+shortError(e));}
      return;
    }
    $('compact').querySelector('.state span:last-child').textContent=loadingText;
    await new Promise(r=>setTimeout(r,1000));
  }
  throw new Error('啟動逾時，請重新開啟 App。');
}
updateCallUI();syncTextControls();refreshLocalStatus();setInterval(()=>{if(!localScopeState||localScopeState.state==='scanning')refreshLocalStatus();},1500);initialize().catch(e=>{loadingText='啟動未完成：'+shortError(e);$('compact').querySelector('.state span:last-child').textContent=loadingText;showTaskStatus(loadingText);});

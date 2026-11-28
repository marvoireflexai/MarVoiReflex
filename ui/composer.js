// Compact composer; dispatches to the existing import, chat, task and call controls.
(() => {
 'use strict';
 const labels={zh:{chat:'傳送訊息…',task:'輸入任務，例如：找出有汽車的照片…',add:'新增素材',openVoice:'開啟語音通話',startVoice:'開始語音通話',previewVoice:'語音通話預覽',sendChat:'送出訊息',sendTask:'送出任務'},en:{chat:'Message…',task:'Describe a task…',add:'Add assets',openVoice:'Open voice call',startVoice:'Start voice call',previewVoice:'Preview voice call',sendChat:'Send message',sendTask:'Send task'}};
 function syncComposers(){
  const words=labels[language],live=document.documentElement.dataset.runtime==='live';
  for(const pane of ['chat','task']){
   $(pane+'Input').placeholder=words[pane];
   for(const [suffix,label] of [['Add',words.add],['Mic',words.openVoice],['Voice',live?words.startVoice:words.previewVoice],['Send',pane==='chat'?words.sendChat:words.sendTask]]){
    const button=$(pane+suffix);button.title=label;button.setAttribute('aria-label',label);
   }
   $(pane+'Voice').disabled=$('callToggle').disabled;
  }
 }
 function voice(pane,start){
  $(pane==='task'?'callTaskMode':'callChatMode').click();
  setMode('call');window.MarVoiSidebar.close();
  if(start&&!callActive&&!$('callToggle').disabled)$('callToggle').click();
  $('callToggle').focus({preventScroll:true});
 }
 for(const pane of ['chat','task']){
  $(pane+'Add').onclick=()=>window.MarVoiSidebar.open('task',true);
  $(pane+'Mic').onclick=()=>voice(pane,false);
  $(pane+'Voice').onclick=()=>voice(pane,true);
  $(pane+'Input').addEventListener('keydown',event=>{
   if(event.key!=='Enter'||event.shiftKey||event.isComposing||event.keyCode===229||event.ctrlKey||event.altKey||event.metaKey)return;
   event.preventDefault();if(pane==='task')previewTask();else sendChat();
  });
 }
 const previousCopy=copy;copy=function(...args){const result=previousCopy.apply(this,args);syncComposers();return result;};
 new MutationObserver(syncComposers).observe($('callToggle'),{attributes:true,attributeFilter:['disabled']});
 syncComposers();
})();

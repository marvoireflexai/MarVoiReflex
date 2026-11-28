from pathlib import Path
from datetime import date
import json,re,secrets,threading,time,hashlib,os
import requests
from app_paths import data_root,model_url,bundle_root
from backend import Services,write_json
from voice_engine import VoiceEngine
from model_router import complete,complex_text,local_endpoint
from local_files import LocalFiles,wants_search,workspace_request,blocked_request,parse_query,IMAGE as LOCAL_IMAGES
from result_files import ResultFiles,capabilities
from search_progress import SearchProgress,SearchCancelled

class Runtime:
    def __init__(self,presentation_files=None):
        self.presentation=presentation_files is not None
        self.root=data_root();self.root.mkdir(parents=True,exist_ok=True);self.services=Services();self.voice=VoiceEngine();self.ready=False;self.error=None;self.phase='正在準備本機模型…';self.op_lock=threading.RLock();self.state_lock=threading.RLock();self.call_id=None;self.generation=0;self.speech_chunks=None;self.speech_lock=threading.RLock();self.chat_history=[];self.close_timer=None;self.client_attached=False
        if self.presentation:
            from presentation import roots_for
            self.local_files=LocalFiles(self.root,excluded=(bundle_root(),),discover=lambda mode:roots_for(presentation_files),presentation=True)
            self.local_files.set_scope('personal')
        else:self.local_files=LocalFiles(self.root,excluded=(bundle_root(),))
        self.local_vision=None;self.result_files=ResultFiles(self.root,self.local_files);self.search_progress=SearchProgress()
    def start(self):
        try:
            self.services.start(lambda phase:setattr(self,'phase',phase))
            from assistant_modes import Assistant
            from intent import Planner
            class GroundedPlanner(Planner):
                def ask(self,history,feedback=None,constraints=None):
                    c=dict(constraints or {})
                    if 'keyword_choices' not in c:c['keyword_choices']=getattr(self,'grounded_keywords',[''])
                    return super().ask(history,feedback,c)
            self.assistant=Assistant(self.root/'sessions'/'live',date.today(),42)
            self.vision_search=None;self.semantic_assets=None
            if os.environ.get('MARVOI_MODEL_PROFILE','gemma4-e2b-vision')=='gemma4-e2b-vision':
                from vision_search import VisionSearch
                self.vision_search=VisionSearch();self.local_vision=VisionSearch(persistent=False)
                try:
                    from semantic_assets import SemanticAssets
                    self.semantic_assets=SemanticAssets()
                except Exception:pass
            self.assistant.task.planner=GroundedPlanner(self.root/'sessions'/'task.requests.jsonl',42,date.today());self.ready=True;self.phase='就緒'
        except BaseException as e:self.error=str(e);self.services.stop()
    def call_start(self):
        if not self.ready:raise RuntimeError(self.error or '助理仍在啟動。')
        with self.state_lock:
            self.call_id=secrets.token_hex(16);self.generation+=1;cid=self.call_id;generation=self.generation
        self.voice.ensure()
        if not self.current(cid,generation):raise RuntimeError('通話已取消。')
        return {'call_id':cid,'voice':self.voice.voice_name,'asr':self.voice.asr_name,'asr_load_s':self.voice.load_s,'partial_asr':self.voice.moonshine_ready}
    def call_end(self):
        if hasattr(self,'search_progress'):self.search_progress.cancel_owner(self.call_id)
        with self.state_lock:self.call_id=None;self.generation+=1;self.speech_chunks=None
        self.voice.reset_stream()
    def cancel_turn(self):
        if hasattr(self,'search_progress'):self.search_progress.cancel_owner(self.call_id)
        with self.state_lock:self.generation+=1;self.speech_chunks=None
        self.voice.reset_stream()
    def current(self,call_id,generation):
        with self.state_lock:return call_id==self.call_id and generation==self.generation
    def log(self,value):
        p=self.root/'logs'/'latency.jsonl';p.parent.mkdir(exist_ok=True)
        with p.open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
    def chat(self,user):
        from semantics import MOVE,READ,SEARCH
        if re.search(MOVE+'|'+READ+'|'+SEARCH,user) and re.search(r'檔案|素材|圖片|文案|資料夾',user):
            return {'status':'chat','mode':'chat','text':'請切到交辦，我會先顯示預覽。','executed':False,'llm_s':0}
        prompt=f'你是 MarVoiReflex，本機中文語音助理。今天是{date.today()}。用台灣繁體中文自然對話，每次只說一到兩句，盡量六十字內，不使用 Markdown 或列表。聊天模式沒有檔案工具，不可假裝已操作電腦；想操作檔案請使用者切到交辦。使用者給的名稱、數字和條件依原文保留。'
        messages=[{'role':'system','content':prompt}]+self.chat_history[-8:]+[{'role':'user','content':user}];t=time.perf_counter()
        raw,route=complete({'messages':messages,'temperature':.1,'seed':42,'max_tokens':160,'stream':False,'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':True},prefer_advanced=complex_text(user));choice=raw['choices'][0];text=choice['message']['content'].strip()
        if not text:raise RuntimeError('模型沒有產生回覆。')
        self.chat_history.extend([{'role':'user','content':user},{'role':'assistant','content':text}]);self.chat_history=self.chat_history[-10:]
        return {'status':'chat','mode':'chat','text':text,'executed':False,'llm_s':time.perf_counter()-t,'model_route':route,'truncated':choice.get('finish_reason')=='length'}
    def task(self,text,owner=None):
        with self.search_progress.operation(owner):
            try:
                result=self._task(text)
                self.search_progress.check()
                refs=result.pop('_file_refs',None)
                if refs is not None:self.result_files.attach(result,refs)
                return result
            except SearchCancelled as e:return {'status':'cancelled','mode':'task','text':str(e),'selected':[]}

    def _task(self,text):
        from flow import paths_in,ScopeError
        from semantics import analyze
        task=self.assistant.task;task.clock=date.today();task.planner.clock=date.today()
        normalized=re.sub(r'[，。！？!?,\s]+$','',text).strip()
        # Normalize only unambiguous colloquial list requests, not model-generated actions.
        if re.fullmatch(r'我有(?:哪些|哪幾個|哪幾張|什麼)(?:圖片|照片|文案|檔案|素材|文件)(?:素材)?',normalized):
            text='列出全部'+re.sub(r'^我有(?:哪些|哪幾個|哪幾張|什麼)','',normalized).removesuffix('素材') if not normalized.endswith('什麼素材') else '列出全部素材'
            if text=='列出全部':text='列出全部素材'
            normalized=text
        if re.fullmatch(r'(?:好|好啊|好的|是|同意|確認|確定|直接搬|執行|開始執行|確認執行|確認搬移)+',normalized):
            return {'status':'clarify','mode':'task','text':'請在畫面按確認，才會搬動檔案。','preserve_pending':True}
        if normalized in ['取消','取消操作','不要執行','先不要動','先取消']:
            if task.pending:return dict(task.cancel(task.pending['id']),mode='task')
            return {'status':'cancelled','mode':'task','text':'沒有待確認的操作。'}
        if normalized in ['繼續搜尋','繼續搜尋下一批','搜尋下一批','下一批'] and self.local_files.mode:
            return self.local_search('',True)
        if normalized in ['清除圖片辨識快取','清除本次圖片快取']:
            if self.vision_search:self.vision_search.cache.clear()
            if self.local_vision:self.local_vision.cache.clear()
            return {'status':'clarify','mode':'task','text':'已清除本次工作階段的圖片辨識快取。請重新提出搜尋條件；工作區的確定結果仍可使用已驗證的內容索引。','preserve_pending':True}
        if normalized in ['建立素材索引','更新素材索引','建立圖片索引','更新圖片索引']:
            if not self.semantic_assets:return {'status':'clarify','mode':'task','text':'素材索引尚未就緒。','preserve_pending':True}
            return self.semantic_assets.build(task.catalog(),task.checked)
        from vision_search import is_visual_search
        if not workspace_request(text):
            if self.local_files.mode and wants_search(text):
                return self.local_search(text)
            if not self.local_files.mode and wants_search(text) and re.search(r'本機|電腦|桌面|下載|磁碟|[A-Za-z]槽|文件資料夾|圖片資料夾',text):
                return {'status':'clarify','mode':'task','text':'請先在任務頁啟用本機檔案搜尋，一次授權後不必匯入檔案。','preserve_pending':True}
            if self.local_files.mode and blocked_request(text):
                return {'status':'clarify','mode':'task','text':'本機檔案搜尋目前為唯讀。若要整理已匯入素材，請明確指定工作區；原始磁碟檔案不會被修改。','preserve_pending':True}
        if is_visual_search(text):
            if not self.vision_search:return {'status':'clarify','mode':'task','text':'圖片內容搜尋需要 Gemma 4 E2B 視覺版；目前使用的是文字模型。','preserve_pending':True}
            if paths_in(text) or re.search(r'本週|這週|上週|下週|今天|昨天|上個月|本月|日期|20\d{2}|\d{1,2}月\d{1,2}',text):
                return {'status':'clarify','mode':'task','text':'視覺實驗版僅搜尋已匯入圖片，不支援路徑或日期複合條件；請先匯入指定素材。','preserve_pending':True}
            if task.pending:task.cancel(task.pending['id'])
            assets=task.catalog()
            if self.semantic_assets:assets=self.semantic_assets.rank(text,assets)
            result=self.vision_search.search(text,assets,task.checked,self.search_progress)
            matches={x['path'] for m in ('yes','uncertain') for x in result.get('visual_results',{}).get(m,[])}
            result['_file_refs']=[a for a in assets if a['path'] in matches]
            return result
        spec=analyze(text,date.today(),paths_in(text))
        if spec['actions'] is None:return {'status':'clarify','mode':'task','text':'請說要做的素材任務。','preserve_pending':True}
        user=text if spec['resource'] else 'materials：'+text
        if not spec['error']:
            try:
                for path in paths_in(text):task.checked(path)
            except ScopeError as error:
                if task.pending:task.cancel(task.pending['id'])
                return {'status':'refused','mode':'task','text':'超出授權範圍，不能執行：'+str(error)}
            assets=task.catalog();candidates=set()
            for a in assets:
                m=re.match(r'(.+?)[_ -]+20\d{6}',a['name'])
                if m and m[1] in text:candidates.add(m[1])
            for a in assets:
                stem=Path(a['name']).stem
                if len(stem)>=2 and stem in text:candidates.add(stem)
            task.planner.grounded_keywords=['']+sorted(candidates,key=len,reverse=True)
            for candidate in sorted(candidates,key=len,reverse=True):
                if candidate in user and '「'+candidate+'」' not in user:user=user.replace(candidate,'「'+candidate+'」',1)
        result=task.request(user)
        if task.pending:result['plan_id']=task.pending['id'];result['items']=task.pending['items']
        return result
    def local_search(self,text,continuation=False):
        from vision_search import is_visual_search
        try:
            visual=False
            if not continuation:
                q=parse_query(text)
                explicit=bool(re.search(r'檔名|檔案名稱|名稱包含|\.[A-Za-z0-9]{2,5}\b',text))
                visual=not explicit and (is_visual_search(text) or bool(q['keyword'] and q['extensions'] and q['extensions']&LOCAL_IMAGES))
                if visual and not self.local_vision:return {'status':'clarify','mode':'task','text':'目前模型不支援圖片內容搜尋，可使用檔名條件。','preserve_pending':True}
            # Search cannot execute or modify files. Invalidate any old workspace confirmation.
            task=self.assistant.task
            if task.pending:task.cancel(task.pending['id'])
            result=self.local_files.search(text,visual,self.local_vision.classify if self.local_vision else None,continuation,self.search_progress)
            with self.local_files.lock:
                rows=[]
                for a in result.get('local_results',[]):
                    try:rows.append(dict(a,source='local',**capabilities(self.local_files._result_path(a['id']))))
                    except (OSError,ValueError):continue
                result['file_results']=rows
            return result
        except (ValueError,PermissionError) as exc:return {'status':'clarify','mode':'task','text':str(exc),'preserve_pending':True}
    def set_local_scope(self,mode):
        if self.presentation and mode=='drives':raise PermissionError('展示模式僅限合成素材。')
        self.search_progress.cancel_local()
        result=self.local_files.set_scope(mode)
        if self.local_vision:
            from vision_search import VisionSearch
            self.local_vision=VisionSearch(persistent=False)
        return result
    def local_continue(self):
        if not self.ready:raise RuntimeError('本機模型尚未就緒。')
        if not self.op_lock.acquire(blocking=False):raise RuntimeError('BUSY')
        try:
            with self.search_progress.operation():
                try:return self.local_search('',True)
                except SearchCancelled as e:return {'status':'cancelled','mode':'task','text':str(e),'selected':[]}
        finally:self.op_lock.release()
    @staticmethod
    def spoken(result):
        if result['mode']=='chat':return result['text']
        status=result['status'];n=len(result.get('selected',[]))
        if status=='preview':return f'找到{len(result.get("items",[]))}份符合的素材。請查看任務預覽，按確認後才會整理。'
        if status in ['searched','listed']:
            if result.get('local_results') is not None:
                extra='，另有候選可繼續搜尋' if result.get('local_more') else ''
                return f'這一批找到{n}個確定符合的檔案{extra}。請查看任務結果。'
            return f'找到{n}個檔案，清單已顯示。'
        if status=='completed':return f'已整理{result.get("moved",0)}個檔案，驗證通過。'
        if status=='read':return result['text'][:150]
        return result['text'][:140]
    def partial_voice(self,content,call_id,utterance):
        if not isinstance(utterance,str) or not re.fullmatch(r'[0-9a-z-]{1,64}',utterance):raise ValueError('Invalid utterance')
        with self.state_lock:
            if not call_id or call_id!=self.call_id:raise PermissionError('通話已結束。')
            generation=self.generation
        text=self.voice.partial(content,(call_id,generation,utterance))
        if not self.current(call_id,generation):return {'text':'','cancelled':True}
        return {'text':text or '','available':text is not None}
    def voice_chunk(self,call_id,turn_id,index):
        if not isinstance(index,int) or isinstance(index,bool):raise ValueError('Invalid chunk index')
        with self.speech_lock:
            with self.state_lock:
                q=self.speech_chunks
                if not q or not call_id or q['call_id']!=call_id or q['turn_id']!=turn_id or not self.current(call_id,q['generation']):raise PermissionError('語音回覆已取消。')
                if index<0 or index>=len(q['texts']):raise ValueError('Invalid chunk index')
                if index in q['audio']:return q['audio'][index]
            audio=self.voice.synthesize(q['texts'][index])
            if not audio:raise RuntimeError('語音合成未完成。')
            with self.state_lock:
                if self.speech_chunks is not q or not self.current(call_id,q['generation']):raise PermissionError('語音回覆已取消。')
                q['audio'][index]=audio
            return audio
    def begin_speech(self,text,call_id,generation,turn_id):
        chunks=self.voice.split(text)
        if not chunks:return None,0
        with self.state_lock:
            if not self.current(call_id,generation):return None,0
            self.speech_chunks={'call_id':call_id,'generation':generation,'turn_id':turn_id,'texts':chunks,'audio':{}}
        try:return self.voice_chunk(call_id,turn_id,0),len(chunks)
        except Exception:return None,0
    @staticmethod
    def is_voice_task(text):
        # Chat can route explicit file commands; questions about how to work stay in chat.
        if re.search(r'怎麼|如何|為什麼|什麼意思|教我',text):return False
        if text.strip().rstrip('。！!') in ('繼續搜尋','繼續搜尋下一批','搜尋下一批','下一批'):return True
        if re.search(r'^我(?:有|的).*(?:哪些|哪幾|什麼).*(?:圖片|照片|文件|文案|檔案|素材)',text):return True
        return bool(re.search(r'^(?:(?:請|麻煩|幫我|可以幫我)\s*)*(?:找出|找一下|找找|找|搜尋|搜索|尋找|查找|列出|讀取|讀出|查看|整理|分類|預覽|搬移|移動|複製|刪除|改名)',text.strip()) and re.search(r'檔案|文件|資料夾|素材|圖片|照片|相片|圖檔|文案|桌面|下載|電腦|磁碟|PDF|TXT|\.\w{2,5}\b',text,re.I))
    def turn(self,content,mode,call_id):
        if mode not in ['chat','task']:raise ValueError('請選擇聊天或交辦。')
        with self.state_lock:
            if not call_id or call_id!=self.call_id:raise PermissionError('通話已結束。')
            generation=self.generation
        if not self.op_lock.acquire(blocking=False):raise RuntimeError('BUSY')
        began=time.perf_counter();turn_id=secrets.token_hex(12)
        try:
            asr=self.voice.transcribe(content,verify=(mode=='task'))
            if not self.current(call_id,generation):return {'status':'cancelled','turn_id':turn_id}
            if not asr['text']:return {'status':'no_speech','turn_id':turn_id,'metrics':{'asr_s':asr['asr_s'],'server_total_s':time.perf_counter()-began}}
            # Automatic read/preview only. All changes still require existing plan confirmation.
            task_mode=mode=='task' or self.is_voice_task(asr['text'])
            if task_mode and mode=='chat' and asr.get('engine')=='moonshine':
                asr=self.voice.transcribe(content,verify=True)
                if not self.current(call_id,generation):return {'status':'cancelled','turn_id':turn_id}
            start=time.perf_counter()
            if task_mode:
                mode='task'
                if not asr.get('text') or asr.get('low_confidence'):
                    result={'status':'clarify','mode':'task','text':'剛才的指令沒有辨識清楚，請再說一次完整的任務。我還沒有執行任何操作。','preserve_pending':True}
                else:
                    result=self.task(asr['text'],owner=call_id)
            else:result=self.chat(asr['text'])
            processing=time.perf_counter()-start
            if not self.current(call_id,generation):return {'status':'cancelled','turn_id':turn_id}
            audio,chunk_count=self.begin_speech(self.spoken(result),call_id,generation,turn_id)
            metrics={'asr_s':asr['asr_s'],'assistant_s':processing,'tts_s':audio['tts_s'] if audio else 0,'server_total_s':time.perf_counter()-began,'input_audio_s':asr['audio_seconds'],'reply_audio_s':audio['audio_seconds'] if audio else 0}
            self.log({'event':'server_turn','at':time.time(),'turn_id':turn_id,'mode':mode,'result_status':result['status'],'recognized_chars':len(asr['text']),'reply_chars':len(result['text']),**metrics})
            if not self.current(call_id,generation):return {'status':'cancelled','turn_id':turn_id}
            return {'status':'ok','turn_id':turn_id,'recognized':asr['text'],'result':result,'audio':audio,'chunk_count':chunk_count,'metrics':metrics,'asr':asr.get('engine')}
        finally:self.op_lock.release()
    def text(self,mode,text):
        if not self.ready:raise RuntimeError(self.error or '助理仍在啟動。')
        if not self.op_lock.acquire(blocking=False):raise RuntimeError('BUSY')
        try:return self.chat(text) if mode=='chat' and not self.is_voice_task(text) else self.task(text)
        finally:self.op_lock.release()
    def control(self,action,plan_id,call_id=None):
        if action not in ['confirm','cancel']:raise ValueError('未知操作。')
        with self.op_lock:
            result=self.assistant.handle('task',control=action,plan_id=plan_id)
            with self.state_lock:active=bool(call_id and call_id==self.call_id)
            if active:result['audio']=self.voice.synthesize(self.spoken(result))
            return result
    def stop(self):
        self.call_end();self.voice.close();self.local_files.close()
        if getattr(self,'semantic_assets',None):self.semantic_assets.close()
        self.services.stop()

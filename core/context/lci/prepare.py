from typing import TYPE_CHECKING,Optional,Iterable

if TYPE_CHECKING:
    from config.settings import LciSettings
    from core.context.lci.model import LciTaskPayload
    from core.session.session_model import ChatSession, ChatMessage


class _Preparer:
    @staticmethod
    def prepare(
        session: "ChatSession", 
        settings: "LciSettings"
        ):
        
        history = session.shallow_history
        required=set(settings.include)
        
        return _Preparer._filter(history,required)
    
    

    def _filter(history:list['ChatMessage'],required:Iterable):

        items=[]
        
        for item in history:

            if item['role'] in required:
                items.append(item)
                continue

            # 理论上是必有的
            info = set(item.get('info',{}).keys())

            if info & required:
                items.append(item)
            
        return items




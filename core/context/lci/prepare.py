from typing import TYPE_CHECKING,Literal
if TYPE_CHECKING:
    from config.settings import LciSettings
    from core.session.session_model import ChatSession, ChatMessage


class _Preparer:
    @staticmethod
    def prepare(
        session: "ChatSession", 
        settings: "LciSettings",
        ):
        
        history = session.shallow_history
        required=set(settings.include)
        
        return _Preparer._filter(history,required)
    
    @staticmethod
    def _filter(
        history:list['ChatMessage'],
        required:set,
        collect_mode:Literal['newest','jumpcut'] = ''
        ):

        items=[]
        
        for item in history:

            if item['role'] in required:
                items.append(item)
                continue

            if item.get('info', {}).keys() & required:
                items.append(item)
            
        return items




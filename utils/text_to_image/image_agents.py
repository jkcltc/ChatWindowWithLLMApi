from PyQt5.QtCore import QObject,pyqtSignal
import os
import configparser
if __name__=='__main__':
    from providers.novita.novita_model_manager import NovitaAgent
    from providers.siliconflow.siliconflow_agent import SiliconFlowAgent
else:
    from .providers.novita.novita_model_manager import NovitaAgent


class ImageApiConfigReader:
    @staticmethod
    def get_api_key(application_path='api_config.ini',provider_name=''):
        if not '.ini' in application_path:
            raise AttributeError('api_config should be a .ini file')
        config = configparser.ConfigParser()
        config.read(application_path)
        return config[provider_name]['key']
    

class ImageAgent(QObject):      #Factory Class
                                #waiting 0.25.2 patch
    pull_success=pyqtSignal(str)#path to image
    failure=pyqtSignal(str,str)
    def __init__(self,application_path):
        super().__init__()  # 确保正确初始化QObject
        self.generator_dict = {
            'novita': NovitaAgent,
            'siliconflow':SiliconFlowAgent
        }
        self.generator_name = None
        self.generator = None 
        self.application_path=application_path
        self.api_config_path=os.path.join(self.application_path,'api_config.ini')
        self._start_model_map_update()
        
    def set_generator(self,name):
        """
        Sets the image generator to use based on the provided name.

        This method updates the current generator by:
        - Storing the generator's name.
        - Retrieving the API key for the specified generator using the configuration reader.
        - Instantiating the generator object with the API key, application path, and a save folder.
        - Connecting the generator's `pull_success` and `failure` signals to the corresponding signals of this class.

        Args:
            name (str): The name of the image generator to set.
        """
        self.generator_name=name
        api_key=ImageApiConfigReader.get_api_key(self.api_config_path,name)
        self.generator=self.generator_dict[name](api_key,self.application_path,save_folder='pics')
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)

    def create(self,params_dict):
        '''
        {
            #Required:
            'prompt': "required",     
            'model': "required", 
            'negative_prompt': "",              # 负面提示实际上没有也行
            
            #Unversal
            'width': 512,                       # 生成图片宽度（像素），默认512
            'height': 512,                      # 生成图片高度（像素），默认512
            
            #Novita
            'image_num': 1,                     # 生成图片数量，默认1
            'steps': 20,                        # 迭代步数，默认20
            'seed': -1,                         # 随机种子，-1表示随机生成
            'clip_skip': 1,                     # CLIP跳过层数，默认1
            'sampler_name': "Euler a",          # 采样器名称，默认"Euler a"
            'guidance_scale': 7.5,               # 指导系数(CFG)，默认7.5

            #Siliconflow
            'image_num': 1,
            'steps': 20,
            'guidance_scale': 7.5,
            'seed': -1,
        }
        '''
        self.generator.create(
            self.generator.translate_params(params_dict)
            )

    def get_model_list(self,provider):
        """
        Retrieves the list of available models for a specified provider.

        Args:
            provider (str): The name of the provider whose model list is to be retrieved.

        Returns:
            list: A list of model names available for the given provider. If the provider is not found,
                  returns a list containing a single string indicating failure.
        """
        if provider in self.generator_dict:
            generator=self.generator_dict[provider]('',self.application_path)
        else:
            return ['Fail:no model list found']
        return generator.get_model_list()
    
    def current_model_list(self):
        return self.generator.get_model_list()
    
    def get_model_map(self):
        '''
        retrun:
            {
            'provider1':['model1','model2','model3'],
            'provider2':['model1','model2','model3']
            }
        '''
        return {'provider1':['model1','model2','model3']}#占位符

    def _start_model_map_update(self):
        return

if __name__=='__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    a=ImageAgent(application_path=r'')
    a.set_generator('novita')
    a.pull_success.connect(print)
    a.failure.connect(print)
    a.create({
        'prompt':'an apple on a banana tree',
        'model':'flat2DAnimerge_v30_72593.safetensors',
        'negative_prompt':''
    })
    app.exec_()


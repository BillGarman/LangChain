import os
from io import BytesIO
from typing import Any, List, Optional
from PIL import Image
from langchain.docstore.document import Document
from langchain.utils import get_from_dict_or_env
import boto3



class AwsTextractExtraction:


    def __init__(self,aws_region_name : str,aws_secret_key : str,aws_access_key,aws_session_token,file_path : str):
   

          self.aws_region_name  =  aws_region_name
          self.aws_secret_key=  aws_secret_key
          self.aws_access_key =  aws_access_key
          self.aws_session_token = aws_session_token
          self.file_path = file_path
          try:
            import boto3

          except ImportError:
                raise ValueError(
                    "Could not import aws boto3 package. "
                    "Please install it with `pip install boto3`."
                )



    def get_text_from_image(self)-> List[Document]:
         output=[] 
         page_no=0
         
         textract_client =  boto3.client('textract',region_name,aws_access_key,aws_secret_key,aws_session_token)
         Pil_Image_obj=  Image.open(self.file_path)
         buf = BytesIO()
         Pil_Image_obj.save(buf, format='PNG')
         image_bytes = buf.getvalue()
        

         response=  textract_client.detect_document_text(Document={'Bytes': image_bytes})
         detected_txt =''
         for item in response["Blocks"]:
              if  item['BlockType'] == 'LINE':
                   detected_txt  += item['Text'] + '\n'
         
         metadata = {"source": self.file_path,"page":page_no}

         output.append(Document(page_content=detected_txt  , metadata=metadata))  
         return output

   


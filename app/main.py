import os
import datetime
import time
import json 

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.storage.blob import BlobServiceClient, generate_account_sas, ResourceTypes, AccountSasPermissions, BlobClient, generate_blob_sas, BlobSasPermissions

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

print("Hello World!")

sa_name = os.environ['SA_NAME']
sas_token = os.environ['SA_KEY']

cvkey = os.environ['ACCOUNT_KEY']
cvendpoint = os.environ['ENDPOINT']

credentials = CognitiveServicesCredentials(cvkey)
cvclient = ComputerVisionClient(
    endpoint=cvendpoint,
    credentials=credentials
)

aiendpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
aideployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")

# gets the API Key from environment variable AZURE_OPENAI_API_KEY
aiclient = AzureOpenAI(
    azure_endpoint=aiendpoint,
    api_version="2024-05-01-preview",
)


def create_service_sas_blob(blob_client: BlobClient, account_key: str):
    # Create a SAS token that's valid for one day, as an example
    start_time = datetime.datetime.now(datetime.timezone.utc)
    expiry_time = start_time + datetime.timedelta(days=1)

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry_time,
        start=start_time
    )

    return sas_token

service = BlobServiceClient(account_url=f"https://{sa_name}.blob.core.windows.net/", credential=sas_token)
containerclient = service.get_container_client("historicsociety")

blobs = containerclient.list_blobs(name_starts_with="card-catalog-c")
#blobs = containerclient.list_blobs(name_starts_with="card-catalog-c/CardCatalogueCC-0002")
list_blobs = list(blobs)
list_blob_urls = []
for b in list_blobs:
    if b.name.endswith('.jpg'):
        blobclient = containerclient.get_blob_client(b.name)
        blobsastoken = create_service_sas_blob(blobclient, sas_token)
        list_blob_urls.append(f'{blobclient.url}?{blobsastoken}')

def extract_text(url):
    retval = {}
    #print(url)
    raw = True
    numberOfCharsInOperationId = 36

    # SDK call
    rawHttpResponse = cvclient.read(url, language="en", raw=True)

    # Get ID from returned headers
    operationLocation = rawHttpResponse.headers["Operation-Location"]
    #print(operationLocation)
    idLocation = len(operationLocation) - numberOfCharsInOperationId
    #print(idLocation)
    operationId = operationLocation[idLocation:]
    #print(operationId)

    # SDK call
    time.sleep(5)
    result = cvclient.get_read_result(operationId)
    #print(result.status)
    while(result.status == OperationStatusCodes.running):
        result = cvclient.get_read_result(operationId)
        #print(result.status)
        time.sleep(1)

    # Get data
    if result.status == OperationStatusCodes.succeeded:
        retval = result.as_dict()
    return retval

def extract_openai_user_prompt(extracted_dict):
    str_arr = []
    for r in extracted_dict['analyze_result']['read_results']:
        for l in r['lines']:
            #print(l['text'])
            #print(l['bounding_box'])
            tl = (l['bounding_box'][0],l['bounding_box'][1])
            tr = (l['bounding_box'][2],l['bounding_box'][3])
            br = (l['bounding_box'][4],l['bounding_box'][5])
            bl = (l['bounding_box'][6],l['bounding_box'][7])
            width = tr[0] - tl[0]
            height = br[1] - tl[1]
            #print(f"top-left={tl}")
            #print(f"width={width}")
            #print(f"height={height}")
            #print("|")
            str_arr.append(f"{l['text']}\n{l['bounding_box']}\n|")
    return "\n".join(str_arr)

def use_ai_to_get_entry(url):
    extracted_dict = extract_text(url)
    user_prompt = extract_openai_user_prompt(extracted_dict)
    #print (user_prompt)
        
   
        
    completion = aiclient.chat.completions.create(
        model=aideployment,
        messages= [
            {
                "role": "system",
                "content": "You are an AI assistant that helps create a digital card catalog. \n\nYou are trying to generate table rows where the column headings are call number, title, and additional details delimit each column by |"
            },
            {
                "role": "user",
                "content": "R\n[16.0, 23.0, 40.0, 22.0, 42.0, 48.0, 17.0, 50.0]\n|\nCivil War Veterans of Rock Island Co.\n[235.0, 22.0, 970.0, 21.0, 970.0, 49.0, 235.0, 50.0]\n|\n929.2\n[20.0, 54.0, 120.0, 53.0, 120.0, 78.0, 20.0, 79.0]\n|\nAppleby, Barbara M\n[163.0, 56.0, 525.0, 55.0, 526.0, 83.0, 163.0, 87.0]\n|\nApp\n[17.0, 90.0, 82.0, 93.0, 80.0, 121.0, 17.0, 118.0]\n|\nCivil War Veterans of Rock Island Co.\n[240.0, 88.0, 970.0, 88.0, 970.0, 116.0, 240.0, 115.0]\n|\nIL.\n[164.0, 124.0, 217.0, 125.0, 217.0, 148.0, 164.0, 146.0]\n|\nAncestors of Barbara Appleby. 1998.\n[259.0, 121.0, 953.0, 121.0, 953.0, 153.0, 259.0, 151.0]\n|\nunpaged - soft cover\n[241.0, 190.0, 641.0, 189.0, 642.0, 219.0, 241.0, 223.0]\n|"
            },
            {
                "role": "assistant",
                "content": "929.2 App | Civil War Veterans of Rock Island Co. IL. Ancestors of Barbara Appleby. 1998. | Appleby, Barbara M. unpaged - soft cover "
            },
            {
                "role": "user",
                "content": "R\n[4.0, 22.0, 24.0, 22.0, 25.0, 45.0, 5.0, 46.0]\n|\n1890 Civil War veterans census, TN\n[207.0, 18.0, 862.0, 22.0, 862.0, 48.0, 207.0, 46.0]\n|\n973.\n[4.0, 54.0, 79.0, 56.0, 79.0, 78.0, 4.0, 79.0]\n|\nSistler, Byron and Sistler, Barbara\n[127.0, 54.0, 821.0, 54.0, 821.0, 80.0, 127.0, 80.0]\n|\n76\n[7.0, 87.0, 45.0, 88.0, 44.0, 112.0, 6.0, 112.0]\n|\n1890 Civil War veterans census,\n[209.0, 86.0, 816.0, 90.0, 816.0, 115.0, 209.0, 112.0]\n|\nSis\n[5.0, 121.0, 64.0, 123.0, 64.0, 146.0, 5.0, 145.0]\n|\nTennessee/ Pub. B. Sistler & Associates\n[124.0, 120.0, 861.0, 120.0, 861.0, 148.0, 124.0, 149.0]\n|\n355 p.\n[206.0, 188.0, 322.0, 191.0, 322.0, 219.0, 205.0, 216.0]\n|"
            },
            {
                "role": "assistant",
                "content": "973.76 Sis | 1890 Civil War veterans census, Tennessee. | Sistler, Byron and Barbara  Published by B. Sistler & Associates. 355 pages"
            },
            {
            "role": "user",
            "content": user_prompt
            }
        ],
        max_tokens=800,
        temperature=0.1,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None,
        stream=False
    )
    #print(completion.to_json())
    #print(completion.choices[0].message.content)

    #rest between calls
    time.sleep(3)

    user_prompt=completion.choices[0].message.content
    completion = aiclient.chat.completions.create(
        model=aideployment,
        messages= [
            {
                "role": "system",
                "content": "You are an AI assistant that helps create a digital card catalog. \n\nGiven the user provided information, determine the call number, title and any additional information and return in a json format"
            },
            {
            "role": "user",
            "content": user_prompt
            }
        ],
        max_tokens=800,
        temperature=0.1,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None,
        stream=False
    )

    str_content = completion.choices[0].message.content
    json_content = json.loads(str_content)
    json_content['source_image']=url.split("?")[0]
    #print(json_content)
    return f"{json_content['call_number']} ~{json_content['title']} ~{json_content['additional_information']} ~{json_content['source_image'].split("/historicsociety/")[1]}"


print("")
for i in range(0,5):
    url = list_blob_urls[i]
    #print(f"Trying:  {url}")
    #print("result>")
    print(use_ai_to_get_entry(url))
    print("")
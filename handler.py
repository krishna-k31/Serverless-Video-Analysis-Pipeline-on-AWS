__copyright__   = "Copyright 2024, VISA Lab"
__license__     = "MIT"

import os
# import imutils
import cv2
import json
from PIL import Image, ImageDraw, ImageFont
from facenet_pytorch import MTCNN, InceptionResnetV1
from shutil import rmtree
import numpy as np
import torch
import boto3

s3 = boto3.client('s3')

os.environ['TORCH_HOME'] = '/tmp/'

mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() # initializing resnet for face img to embeding conversion

def face_recognition_function(key_path):
    # Face extraction
    img = cv2.imread(key_path, cv2.IMREAD_COLOR)
    boxes, _ = mtcnn.detect(img)

    # Face recognition
    key = os.path.splitext(os.path.basename(key_path))[0].split(".")[0]
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    face, prob = mtcnn(img, return_prob=True, save_path=None)

    data_bucket_name = '####'
    # Local path where data.pt will be downloaded
    local_data_pt_path = '/tmp/data.pt'
    s3.download_file(data_bucket_name, 'data.pt', local_data_pt_path)

    # Download data.pt file from S3 bucket

    saved_data = torch.load('/tmp/data.pt')  # loading data.pt file
    if face != None:
        emb = resnet(face.unsqueeze(0)).detach()  # detech is to make required gradient false
        embedding_list = saved_data[0]  # getting embedding data
        name_list = saved_data[1]  # getting list of names
        dist_list = []  # list of matched distances, minimum distance is used to identify the person
        for idx, emb_db in enumerate(embedding_list):
            dist = torch.dist(emb, emb_db).item()
            dist_list.append(dist)
        idx_min = dist_list.index(min(dist_list))

        # Save the result name in a file
        with open("/tmp/" + key + ".txt", 'w+') as f:
            f.write(name_list[idx_min])
        return name_list[idx_min]
    else:
        print(f"No face is detected")
    return

def handler(event, context):
    try:
        # Extract parameters from the event
		
        # bucket_name = event['Records'][0]['s3']['bucket']['name']
        # image_file_name = event['Records'][0]['s3']['object']['key']
        
        print(event,type(event),event.items())
        # payload = json.loads(event['body'])
        bucket_name = event['bucket_name']
        image_file_name = event['image_file_name']

        # Define the path to the image file in S3
        image_key = os.path.join(bucket_name, image_file_name)

        # Define the local path to download the image file
        local_image_path = '/tmp/' + image_file_name

        # Download the image file from S3 to local storage
        s3.download_file(bucket_name, image_file_name, local_image_path)

        # Perform face recognition
        recognized_name = face_recognition_function(local_image_path)

        # Define the result file name and path
        result_file_name = os.path.splitext(image_file_name)[0] + '.txt'
        local_result_path = '/tmp/' + result_file_name

        # Write the recognized name to the result file
        with open(local_result_path, 'w') as f:
            f.write(recognized_name)

        # Define the key for uploading the result file to the output bucket
        output_bucket_name = bucket_name.split('-')[0] + '-output'  # Extract ASU ID and add "-output"
        #output_key = os.path.join(output_bucket_name, result_file_name)
        output_key = os.path.join(result_file_name)
        print(output_key)
        # Upload the result file to the output bucket
        print(local_result_path, output_bucket_name, result_file_name)
        s3.upload_file(local_result_path, output_bucket_name, result_file_name)

        return {
            'statusCode': 200,
            'body': json.dumps({'recognized_name': recognized_name})
        }
    except Exception as e:
        print(f"An error occurred: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

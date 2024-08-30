import io
import os
from flask import Flask,request,jsonify
from flask_cors import CORS
import numpy as np
from io import BytesIO
import base64
from PIL import Image
# for model
from torchvision import transforms # type: ignore
import torchvision.transforms # type: ignore
import timm # type: ignore
import torch # type: ignore
import torch.nn as nn # type: ignore
from typing import List, Tuple
#mongodb
from pymongo import MongoClient # type: ignore
#rag
from PyPDF2 import PdfReader #type: ignore
#rag image
import fitz  # type: ignore # PyMuPDF

app=Flask(__name__)
CORS(app,origins=['*'],methods=['POST','GET'],headers=['Content-Type'])

#device(GPU)
device = 'cuda' if torch.cuda.is_available() else 'cpu'

#class name
class_names =['Aloevera', 'Amla', 'Amruthaballi', 'Arali', 'Astma_weed', 'Badipala', 'Balloon_Vine', 'Bamboo', 'Beans', 'Betel', 'Bhrami', 'Bringaraja', 'Caricature', 'Castor', 'Catharanthus', 'Chakte', 'Chilly', 'Citron lime (herelikai)', 'Coffee', 'Common rue(naagdalli)', 'Coriender', 'Curry', 'Doddpathre', 'Drumstick', 'Ekka', 'Eucalyptus', 'Ganigale', 'Ganike', 'Gasagase', 'Ginger', 'Globe Amarnath', 'Guava', 'Henna', 'Hibiscus', 'Honge', 'Insulin', 'Jackfruit', 'Jasmine', 'Kambajala', 'Kasambruga', 'Kohlrabi', 'Lantana', 'Lemon', 'Lemongrass', 'Malabar_Nut', 'Malabar_Spinach', 'Mango', 'Marigold', 'Mint', 'Neem', 'Nelavembu', 'Nerale', 'Nooni', 'Onion', 'Padri', 'Palak(Spinach)', 'Papaya', 'Parijatha', 'Pea', 'Pepper', 'Pomoegranate', 'Pumpkin', 'Raddish', 'Rose', 'Sampige', 'Sapota', 'Seethaashoka', 'Seethapala', 'Spinach1', 'Tamarind', 'Taro', 'Tecoma', 'Thumbe', 'Tomato', 'Tulsi', 'Turmeric', 'ashoka', 'camphor', 'kamakasturi', 'kepala']
#model
model = timm.create_model('xception', pretrained=True)
model.fc = nn.Linear(2048, 80)
state_dict = torch.load(r'P:\\Herbal_Detecter_App\\backend\\plants_best_model.pth', map_location=torch.device('cpu'), weights_only=True)
state_dict['fc.weight'] = state_dict.pop('fc.1.weight')
state_dict['fc.bias'] = state_dict.pop('fc.1.bias')
model.load_state_dict(state_dict, strict=False)


#transform
transform = transforms.Compose([
    transforms.Resize((299, 299)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

#prediction
def pred(model: torch.nn.Module,image_path: bytes,class_names: List[str],image_size: Tuple[int, int] = (299, 299),transform: torchvision.transforms = None,device: torch.device=device):
    
    img = Image.open(BytesIO(image_path))

    if transform is not None:
        image_transform = transform
    else:
        image_transform = transforms.Compose([
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

    model.to(device)

    model.eval()
    with torch.inference_mode():
      transformed_image = image_transform(img).unsqueeze(dim=0)

      target_image_pred = model(transformed_image.to(device))

    target_image_pred_probs = torch.softmax(target_image_pred, dim=1)

    target_image_pred_label = torch.argmax(target_image_pred_probs, dim=1)
    
    output =class_names[target_image_pred_label]
    return output

#mongodb
mongourl = "mongodb+srv://nmdharineesh2004:mongodb123@cluster0.1ebq3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
try:
    client = MongoClient(mongourl)
    db = client.get_database('herbal_app')
    herb_collection = db['herbs']
    # Test the connection by attempting to retrieve one document
    test_doc = herb_collection.find_one()
    if test_doc:
        print("Successfully connected to MongoDB.")
    else:
        print("Connected to MongoDB, but the collection is empty.")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    
# Function to extract text from PDF
def extract_pdf_content(pdf_path):
    reader = PdfReader(pdf_path)
    extracted_text = []
    
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text.append(text)
    
    return extracted_text

# Provide the path to the PDF file here
pdf_path = "plant finals.pdf"
extracted_text = extract_pdf_content(pdf_path)
pdf1_path = r"plant images[1].pdf"


#function to fecth image from pdf
def extract_images_from_pdf_based_on_query(pdf1_path, query=None):
    pdf_document = fitz.open(pdf1_path)
    matching_images = []

    for page_number in range(len(pdf_document)):
        page = pdf_document[page_number]
        text = page.get_text("text")

        if query is None or query.lower() in text.lower():
            image_list = page.get_images(full=True)
            print(f"Images found on page {page_number + 1}: {len(image_list)}")  # Log the number of images found
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image = Image.open(io.BytesIO(image_bytes))
                
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                matching_images.append(img_base64)
                   
    pdf_document.close()
    return matching_images

#routing,api
@app.route('/')
def home():
    return 'Welcome to the backend server of herbal identifier'

@app.route('/predict',methods=['POST'])
def predict():
    data =request.get_json()
    base64img =data.get('image')

    if not base64img:
        return jsonify({'error':'No image data found'}),400
        
    try:
        image_data = base64.b64decode(base64img)
        op =pred(model=model,image_path=image_data,class_names=class_names,transform=transform,image_size=((256,256)))
        
        matches = [page for page in extracted_text if op.lower() in page.lower()]
        images = extract_images_from_pdf_based_on_query(pdf1_path,op)

        if matches:
            return jsonify({"status":"ok","predicted_class":op,"result": matches[0],"images": images})
        else:
            return jsonify({"status": "error", "message": "Herb not found"}), 404
        
    except Exception as e:
        print(f"Error processing image :{e}")
        return jsonify({'error':'Failed to process image'}),500    

if __name__ == '__main__':
    app.run(debug=True ,host='0.0.0.0')
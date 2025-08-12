import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# Tesseract'ın kurulum yolunu belirtin
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Dosya seçilmedi')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Dosya seçilmedi')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                summary = analyze_blood_test(filepath)
                session['summary'] = summary
                return redirect(url_for('upload_file'))
            except Exception as e:
                flash(f'Dosya analiz edilirken bir hata oluştu: {e}')
                return redirect(request.url)

    summary = session.pop('summary', None)
    return render_template('index.html', summary=summary)

def analyze_blood_test(filepath):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    file_extension = filepath.rsplit('.', 1)[1].lower()
    text = ""

    if file_extension == 'pdf':
        with fitz.open(filepath) as doc:
            for page in doc:
                text += page.get_text()
    elif file_extension in ['png', 'jpg', 'jpeg']:
        text = pytesseract.image_to_string(Image.open(filepath), lang='tur')
    elif file_extension == 'txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

    prompt = f'''Aşağıdaki kan tahlili sonuçlarını analiz et ve JSON formatında bir çıktı üret.
    
    JSON yapısı şu şekilde olmalı:
    {{
      "results": [
        {{
          "test": "Test Adı",
          "value": "Hastanın Sonucu",
          "unit": "Birimi",
          "range": "Referans Aralığı",
          "status": "Yüksek, Düşük veya Normal"
        }}
      ],
      "advice": "Genel bir değerlendirme ve tavsiye."
    }}

    - Her bir kan tahlili değeri için "results" listesine bir obje ekle.
    - "status" alanı için sadece "Yüksek", "Düşük" veya "Normal" kelimelerinden birini kullan.
    - "advice" alanına genel bir tıbbi olmayan tavsiye ve özet ekle.
    - Sadece ve sadece JSON formatında çıktı ver. Başka hiçbir metin ekleme.

    Kan Tahlili Sonuçları:
    {text}
    '''
    
    response = model.generate_content(prompt)
    
    cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
    
    try:
        summary_data = json.loads(cleaned_response)
        return summary_data
    except json.JSONDecodeError:
        raise Exception("Yapay zeka modelinden gelen yanıt işlenemedi. Lütfen tekrar deneyin.")

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)